from __future__ import annotations

"""Lazy-Objekte für den Zugriff auf den lokalen Varstore."""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .build_index import search_spans


class MissingVarstoreError(RuntimeError):
    pass


class SGBMemory:
    def __init__(self, varstore_path: str = "varstore", scope: str | None = None) -> None:
        self.varstore_path = Path(varstore_path)
        self.scope = scope
        self._loaded = False
        self._source: dict[str, Any] = {}
        self._norms: dict[str, dict[str, Any]] = {}
        self._spans: dict[str, list[dict[str, Any]]] = {}
        self._cards: dict[str, dict[str, Any]] = {}
        self._topics_by_label: dict[str, dict[str, Any]] = {}
        self._topics_by_norm: dict[str, list[dict[str, Any]]] = {}
        self._books: list[str] = []
        self._conn: sqlite3.Connection | None = None
        self._cards_collection = _CardCollection(self)
        self._topics_collection = _TopicCollection(self)

        from .packer import Packer

        self._packer = Packer(self)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return

        path = self.varstore_path
        if not path.exists():
            raise MissingVarstoreError(
                "Varstore not found. Run: python -m sgbpot.cli ingest ..."
            )
        source_path = path / "source.json"
        if not source_path.exists():
            raise MissingVarstoreError(
                "Varstore incomplete. Run: python -m sgbpot.cli ingest ..."
            )

        self._source = json.loads(source_path.read_text(encoding="utf-8"))

        books_file = path / "books.jsonl"
        for row in _iter_jsonl(books_file):
            self._books.append(row["book_id"])

        norms_file = path / "norms.jsonl"
        for row in _iter_jsonl(norms_file):
            self._norms[row["norm_id"]] = row

        spans_file = path / "raw_spans.jsonl"
        for row in _iter_jsonl(spans_file):
            self._spans.setdefault(row["norm_id"], []).append(row)

        for spans in self._spans.values():
            spans.sort(key=lambda item: (item.get("unit_type"), item.get("ordinal", 0), item.get("span_id")))

        cards_root = path / "cards"
        if cards_root.exists():
            for card_file in sorted(cards_root.glob("*.jsonl")):
                for row in _iter_jsonl(card_file):
                    self._cards[row["norm_id"]] = row

        topics_path = path / "topics.jsonl"
        if topics_path.exists():
            for row in _iter_jsonl(topics_path):
                label = (row.get("label") or "").strip().lower()
                if label:
                    self._topics_by_label[label] = row
                for norm_id in row.get("core_norms", []) or []:
                    self._topics_by_norm.setdefault(norm_id, []).append(row)

        index_path = path / "index.sqlite"
        if index_path.exists():
            self._conn = sqlite3.connect(index_path)

        self._loaded = True

    @property
    def source_commit(self) -> str:
        self._ensure_loaded()
        return str(self._source.get("source_commit", ""))

    def _scoped_books(self) -> list[str]:
        books = self._books
        if self.scope is None:
            return books
        if self.scope.upper() == "SGB":
            return [b for b in books if b.startswith("SGB_")]
        if self.scope.upper() == "SGG":
            return [b for b in books if b.startswith("SGG")]
        return books

    def books(self) -> list[str]:
        self._ensure_loaded()
        return sorted(self._scoped_books())

    def norm(self, norm_id: str) -> "NormVar":
        self._ensure_loaded()
        if norm_id not in self._norms:
            raise KeyError(f"norm not found: {norm_id}")

        # Scope-Prüfung: wenn scope gesetzt ist, muss die Norm zum Scope passen
        if self.scope is not None:
            book_id = norm_id.split(":", 1)[0]
            if self.scope.upper() == "SGB" and not book_id.startswith("SGB_"):
                raise KeyError(
                    f"norm {norm_id} is out of scope '{self.scope}'. "
                    f"Scope 'SGB' only allows SGB_* books."
                )
            if self.scope.upper() == "SGG" and not book_id.startswith("SGG"):
                raise KeyError(
                    f"norm {norm_id} is out of scope '{self.scope}'. "
                    f"Scope 'SGG' only allows SGG books."
                )

        return NormVar(self, norm_id)

    def search(self, query: str, k: int = 20, unit_type: str | None = None) -> list[dict[str, Any]]:
        """Volltextsuche über Raw-Spans.

        Args:
            query: Suchbegriff(e)
            k: Maximale Anzahl Treffer
            unit_type: Optionaler Filter ("paragraph", "sentence", …).
                       Wenn gesetzt, werden nur Spans dieses Typs geliefert.
                       Default (None): alle unit_types (Rückwärtskompatibilität).

        Returns:
            Liste von Treffern, dedupliziert nach norm_id.
            Bei Duplikaten wird der Paragraph-Span bevorzugt.
        """
        self._ensure_loaded()
        if not query:
            return []

        scope_books = set(self._scoped_books())

        hits: list[dict[str, Any]]
        if self._conn is not None:
            # Hole mehr Treffer für Deduplizierung (2× k)
            hits = search_spans(self._conn, query, max(k * 2, 50))
        else:
            hits = []
            q = query.lower()
            for spans in self._spans.values():
                for span in spans:
                    if not scope_books or span.get("norm_id", "").split(":", 1)[0] in scope_books:
                        if q in span.get("text", "").lower():
                            hits.append({
                                "norm_id": span["norm_id"],
                                "text": span.get("text", ""),
                                "unit_type": span.get("unit_type", ""),
                                "span_id": span["span_id"],
                            })

        # Scope-Filter
        if scope_books:
            hits = [h for h in hits if h.get("norm_id", "").split(":", 1)[0] in scope_books]

        # Optional: unit_type-Filter
        if unit_type:
            hits = [h for h in hits if h.get("unit_type") == unit_type]

        # Dedupliziere nach norm_id, bevorzuge Paragraph-Spans
        deduped: dict[str, dict[str, Any]] = {}
        for hit in hits:
            nid = hit["norm_id"]
            if nid not in deduped:
                deduped[nid] = hit
            else:
                # Behalte den Paragraph-Treffer, wenn der vorhandene kein Paragraph ist
                existing = deduped[nid]
                if hit.get("unit_type") == "paragraph" and existing.get("unit_type") != "paragraph":
                    deduped[nid] = hit

        return list(deduped.values())[:k]

    def topic(self, label: str) -> "TopicVar":
        self._ensure_loaded()
        return self._topics_collection[label]

    @property
    def cards(self) -> "_CardCollection":
        return self._cards_collection

    @property
    def topics(self) -> "_TopicCollection":
        return self._topics_collection

    @property
    def topics_by_norm(self) -> dict[str, list[dict[str, Any]]]:
        self._ensure_loaded()
        return self._topics_by_norm

    @property
    def index(self) -> "IndexAccessor":
        return IndexAccessor(self)

    @property
    def packer(self) -> "Packer":
        return self._packer

    @property
    def trace(self) -> "_TraceAccessor":
        return _TraceAccessor(self.varstore_path)


@dataclass
class NormVar:
    memory: SGBMemory
    norm_id: str

    def _record(self) -> dict[str, Any]:
        self.memory._ensure_loaded()
        return self.memory._norms[self.norm_id]

    @property
    def heading(self) -> str:
        return self._record().get("heading", "")

    def text(self) -> str:
        self.memory._ensure_loaded()
        spans = self.memory._spans.get(self.norm_id, [])
        paragraphs = [s["text"] for s in spans if s.get("unit_type") == "paragraph"]
        return "\n".join(paragraphs)

    def spans(self) -> list[dict[str, Any]]:
        self.memory._ensure_loaded()
        return list(self.memory._spans.get(self.norm_id, []))

    def card(self) -> dict[str, Any] | None:
        self.memory._ensure_loaded()
        return self.memory._cards.get(self.norm_id)

    def neighbors(self) -> list[str]:
        self.memory._ensure_loaded()
        record = self._record()
        book_id = record["book_id"]

        sibling_ids = [
            n_id for n_id in self.memory._norms if self.memory._norms[n_id].get("book_id") == book_id
        ]
        sibling_ids.sort()
        try:
            pos = sibling_ids.index(self.norm_id)
        except ValueError:
            return []

        out: list[str] = []
        if pos > 0:
            out.append(sibling_ids[pos - 1])
        if pos + 1 < len(sibling_ids):
            out.append(sibling_ids[pos + 1])
        return out


@dataclass
class TopicVar:
    memory: SGBMemory
    topic: dict[str, Any]

    def core_norms(self) -> list[str]:
        return list(self.topic.get("core_norms", []))

    def related_norms(self) -> list[str]:
        return list(self.topic.get("related_norms", []))

    def cards(self) -> list[dict[str, Any]]:
        cards = []
        for norm_id in self.core_norms():
            self.memory._ensure_loaded()
            card = self.memory._cards.get(norm_id)
            if card:
                cards.append(card)
        return cards

    def pack(self) -> str:
        ids = self.core_norms()
        return self.memory.packer.norms(ids, include_cards=True, include_topics=False)


class _CardCollection:
    def __init__(self, memory: SGBMemory) -> None:
        self.memory = memory

    def __call__(self, norm_id: str) -> dict[str, Any] | None:
        self.memory._ensure_loaded()
        return self.memory._cards.get(norm_id)

    def __getitem__(self, norm_id: str) -> dict[str, Any] | None:
        return self.__call__(norm_id)


class _TopicCollection:
    def __init__(self, memory: SGBMemory) -> None:
        self.memory = memory

    def __call__(self, label: str) -> TopicVar:
        return self.__getitem__(label)

    def __getitem__(self, label: str) -> TopicVar:
        self.memory._ensure_loaded()
        key = (label or "").strip().lower()
        topic = self.memory._topics_by_label.get(key)
        if topic is None:
            raise KeyError(f"topic not found: {label}")
        return TopicVar(self.memory, topic)


class IndexAccessor:
    def __init__(self, memory: SGBMemory) -> None:
        self.memory = memory

    def search(self, query: str, k: int = 20) -> list[dict[str, Any]]:
        return self.memory.search(query, k)


class _TraceAccessor:
    def __init__(self, varstore_path: Path) -> None:
        self.varstore_path = varstore_path

    @property
    def all(self) -> list[Any]:
        from .trace import read_traces

        return read_traces(str(self.varstore_path))


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


__all__ = [
    "SGBMemory",
    "NormVar",
    "TopicVar",
    "MissingVarstoreError",
]
