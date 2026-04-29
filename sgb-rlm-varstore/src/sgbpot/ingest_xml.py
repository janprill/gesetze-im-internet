from __future__ import annotations

"""Deterministischer XML-Ingest für Normen und Raw-Spans."""

import ast
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from typing import Any, Iterable, Iterator, Mapping, Sequence
import re
import subprocess


def _resolve_repo_root(path: str) -> str:
    candidate = Path(path).resolve()
    for current in [candidate] + list(candidate.parents):
        if (current / ".git").exists() and current.is_dir():
            return str(current)

from .normalize import normalize_ws, sha256_text
from .span_ids import norm_id, paragraph_span_id, sentence_span_id


@dataclass(frozen=True)
class BookConfig:
    book_id: str
    aliases: tuple[str, ...]
    data_paths: tuple[str, ...]


def _normalize_alias(v: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", v.upper())


def _is_list_like(value: str) -> bool:
    return value.startswith("[") and value.endswith("]")


def _parse_simple_yaml_list(value: str) -> list[str]:
    try:
        parsed = ast.literal_eval(value)
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"cannot parse list value: {value}") from exc
    if not isinstance(parsed, list):
        raise ValueError(f"list value expected: {value}")
    return [str(v) for v in parsed]


def load_books_config(path: str) -> list[BookConfig]:
    """Parse the tiny config format in `sgb_books.yaml`."""

    cfg = Path(path)
    if not cfg.exists():
        raise FileNotFoundError(f"config not found: {path}")

    current: dict[str, Any] = {}
    out: list[dict[str, Any]] = []

    for raw_line in cfg.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "books:":
            continue
        if line.startswith("- book_id:"):
            if current:
                out.append(current)
            current = {}
            current["book_id"] = line.split(":", 1)[1].strip()
            continue

        if ":" in line and current is not None:
            key, val = [part.strip() for part in line.split(":", 1)]
            if _is_list_like(val):
                current[key] = _parse_simple_yaml_list(val)
            else:
                current[key] = val.strip('"')

    if current:
        out.append(current)

    books: list[BookConfig] = []
    for entry in out:
        book_id = entry["book_id"]
        aliases = tuple(str(v) for v in entry.get("aliases", []))
        data_paths = tuple(str(v) for v in entry.get("data_paths", []))
        books.append(BookConfig(book_id=book_id, aliases=aliases, data_paths=data_paths))

    return books


def _book_lookup(books: Sequence[BookConfig]) -> tuple[dict[str, str], list[str]]:
    alias_to_book: dict[str, str] = {}
    for b in books:
        alias_to_book[_normalize_alias(b.book_id)] = b.book_id
        for a in b.aliases:
            alias_to_book[_normalize_alias(a)] = b.book_id
    return alias_to_book, [b.book_id for b in books]


def _run_git_command(repo: str, args: Sequence[str]) -> str:
    resolved_repo = _resolve_repo_root(repo)
    completed = subprocess.run(
        ["git", "-C", resolved_repo] + list(args),
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def _safe_local_name(text: str) -> str:
    return text.split("}")[-1]


def _find_first_text(node: ET.Element, *tags: str) -> str:
    for tag in tags:
        for child in node:
            if _safe_local_name(child.tag) == tag:
                return "".join(child.itertext()).strip()
    for found in node.iter():
        if _safe_local_name(found.tag) in tags:
            if found is not node:
                return "".join(found.itertext()).strip()
    return ""


def _extract_jurabk_aliases(norm_node: ET.Element) -> list[str]:
    aliases: list[str] = []
    for node in norm_node.iter():
        if _safe_local_name(node.tag) != "jurabk":
            continue
        text = "".join(node.itertext()).strip()
        if text:
            aliases.append(text)
    return aliases


# -----------------------------------------------------------
#  Juristischer Satzsplitter
# -----------------------------------------------------------

# Menge bekannter Abkürzungen, die einen Punkt enthalten dürfen,
# ohne dass dieser als Satzende interpretiert wird.
#
# Enthält sowohl kurze Token ("Abs", "Nr", ...) als auch
# mehrteilige Punktabkürzungen ("i.V.m", "i.S.d", ...).
# Beim Splitting wird das Wort VOR dem Punkt extrahiert und
# gegen diese Menge geprüft.
#
# ERWEITERBAR: Neue Abkürzungen einfach zum frozen set hinzufügen.
_LEGAL_ABBREVIATIONS: frozenset[str] = frozenset({
    # ── Einfache Abkürzungen ──
    "Abs", "Nr", "Art", "Buchst", "lit", "Halbs", "Alt", "Var",
    "Absatz", "Abschnitt",
    # ── Satz-/Randnummer-ähnlich ──
    "S", "Rn", "ff", "f",
    # ── Mehrteilige Punktabkürzungen (ohne den finalen Punkt) ──
    # Das Wort vor dem Punkt lautet dann z. B. "i.V.m", "a.F", …
    "i.V.m", "i.S.d", "i.S.v", "e.V", "a.F", "n.F",
    "m.W.v", "m.w.N",
})


def _norm_unit_sentences(text: str) -> list[str]:
    """Split text into sentences while ignoring legal abbreviations.

    Splits ONLY at ``. `` / ``! `` / ``? `` when the word immediately
    before the punctuation is NOT a known legal abbreviation.

    >>> _norm_unit_sentences("gemäß § 23 Abs. 1 Satz 1 gilt.")
    ['gemäß § 23 Abs. 1 Satz 1 gilt.']
    >>> _norm_unit_sentences("Satz 1 gilt. Satz 2 gilt.")
    ['Satz 1 gilt.', 'Satz 2 gilt.']
    """
    if not text:
        return []

    out: list[str] = []
    last_end = 0

    for m in re.finditer(r"(?<=[\.\?\!])\s+", text):
        space_pos = m.start()  # position where whitespace begins
        if space_pos == 0:
            continue

        # ── Extrahiere das Wort VOR dem Satzzeichen ──
        # Das Satzzeichen (., ?, !) steht unmittelbar vor dem Whitespace.
        punct_pos = space_pos - 1  # position of . / ? / !

        # Walk backward from punct_pos to find the start of the word
        word_start = punct_pos
        while word_start > 0 and not text[word_start - 1].isspace():
            word_start -= 1

        # Wort zwischen word_start und punct_pos
        # (enthält KEINE Satzzeichen mehr, nur Buchstaben/Ziffern)
        word_before = text[word_start:punct_pos]

        if word_before in _LEGAL_ABBREVIATIONS:
            # Abkürzung erkannt – nicht splitten
            continue

        # Kein Abkürzungsschutz → Satzende, splitten
        piece = text[last_end:space_pos].strip()
        if piece:
            out.append(piece)
        last_end = m.end()

    # Rest anfügen
    piece = text[last_end:].strip()
    if piece:
        out.append(piece)

    if not out:
        out = [text]
    return out


def _guess_book_id(
    jurabk_aliases: Sequence[str],
    source_path: str,
    books: Sequence[BookConfig],
    alias_to_book: Mapping[str, str],
) -> str:
    for alias in jurabk_aliases:
        key = _normalize_alias(alias)
        if key in alias_to_book:
            return alias_to_book[key]

    sp = source_path.replace("\\", "/")
    for book in books:
        for data_path in book.data_paths:
            if sp.startswith(data_path.rstrip("/")) or data_path.rstrip("/") in sp:
                return book.book_id
    raise ValueError(f"Cannot map book from jurabk={jurabk_aliases} and path={source_path}")


def _iter_norm_nodes(xml_text: str) -> Iterator[ET.Element]:
    text = xml_text.strip()
    if not text:
        return iter(())

    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        text_no_decl = re.sub(r"<\?xml[^>]*\?>", "", text).strip()
        try:
            root = ET.fromstring(f"<root>{text_no_decl}</root>")
        except ET.ParseError:
            # Let the caller show a useful error.
            raise

    for node in root.iter():
        if _safe_local_name(node.tag) == "norm":
            yield node


def _read_fixture_files(path: str) -> list[tuple[str, str]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"fixture path does not exist: {path}")

    files: list[Path] = []
    if p.is_file():
        if p.suffix.lower() != ".xml":
            raise ValueError(f"fixture must be XML: {path}")
        files = [p]
    else:
        files = sorted([f for f in p.rglob("*.xml") if f.is_file()])

    out = []
    for file in files:
        out.append((str(file.as_posix()), file.read_text(encoding="utf-8")))
    return out


def _read_data_files(repo: str, data_ref: str, books: Sequence[BookConfig]) -> list[tuple[str, str]]:
    prefixes = sorted({path for b in books for path in b.data_paths if path})
    if not prefixes:
        raise ValueError("config has no data_paths")

    paths: list[str] = []
    for prefix in prefixes:
        out = _run_git_command(repo, ["ls-tree", "-r", "--name-only", data_ref, prefix])
        for path in out.splitlines():
            p = path.strip()
            if p and p.endswith(".xml"):
                paths.append(p)

    files = []
    for p in sorted(set(paths)):
        content = _run_git_command(repo, ["show", f"{data_ref}:{p}"])
        files.append((p, content))
    return files


def _build_norm_records(
    xml_text: str,
    source_path: str,
    books: Sequence[BookConfig],
    alias_to_book: Mapping[str, str],
    source_commit: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    norms: list[dict[str, Any]] = []
    spans: list[dict[str, Any]] = []
    found_books: set[str] = set()

    for norm_node in _iter_norm_nodes(xml_text):
        paragraph = _find_first_text(norm_node, "enbez")
        if not paragraph:
            continue
        heading = _find_first_text(norm_node, "titel")
        paragraph = normalize_ws(paragraph)

        jurabk = _extract_jurabk_aliases(norm_node)
        book_id = _guess_book_id(jurabk, source_path, books, alias_to_book)
        found_books.add(book_id)

        normalized_par = re.sub(r"^\s*", "", paragraph)
        normalized_par = re.sub(r"\s+", "", normalized_par)
        # ensure canonical shape: handle § and Art. explicitly
        normalized_par = norm_id(book_id, paragraph).split(":", 1)[1]
        n_id = norm_id(book_id, paragraph)

        paragraph_spans: list[str] = []

        abs_no = 0
        for p_node in norm_node.iter():
            if _safe_local_name(p_node.tag).upper() != "P":
                continue
            abs_no += 1
            paragraph_text = normalize_ws("".join(p_node.itertext()))
            if not paragraph_text:
                continue

            p_span_id = paragraph_span_id(n_id, abs_no)
            paragraph_spans.append(p_span_id)
            spans.append(
                {
                    "span_id": p_span_id,
                    "book_id": book_id,
                    "norm_id": n_id,
                    "paragraph": normalized_par,
                    "heading": heading,
                    "unit_type": "paragraph",
                    "path": [f"Abs. {abs_no}"],
                    "ordinal": abs_no,
                    "text": paragraph_text,
                    "text_hash": sha256_text(paragraph_text),
                    "source_commit": source_commit,
                }
            )

            sentences = _norm_unit_sentences(paragraph_text)
            for sent_no, sentence in enumerate(sentences, start=1):
                s_id = sentence_span_id(n_id, abs_no, sent_no)
                paragraph_spans.append(s_id)
                spans.append(
                    {
                        "span_id": s_id,
                        "book_id": book_id,
                        "norm_id": n_id,
                        "paragraph": normalized_par,
                        "heading": heading,
                        "unit_type": "sentence",
                        "path": [f"Abs. {abs_no}", f"Satz {sent_no}"],
                        "ordinal": sent_no,
                        "text": sentence,
                        "text_hash": sha256_text(sentence),
                        "source_commit": source_commit,
                    }
                )

        if not paragraph_spans:
            continue

        norm_text = " ".join(
            normalize_ws(span["text"]) for span in spans if span["norm_id"] == n_id and span["unit_type"] == "paragraph"
        )
        norms.append(
            {
                "norm_id": n_id,
                "book_id": book_id,
                "paragraph": normalized_par,
                "heading": heading,
                "span_ids": paragraph_spans,
                "norm_text_hash": sha256_text(norm_text),
                "source_commit": source_commit,
            }
        )

    return norms, spans, found_books


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            json.dump(row, handle, ensure_ascii=False)
            handle.write("\n")


def _write_source_json(path: Path, source_commit: str, books: Iterable[str], branch: str) -> None:
    payload = {
        "source_repo": "this-repository",
        "source_branch": branch,
        "source_commit": source_commit,
        "built_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope": sorted(list(books)),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_books_jsonl(path: Path, found_books: Iterable[str], source_commit: str, books: Sequence[BookConfig]) -> None:
    known = {b.book_id: b for b in books}
    out: list[dict[str, Any]] = []
    for book_id in sorted(found_books):
        book = known[book_id]
        out.append(
            {
                "book_id": book.book_id,
                "title": book.book_id,
                "aliases": list(book.aliases),
                "data_paths": list(book.data_paths),
                "source_commit": source_commit,
            }
        )
    _write_jsonl(path, out)


def _dedupe_norm_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep first occurrence for duplicate norm_ids.

    Input rows are expected to be sorted deterministically before deduplication.
    """
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        norm_id_value = row["norm_id"]
        if norm_id_value in best:
            continue
        best[norm_id_value] = row

    return [best[key] for key in sorted(best.keys())]


def _dedupe_span_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        span_id_value = row["span_id"]
        if span_id_value in seen:
            continue
        seen.add(span_id_value)
        out.append(row)
    return out


def _run_ingest(
    source_items: list[tuple[str, str]],
    books: list[BookConfig],
    source_commit: str,
    source_branch: str,
    out_dir: Path,
    scope_filter: Sequence[str] | None = None,
) -> tuple[Path, Path, Path, Path]:
    alias_to_book, _ = _book_lookup(books)

    all_norms: list[dict[str, Any]] = []
    all_spans: list[dict[str, Any]] = []
    found_books: set[str] = set()

    if scope_filter:
        requested = {b.upper() for b in scope_filter}
        books = [b for b in books if b.book_id.upper() in requested]

    for source_path, xml_text in source_items:
        norms, spans, found = _build_norm_records(
            xml_text,
            source_path,
            books,
            alias_to_book,
            source_commit,
        )
        all_norms.extend(norms)
        all_spans.extend(spans)
        found_books.update(found)

    all_norms.sort(key=lambda row: (row["norm_id"], row.get("norm_text_hash", "")))
    all_spans.sort(key=lambda row: (row["norm_id"], row["ordinal"], row["unit_type"], row["span_id"]))

    all_norms = _dedupe_norm_records(all_norms)
    kept_span_ids = {sid for n in all_norms for sid in n.get("span_ids", [])}
    all_spans = [row for row in all_spans if row["span_id"] in kept_span_ids]
    all_spans = _dedupe_span_records(all_spans)

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_source_json(out_dir / "source.json", source_commit, found_books, source_branch)
    _write_books_jsonl(out_dir / "books.jsonl", found_books, source_commit, books)
    _write_jsonl(out_dir / "norms.jsonl", all_norms)
    _write_jsonl(out_dir / "raw_spans.jsonl", all_spans)

    return (
        out_dir / "source.json",
        out_dir / "books.jsonl",
        out_dir / "norms.jsonl",
        out_dir / "raw_spans.jsonl",
    )


def ingest_from_fixture(
    fixture: str,
    out_dir: str,
    config_path: str = "config/sgb_books.yaml",
    repo: str = ".",
    books: Sequence[str] | None = None,
) -> dict[str, str]:
    """Ingest from fixture files (path to file or directory)."""
    cfg_books = load_books_config(Path(repo) / config_path)
    source_items = _read_fixture_files(fixture)
    if not source_items:
        raise ValueError("No XML content to ingest")
    source_commit = "fixture"
    out_path = Path(out_dir)
    output_files = _run_ingest(source_items, cfg_books, source_commit, "fixture", out_path, scope_filter=books)
    return {"source": str(output_files[0]), "books": str(output_files[1]), "norms": str(output_files[2]), "spans": str(output_files[3])}


def ingest_from_data_branch(
    repo: str,
    data_ref: str,
    out_dir: str,
    config_path: str = "config/sgb_books.yaml",
    books: Sequence[str] | None = None,
) -> dict[str, str]:
    """Ingest configured books from `data_ref` in the local repo."""
    cfg_books = load_books_config(Path(repo) / config_path)
    source_commit = _run_git_command(repo, ["rev-parse", data_ref]).strip()

    active_books: list[BookConfig]
    if books:
        requested = {b.upper() for b in books}
        active_books = [book for book in cfg_books if book.book_id.upper() in requested]
    else:
        active_books = cfg_books

    if not active_books:
        raise ValueError("No books selected; check --books filter")

    source_items = _read_data_files(repo, data_ref, active_books)
    if not source_items:
        raise ValueError(f"No XML files found for data_ref={data_ref}")

    out_path = Path(out_dir)
    output_files = _run_ingest(source_items, active_books, source_commit, data_ref, out_path, scope_filter=books)
    return {"source": str(output_files[0]), "books": str(output_files[1]), "norms": str(output_files[2]), "spans": str(output_files[3])}


__all__ = [
    "BookConfig",
    "load_books_config",
    "ingest_from_fixture",
    "ingest_from_data_branch",
]
