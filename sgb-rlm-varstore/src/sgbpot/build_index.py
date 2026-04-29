from __future__ import annotations

"""SQLite-Index-Build für deterministische Suche über JSONL-Artefakte."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


_JSONL_FILES = (
    "books.jsonl",
    "norms.jsonl",
    "raw_spans.jsonl",
)


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        yield json.loads(line)


def _detect_fts5(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(test)")
        conn.execute("DROP TABLE _fts5_probe")
        return True
    except sqlite3.OperationalError:
        return False


def _create_schema(conn: sqlite3.Connection, fts_available: bool) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS books;
        DROP TABLE IF EXISTS norms;
        DROP TABLE IF EXISTS spans;
        DROP TABLE IF EXISTS cards;
        DROP TABLE IF EXISTS topics;
        DROP TABLE IF EXISTS search_meta;
        """
    )

    conn.executescript(
        """
        CREATE TABLE books (
            book_id TEXT PRIMARY KEY,
            title TEXT,
            source_commit TEXT
        );

        CREATE TABLE norms (
            norm_id TEXT PRIMARY KEY,
            book_id TEXT,
            paragraph TEXT,
            heading TEXT,
            text_hash TEXT
        );

        CREATE TABLE spans (
            span_id TEXT PRIMARY KEY,
            norm_id TEXT,
            book_id TEXT,
            path_json TEXT,
            unit_type TEXT,
            text TEXT,
            heading TEXT,
            paragraph TEXT
        );

        CREATE TABLE cards (
            norm_id TEXT PRIMARY KEY,
            heading TEXT,
            one_sentence TEXT,
            roles_json TEXT,
            topics_json TEXT
        );

        CREATE TABLE topics (
            topic_id TEXT PRIMARY KEY,
            label TEXT,
            description TEXT,
            core_norms_json TEXT
        );

        CREATE TABLE search_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )

    if fts_available:
        conn.execute(
            "CREATE VIRTUAL TABLE spans_fts USING fts5(span_id, norm_id, book_id, heading, text, tokenize='porter')"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE cards_fts USING fts5(norm_id, heading, one_sentence, topic_tags, likely_questions, tokenize='porter')"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE topics_fts USING fts5(topic_id, label, description, likely_questions, tokenize='porter')"
        )
    else:
        conn.execute(
            "CREATE TABLE spans_fts (span_id TEXT, norm_id TEXT, book_id TEXT, heading TEXT, text TEXT)"
        )
        conn.execute(
            "CREATE TABLE cards_fts (norm_id TEXT, heading TEXT, one_sentence TEXT, topic_tags TEXT, likely_questions TEXT)"
        )
        conn.execute(
            "CREATE TABLE topics_fts (topic_id TEXT, label TEXT, description TEXT, likely_questions TEXT)"
        )

    conn.execute("CREATE INDEX IF NOT EXISTS idx_norms_book ON norms(book_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_norm ON spans(norm_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_book ON spans(book_id)")


def _insert_books(conn: sqlite3.Connection, books_file: Path) -> None:
    if not books_file.exists():
        return
    for row in _iter_jsonl(books_file):
        conn.execute(
            "INSERT INTO books (book_id, title, source_commit) VALUES (?, ?, ?)",
            (row["book_id"], row.get("title") or row["book_id"], row.get("source_commit", "")),
        )


def _insert_norms(conn: sqlite3.Connection, norms_file: Path) -> None:
    for row in _iter_jsonl(norms_file):
        conn.execute(
            "INSERT INTO norms (norm_id, book_id, paragraph, heading, text_hash) VALUES (?, ?, ?, ?, ?)",
            (row["norm_id"], row["book_id"], row.get("paragraph", ""), row.get("heading", ""), row.get("norm_text_hash", "")),
        )


def _insert_spans(conn: sqlite3.Connection, spans_file: Path) -> None:
    for row in _iter_jsonl(spans_file):
        conn.execute(
            "INSERT INTO spans (span_id, norm_id, book_id, path_json, unit_type, text, heading, paragraph) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row["span_id"],
                row["norm_id"],
                row["book_id"],
                json.dumps(row.get("path", []), ensure_ascii=False),
                row.get("unit_type", ""),
                row.get("text", ""),
                row.get("heading", ""),
                row.get("paragraph", ""),
            ),
        )
        conn.execute(
            "INSERT INTO spans_fts (span_id, norm_id, book_id, heading, text) VALUES (?, ?, ?, ?, ?)",
            (row["span_id"], row["norm_id"], row["book_id"], row.get("heading", ""), row.get("text", "")),
        )


def _iter_card_records(varstore_path: Path) -> Iterable[dict[str, Any]]:
    cards_dir = varstore_path / "cards"
    if not cards_dir.exists():
        return []
    for card_file in sorted(cards_dir.glob("*.jsonl")):
        for row in _iter_jsonl(card_file):
            yield row


def _insert_cards(conn: sqlite3.Connection, varstore_path: Path) -> None:
    for row in _iter_card_records(varstore_path):
        conn.execute(
            "INSERT OR REPLACE INTO cards (norm_id, heading, one_sentence, roles_json, topics_json) VALUES (?, ?, ?, ?, ?)",
            (
                row["norm_id"],
                row.get("heading", ""),
                row.get("one_sentence", ""),
                json.dumps(row.get("roles", []), ensure_ascii=False),
                json.dumps(row.get("topic_tags", []), ensure_ascii=False),
            ),
        )
        conn.execute(
            "INSERT INTO cards_fts (norm_id, heading, one_sentence, topic_tags, likely_questions) VALUES (?, ?, ?, ?, ?)",
            (
                row["norm_id"],
                row.get("heading", ""),
                row.get("one_sentence", ""),
                ",".join(row.get("topic_tags", [])),
                ",".join(row.get("likely_questions", [])),
            ),
        )


def _iter_topic_records(varstore_path: Path) -> Iterable[dict[str, Any]]:
    path = varstore_path / "topics.jsonl"
    if not path.exists():
        return []
    return list(_iter_jsonl(path))


def _insert_topics(conn: sqlite3.Connection, varstore_path: Path) -> None:
    for row in _iter_topic_records(varstore_path):
        conn.execute(
            "INSERT OR REPLACE INTO topics (topic_id, label, description, core_norms_json) VALUES (?, ?, ?, ?)",
            (row["topic_id"], row.get("label", ""), row.get("description", ""), json.dumps(row.get("core_norms", []), ensure_ascii=False)),
        )
        conn.execute(
            "INSERT INTO topics_fts (topic_id, label, description, likely_questions) VALUES (?, ?, ?, ?)",
            (row["topic_id"], row.get("label", ""), row.get("description", ""), ",".join(row.get("likely_questions", []))),
        )


def build_index(varstore_path: str) -> Path:
    root = Path(varstore_path)
    if not root.exists():
        raise FileNotFoundError(f"varstore not found: {varstore_path}")

    source = root / "source.json"
    if not source.exists():
        raise FileNotFoundError("missing source.json. Run ingest first")

    db_path = root / "index.sqlite"
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        fts_available = _detect_fts5(conn)
        _create_schema(conn, fts_available)

        conn.execute("INSERT INTO search_meta (key, value) VALUES (?, ?)", ("fts_enabled", str(int(fts_available)),))

        _insert_books(conn, root / "books.jsonl")
        _insert_norms(conn, root / "norms.jsonl")
        _insert_spans(conn, root / "raw_spans.jsonl")
        _insert_cards(conn, root)
        _insert_topics(conn, root)

        conn.commit()
    finally:
        conn.close()

    return db_path


def _fts5_escape(query: str) -> str:
    """Bereite einen Suchquery für FTS5 vor.

    - Ersetze Bindestriche durch Leerzeichen (FTS5 '-' ist NOT-Operator)
    - Bei Mehrwort-Queries: AND (alle Begriffe müssen vorkommen)
      für präzise juristische Recherche.
    - Einzelwort: direkt.
    - Schütze Anführungszeichen.
    """
    # Hyphen → space (verhindert FTS5-NOT-Operator)
    cleaned = query.replace("-", " ")
    words = cleaned.split()
    if not words:
        return query
    quoted = []
    for w in words:
        w = w.strip('"')
        if w:
            quoted.append(f'"{w}"')
    if len(quoted) == 1:
        return quoted[0]
    return " AND ".join(quoted)


def search_spans(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[dict]:
    meta = conn.execute("SELECT value FROM search_meta WHERE key='fts_enabled'").fetchone()
    fts_enabled = bool(int(meta[0])) if meta else False
    if fts_enabled:
        fts_query = _fts5_escape(query)
        rows = conn.execute(
            """
            SELECT s.norm_id, s.text, s.unit_type, s.span_id
            FROM (
                SELECT span_id, rank
                FROM spans_fts
                WHERE spans_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            ) f
            JOIN spans s ON s.span_id = f.span_id
            ORDER BY f.rank
            """,
            (fts_query, limit),
        ).fetchall()
        # Fallback: wenn AND zu wenige Treffer liefert, mit OR wiederholen
        if len(rows) < limit // 2:
            or_query = " OR ".join(_fts5_escape(query).split(" AND "))
            if or_query != fts_query:
                rows = conn.execute(
                    """
                    SELECT s.norm_id, s.text, s.unit_type, s.span_id
                    FROM (
                        SELECT span_id, rank
                        FROM spans_fts
                        WHERE spans_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                    ) f
                    JOIN spans s ON s.span_id = f.span_id
                    ORDER BY f.rank
                    """,
                    (or_query, limit),
                ).fetchall()
        return [dict(norm_id=r[0], text=r[1], unit_type=r[2], span_id=r[3]) for r in rows]

    pattern = f"%{query}%"
    rows = conn.execute(
        """
        SELECT norm_id, text, unit_type, span_id
        FROM spans
        WHERE text LIKE ?
        ORDER BY norm_id, span_id
        LIMIT ?
        """,
        (pattern, limit),
    ).fetchall()
    return [dict(norm_id=r[0], text=r[1], unit_type=r[2], span_id=r[3]) for r in rows]


__all__ = ["build_index", "search_spans"]
