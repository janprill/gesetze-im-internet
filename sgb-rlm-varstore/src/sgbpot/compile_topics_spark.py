from __future__ import annotations

"""Topic-Compiler für den Proof-Pfad.

Es werden deterministische, minimale Topics aus vorhandenen Cards erzeugt
und semantisch gruppiert.
"""

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .trace import new_trace, write_trace


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def _load_all_cards(varstore_path: Path) -> list[dict[str, Any]]:
    cards_dir = varstore_path / "cards"
    if not cards_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(cards_dir.glob("*.jsonl")):
        rows.extend(_iter_jsonl(path))
    return rows


def _topic_id(label: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", label.strip())
    if not safe:
        safe = "topic"
    return f"TOPIC:{safe}"


# ── Semantische Gruppierung ───────────────────────────────────────────────────

_WORD_RE = re.compile(r"[a-zäöüß]+(?:_[a-zäöüß]+)*")

# Deutsche Stoppwörter, die für Topic-Ähnlichkeit ignoriert werden.
_STOP_WORDS: frozenset[str] = frozenset({
    "der", "die", "das", "des", "dem", "den",
    "und", "oder", "von", "vom", "für", "mit", "bei", "auf",
    "im", "am", "an", "in", "zu", "zur", "zum", "ist", "sind",
    "ein", "eine", "einer", "eines", "einem", "einen",
    "sowie", "auch", "nur", "nach", "vor", "über", "unter",
    "durch", "bis", "als", "wie", "wird", "werden",
    "nicht", "kein", "keine", "wenn", "dann",
})


def _tokenize(text: str) -> set[str]:
    """Extrahiere relevante Wortstämme aus einem Topic-Label / Heading."""
    words = _WORD_RE.findall(text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 1}


def _card_topic_tags(card: dict[str, Any]) -> set[str]:
    """Sammle Topic-Tags aus der Card (heading + topic_tags)."""
    tags: set[str] = set()
    heading = card.get("heading", "")
    if heading:
        tags.update(_tokenize(heading))
    for tag in card.get("topic_tags", []) or []:
        tags.update(_tokenize(str(tag)))
    return tags


def _group_topics(
    raw_topics: list[dict[str, Any]],
    cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Gruppiere Topics semantisch.

    Zwei Topics werden zusammengeführt, wenn:
    - sie mindestens ein tokenisiertes topic_tag teilen UND
    - sie denselben book_scope haben.

    Einzelne Normen ohne thematische Verwandte bleiben Einzeltopics.
    """
    if not raw_topics:
        return []

    # Mapping: card norm_id → card index für schnellen Lookup
    card_by_norm: dict[str, dict[str, Any]] = {}
    for card in cards:
        nid = card.get("norm_id")
        if nid:
            card_by_norm[nid] = card

    # Extrahiere Tags pro Topic
    topic_tags: list[set[str]] = []
    for topic in raw_topics:
        norm_ids = topic.get("core_norms", [])
        all_tags: set[str] = set()
        for nid in norm_ids:
            card = card_by_norm.get(nid)
            if card:
                all_tags.update(_card_topic_tags(card))
        # Fallback: tokenisiere das Label
        if not all_tags:
            all_tags = _tokenize(topic.get("label", ""))
        topic_tags.append(all_tags)

    # Union-Find: Gruppiere Topics mit überlappenden Tags UND gleichem book_scope
    n = len(raw_topics)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        scope_i = frozenset(raw_topics[i].get("book_scope", []))
        for j in range(i + 1, n):
            scope_j = frozenset(raw_topics[j].get("book_scope", []))
            # Gleicher book_scope UND überlappende Tags
            if scope_i and scope_j and scope_i == scope_j:
                if topic_tags[i] & topic_tags[j]:
                    union(i, j)

    # Gruppiere nach Wurzel
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    # Baue zusammengeführte Topics
    result: list[dict[str, Any]] = []
    for indices in groups.values():
        group_topics = [raw_topics[i] for i in indices]

        all_norms: list[str] = []
        all_scopes: set[str] = set()
        all_labels: list[str] = []
        all_evidence: list[str] = []
        all_questions: list[str] = []

        for t in group_topics:
            for nid in t.get("core_norms", []):
                if nid and nid not in all_norms:
                    all_norms.append(nid)
            all_scopes.update(t.get("book_scope", []))
            all_labels.append(t.get("label", ""))
            all_evidence.extend(t.get("evidence", []) or [])
            all_questions.extend(t.get("likely_questions", []) or [])

        # Häufigstes Label als Topic-Namen
        label_counter = Counter(l for l in all_labels if l)
        label = label_counter.most_common(1)[0][0] if label_counter else "Allgemein"

        # Beschreibung generieren
        norms_sorted = sorted(set(all_norms))
        if len(norms_sorted) == 1:
            description = f"Normen zur '{label}'."
        elif len(norms_sorted) <= 5:
            description = f"{len(norms_sorted)} Normen zur '{label}': {', '.join(norms_sorted)}."
        else:
            description = (
                f"{len(norms_sorted)} Normen zur '{label}': "
                f"{', '.join(norms_sorted[:5])} und "
                f"{len(norms_sorted) - 5} weitere."
            )

        result.append({
            "topic_id": _topic_id(label),
            "label": label,
            "description": description,
            "core_norms": norms_sorted,
            "related_norms": [],
            "book_scope": sorted(all_scopes),
            "likely_questions": all_questions[:5],
            "pitfalls": [],
            "evidence": list(dict.fromkeys(all_evidence))[:10],  # dedup, limit
            "compiler": group_topics[0].get("compiler", {}),
        })

    # Sortiere deterministisch
    result.sort(key=lambda t: t["topic_id"])
    return result


# ── Hauptfunktion ─────────────────────────────────────────────────────────────


def compile_topics(varstore_path: str, dry_run: bool = True, prompt_version: str = "topic-v0.1", model: str = "dry-run", group: bool = True) -> Path:
    varstore = Path(varstore_path)
    if not varstore.exists():
        raise FileNotFoundError(f"varstore not found: {varstore_path}")

    cards = _load_all_cards(varstore)
    if not cards and not dry_run:
        raise RuntimeError("No cards available")

    # Phase 1: Initiale Topics (1 pro Card)
    topics: list[dict[str, Any]] = []
    for card in cards:
        heading = (card.get("heading") or "")
        label = heading.split(" — ")[0].strip() or card.get("norm_id", "") or "Allgemein"
        topics.append(
            {
                "topic_id": _topic_id(label),
                "label": label,
                "description": f"Normen, die sich auf '{label}' beziehen.",
                "core_norms": [card.get("norm_id")],
                "related_norms": [],
                "book_scope": [card.get("book_id")],
                "likely_questions": card.get("likely_questions", []),
                "pitfalls": [],
                "evidence": card.get("roles", [{}])[0].get("evidence", []) if card.get("roles") else [],
                "compiler": {
                    "model": "dry-run" if dry_run else model,
                    "prompt_version": prompt_version,
                    "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                },
            }
        )

    # Phase 2: Deduplizieren nach topic_id (gleiche Labels mergen)
    deduped: dict[str, dict[str, Any]] = {}
    for topic in topics:
        current = deduped.get(topic["topic_id"])
        if current is None:
            deduped[topic["topic_id"]] = topic
        else:
            current_norms = current.setdefault("core_norms", [])
            for value in topic["core_norms"]:
                if value and value not in current_norms:
                    current_norms.append(value)

    deduped_list = sorted(deduped.values(), key=lambda t: t["topic_id"])

    # Phase 3: Semantisch gruppieren
    if group:
        out = _group_topics(deduped_list, cards)
    else:
        out = deduped_list

    if not dry_run:
        if model in ("", None, "dry-run"):
            raise RuntimeError("Topic model mode requested without model key. Use --dry-run or provide model.")
        raise RuntimeError("Real topic model mode is intentionally not implemented in this proof path.")

    path = varstore / "topics.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for row in out:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    trace = new_trace(
        varstore_path=str(varstore),
        command="compile-topics",
        model="dry-run" if dry_run else model,
        prompt_version=prompt_version,
        output_path=str(path),
        validation_status="passed",
    )
    write_trace(str(varstore), trace)
    return path


__all__ = ["compile_topics", "_group_topics", "_card_topic_tags", "_tokenize"]
