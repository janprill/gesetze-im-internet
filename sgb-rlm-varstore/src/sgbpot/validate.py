from __future__ import annotations

"""Validator für Varstore-Artefakte."""

import json
from pathlib import Path
from typing import Any, Iterable

from .normalize import sha256_text


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"unparseable JSONL line in {path}: {line}") from exc


def _validate_required_source(row: dict[str, Any], errors: list[str], file_name: str) -> None:
    if not row.get("source_commit"):
        errors.append(f"{file_name}: source_commit missing or empty")


def _evidence_ids_present(evidence: Any) -> list[str]:
    if not isinstance(evidence, list):
        return []
    return [x for x in evidence if isinstance(x, str)]


def validate(varstore_path: str) -> tuple[bool, list[str]]:
    root = Path(varstore_path)
    if not root.exists():
        return False, [f"varstore not found: {varstore_path}"]

    errors: list[str] = []

    source_path = root / "source.json"
    if not source_path.exists():
        return False, ["missing source.json"]

    try:
        source = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"invalid source.json: {exc}"]

    source_commit = source.get("source_commit", "")
    if not source_commit:
        errors.append("source.json: source_commit missing or empty")

    norms_path = root / "norms.jsonl"
    spans_path = root / "raw_spans.jsonl"
    cards_path = root / "cards"
    topics_path = root / "topics.jsonl"

    if not norms_path.exists():
        errors.append("missing norms.jsonl")
        return False, errors
    if not spans_path.exists():
        errors.append("missing raw_spans.jsonl")
        return False, errors

    spans: list[dict[str, Any]] = []
    span_ids: set[str] = set()
    try:
        span_rows = list(_iter_jsonl(spans_path))
    except ValueError as exc:
        return False, [str(exc)]

    for row in span_rows:
        _validate_required_source(row, errors, "raw_spans.jsonl")
        sid = row.get("span_id")
        if not isinstance(sid, str) or not sid:
            errors.append("raw_spans.jsonl: span_id missing or not a string")
            continue
        if sid in span_ids:
            errors.append(f"raw_spans.jsonl: duplicate span_id {sid}")
        span_ids.add(sid)

        expected = sha256_text(row.get("text", ""))
        if expected != row.get("text_hash", ""):
            errors.append(f"raw_spans.jsonl: wrong text_hash for {sid}")
        spans.append(row)

    norm_ids: set[str] = set()
    try:
        norm_rows = list(_iter_jsonl(norms_path))
    except ValueError as exc:
        return False, [str(exc)]

    for row in norm_rows:
        _validate_required_source(row, errors, "norms.jsonl")
        nid = row.get("norm_id")
        if not isinstance(nid, str) or not nid:
            errors.append("norms.jsonl: norm_id missing or not a string")
            continue
        if row.get("norm_id") in norm_ids:
            errors.append(f"norms.jsonl: duplicate norm_id {nid}")
        norm_ids.add(nid)

        # Norm referenziert Spans
        norm_span_ids = row.get("span_ids")
        if not isinstance(norm_span_ids, list):
            errors.append(f"norms.jsonl: span_ids missing for {nid}")
            continue
        missing = [sid for sid in norm_span_ids if sid not in span_ids]
        if missing:
            errors.append(f"norm {nid}: unknown span_ids {missing[:3]}")

        if row.get("norm_text_hash"):
            paragraph_text = " ".join(
                s["text"]
                for s in spans
                if s.get("norm_id") == nid and s.get("unit_type") == "paragraph"
            )
            if row["norm_text_hash"] != sha256_text(paragraph_text):
                errors.append(f"norm {nid}: norm_text_hash mismatch")

    # Cards
    card_count = 0
    if cards_path.exists():
        for card_file in sorted((root / "cards").glob("*.jsonl")):
            try:
                card_rows = list(_iter_jsonl(card_file))
            except ValueError as exc:
                return False, [str(exc)]
            for row in card_rows:
                card_count += 1

                if row.get("norm_id") not in norm_ids:
                    errors.append(f"card {row.get('card_id')}: references missing norm {row.get('norm_id')}")

                if not isinstance(row.get("one_sentence"), str) or not row.get("one_sentence", "").strip():
                    errors.append(f"card {row.get('card_id')}: one_sentence empty")

                def _check_bucket(bucket_name: str) -> None:
                    for idx, item in enumerate(row.get(bucket_name, []) or []):
                        if not isinstance(item, dict):
                            errors.append(f"card {row.get('card_id')}: {bucket_name}[{idx}] must be object")
                            continue
                        evidence = _evidence_ids_present(item.get("evidence"))
                        has_payload = any(
                            isinstance(v, str)
                            for k, v in item.items()
                            if k != "evidence" and v
                        )
                        if has_payload and not evidence:
                            errors.append(f"card {row.get('card_id')}: {bucket_name}[{idx}] has content without evidence")
                        for evidence_id in evidence:
                            if evidence_id not in span_ids:
                                errors.append(
                                    f"card {row.get('card_id')}: {bucket_name}[{idx}] references unknown evidence {evidence_id}"
                                )

                _check_bucket("roles")
                _check_bucket("actors")
                _check_bucket("legal_effects")
                _check_bucket("conditions")
                _check_bucket("exceptions_or_limits")

    if card_count == 0:
        errors.append("no cards found; run compile-cards --dry-run")

    if topics_path.exists():
        try:
            topic_rows = list(_iter_jsonl(topics_path))
        except ValueError as exc:
            return False, [str(exc)]

        for row in topic_rows:
            for key in ("core_norms", "related_norms"):
                values = row.get(key) or []
                if not isinstance(values, list):
                    continue
                for norm_id_ref in values:
                    if norm_id_ref not in norm_ids:
                        errors.append(f"topic {row.get('topic_id')}: unknown {key[:-1]} {norm_id_ref}")

    if errors:
        return False, errors
    return True, ["validation passed"]


def _print_errors(errors: list[str]) -> None:
    for err in errors:
        print(f"ERROR: {err}")


def run_validate(varstore_path: str) -> int:
    ok, messages = validate(varstore_path)
    if ok:
        for message in messages:
            print(message)
        return 0
    _print_errors(messages)
    return 1


__all__ = ["validate", "run_validate"]
