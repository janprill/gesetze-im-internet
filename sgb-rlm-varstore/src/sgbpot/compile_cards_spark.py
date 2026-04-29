from __future__ import annotations

"""Compiler-Adapter für Norm-Karten.

Der produktive Modellpfad ist optional; der Dry-Run erzeugt deterministische
kleine Thin Cards, damit die Pipeline ohne LLM-Zugriff testbar bleibt.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence, Mapping

from .trace import new_trace, write_trace


@dataclass(frozen=True)
class CompileResult:
    output_path: Path
    count: int


def _iter_jsonl(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def _load_norms(varstore_path: Path):
    norms_path = varstore_path / "norms.jsonl"
    if not norms_path.exists():
        raise FileNotFoundError("norms.jsonl missing; run ingest first")
    return list(_iter_jsonl(norms_path))


def _load_spans_by_norm(varstore_path: Path) -> dict[str, list[dict[str, Any]]]:
    spans_by_norm: dict[str, list[dict[str, Any]]] = {}
    spans_path = varstore_path / "raw_spans.jsonl"
    if not spans_path.exists():
        return spans_by_norm
    for row in _iter_jsonl(spans_path):
        spans_by_norm.setdefault(row["norm_id"], []).append(row)
    return spans_by_norm


def _build_dry_run_card(norm: Mapping[str, Any], spans: list[dict[str, Any]]) -> dict[str, Any]:
    norm_id = norm["norm_id"]
    book_id = norm["book_id"]
    heading = norm.get("heading", "")
    evidence = [s["span_id"] for s in spans if s.get("unit_type") in ("sentence", "paragraph")][:1]
    return {
        "card_id": f"CARD:{norm_id}",
        "card_type": "thin",
        "norm_id": norm_id,
        "book_id": book_id,
        "heading": heading,
        "one_sentence": f"Navigationskarte zu {norm_id}: {heading}.".strip(),
        "roles": [{"role": "Norm", "evidence": evidence}] if evidence else [],
        "actors": [],
        "legal_effects": [],
        "conditions": [],
        "exceptions_or_limits": [],
        "topic_tags": [heading] if heading else [],
        "likely_questions": [f"Welche Bedeutung hat {norm_id}?"],
        "xref_candidates": [],
        "compiler": {
            "model": "dry-run",
            "prompt_version": "norm-card-v0.1",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    }


def _write_book_cards(varstore_path: Path, norms: list[dict[str, Any]], spans_by_norm: dict[str, list[dict[str, Any]]], books: Sequence[str] | None) -> int:
    cards_dir = varstore_path / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    by_book: dict[str, list[dict[str, Any]]] = {}
    for norm in norms:
        if books and norm["book_id"] not in books:
            continue
        by_book.setdefault(norm["book_id"], []).append(norm)

    for norms_for_book in by_book.values():
        norms_for_book.sort(key=lambda n: n["norm_id"])

    written = 0
    for book_id, entries in sorted(by_book.items()):
        path = cards_dir / f"{book_id}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for norm in entries:
                spans = spans_by_norm.get(norm["norm_id"], [])
                card = _build_dry_run_card(norm, spans)
                handle.write(json.dumps(card, ensure_ascii=False) + "\n")
                written += 1

    return written


def compile_cards(
    varstore_path: str,
    books: Sequence[str] | None = None,
    model: str = "dry-run",
    prompt_version: str = "norm-card-v0.1",
    dry_run: bool = True,
) -> CompileResult:
    if books and isinstance(books, str):
        books = [books]

    varstore = Path(varstore_path)
    norms = _load_norms(varstore)
    spans_by_norm = _load_spans_by_norm(varstore)

    if not dry_run:
        if model in ("", None, "dry-run"):
            raise RuntimeError("Model mode requested without model key. Use --dry-run or provide a configured model.")
        # Adapter-Stelle für echte API-Anbindung. Nicht implementiert, damit dieser Proof offline testbar bleibt.
        raise RuntimeError("Real model mode is intentionally not implemented in this proof path.")

    cards_dir = varstore / "cards"
    for path in cards_dir.glob("*.jsonl"):
        path.unlink()

    count = _write_book_cards(varstore, norms, spans_by_norm, books)

    trace = new_trace(
        varstore_path=varstore,
        command="compile-cards",
        model="dry-run",
        prompt_version=prompt_version,
        output_path=str(cards_dir / "cards.jsonl"),
        validation_status="passed",
    )
    write_trace(varstore, trace)
    return CompileResult(output_path=cards_dir, count=count)


__all__ = ["compile_cards", "CompileResult"]
