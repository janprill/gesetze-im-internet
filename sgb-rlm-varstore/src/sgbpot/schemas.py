"""Dataclasses und Validierungsfunktionen für Varstore-Artefakte."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


class ValidationError(ValueError):
    """Raised when a varstore record is invalid."""


def _require_fields(data: Mapping[str, Any], fields: Iterable[str], what: str) -> None:
    for field in fields:
        if field not in data:
            raise ValidationError(f"{what} missing required field: {field}")


def _require_type(value: Any, expected: type, field: str, what: str) -> None:
    if not isinstance(value, expected):
        raise ValidationError(f"{what}.{field} must be {expected.__name__}, got {type(value).__name__}")


@dataclass(frozen=True)
class BookRecord:
    book_id: str
    title: str
    source_commit: str
    aliases: list[str] | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BookRecord":
        _require_fields(data, ["book_id", "title", "source_commit"], "BookRecord")
        _require_type(data["book_id"], str, "book_id", "BookRecord")
        _require_type(data["title"], str, "title", "BookRecord")
        _require_type(data["source_commit"], str, "source_commit", "BookRecord")
        aliases = data.get("aliases")
        if aliases is not None and not isinstance(aliases, list):
            raise ValidationError("BookRecord.aliases must be a list")
        return cls(
            book_id=data["book_id"],
            title=data["title"],
            source_commit=data["source_commit"],
            aliases=aliases,
        )


@dataclass(frozen=True)
class NormRecord:
    norm_id: str
    book_id: str
    paragraph: str
    heading: str
    span_ids: list[str]
    norm_text_hash: str
    source_commit: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NormRecord":
        _require_fields(data, ["norm_id", "book_id", "paragraph", "heading", "span_ids", "norm_text_hash", "source_commit"], "NormRecord")
        for field in ["norm_id", "book_id", "paragraph", "heading", "norm_text_hash", "source_commit"]:
            _require_type(data[field], str, field, "NormRecord")
        if not isinstance(data["span_ids"], list):
            raise ValidationError("NormRecord.span_ids must be a list")
        return cls(
            norm_id=data["norm_id"],
            book_id=data["book_id"],
            paragraph=data["paragraph"],
            heading=data.get("heading", ""),
            span_ids=[str(v) for v in data["span_ids"]],
            norm_text_hash=data["norm_text_hash"],
            source_commit=data["source_commit"],
        )


@dataclass(frozen=True)
class SpanRecord:
    span_id: str
    book_id: str
    norm_id: str
    paragraph: str
    heading: str
    unit_type: str
    path: list[str]
    ordinal: int
    text: str
    text_hash: str
    source_commit: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SpanRecord":
        required = [
            "span_id",
            "book_id",
            "norm_id",
            "paragraph",
            "heading",
            "unit_type",
            "path",
            "ordinal",
            "text",
            "text_hash",
            "source_commit",
        ]
        _require_fields(data, required, "SpanRecord")
        for field in ["span_id", "book_id", "norm_id", "paragraph", "heading", "unit_type", "text", "text_hash", "source_commit"]:
            _require_type(data[field], str, field, "SpanRecord")
        if not isinstance(data["path"], list):
            raise ValidationError("SpanRecord.path must be a list")
        _require_type(data["ordinal"], int, "ordinal", "SpanRecord")
        return cls(
            span_id=data["span_id"],
            book_id=data["book_id"],
            norm_id=data["norm_id"],
            paragraph=data["paragraph"],
            heading=data["heading"],
            unit_type=data["unit_type"],
            path=[str(x) for x in data["path"]],
            ordinal=data["ordinal"],
            text=data["text"],
            text_hash=data["text_hash"],
            source_commit=data["source_commit"],
        )


@dataclass(frozen=True)
class CardRecord:
    card_id: str
    card_type: str
    norm_id: str
    book_id: str
    heading: str
    one_sentence: str
    roles: list[dict]
    actors: list[dict]
    legal_effects: list[dict]
    conditions: list[dict]
    exceptions_or_limits: list[dict]
    topic_tags: list[str]
    likely_questions: list[str]
    xref_candidates: list[dict]
    compiler: dict

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CardRecord":
        required = [
            "card_id",
            "card_type",
            "norm_id",
            "book_id",
            "heading",
            "one_sentence",
            "roles",
            "actors",
            "legal_effects",
            "conditions",
            "exceptions_or_limits",
            "topic_tags",
            "likely_questions",
            "xref_candidates",
            "compiler",
        ]
        _require_fields(data, required, "CardRecord")
        _require_type(data["card_id"], str, "card_id", "CardRecord")
        _require_type(data["card_type"], str, "card_type", "CardRecord")
        for field in ["norm_id", "book_id", "heading", "one_sentence"]:
            _require_type(data[field], str, field, "CardRecord")
        for field in ["roles", "actors", "legal_effects", "conditions", "exceptions_or_limits", "topic_tags", "likely_questions", "xref_candidates"]:
            if not isinstance(data[field], list):
                raise ValidationError(f"CardRecord.{field} must be a list")
        if not isinstance(data["compiler"], dict):
            raise ValidationError("CardRecord.compiler must be an object")
        return cls(
            card_id=data["card_id"],
            card_type=data["card_type"],
            norm_id=data["norm_id"],
            book_id=data["book_id"],
            heading=data["heading"],
            one_sentence=data["one_sentence"],
            roles=list(data["roles"]),
            actors=list(data["actors"]),
            legal_effects=list(data["legal_effects"]),
            conditions=list(data["conditions"]),
            exceptions_or_limits=list(data["exceptions_or_limits"]),
            topic_tags=list(data["topic_tags"]),
            likely_questions=list(data["likely_questions"]),
            xref_candidates=list(data["xref_candidates"]),
            compiler=dict(data["compiler"]),
        )


@dataclass(frozen=True)
class TopicRecord:
    topic_id: str
    label: str
    description: str
    core_norms: list[str]
    related_norms: list[str] | None = None
    book_scope: list[str] | None = None
    likely_questions: list[str] | None = None
    pitfalls: list[str] | None = None
    evidence: list[str] | None = None
    compiler: dict | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TopicRecord":
        required = ["topic_id", "label", "description", "core_norms"]
        _require_fields(data, required, "TopicRecord")
        for field in ["topic_id", "label", "description"]:
            _require_type(data[field], str, field, "TopicRecord")
        if not isinstance(data["core_norms"], list):
            raise ValidationError("TopicRecord.core_norms must be a list")
        if "related_norms" in data and data["related_norms"] is not None and not isinstance(data["related_norms"], list):
            raise ValidationError("TopicRecord.related_norms must be a list")
        return cls(
            topic_id=data["topic_id"],
            label=data["label"],
            description=data["description"],
            core_norms=list(data["core_norms"]),
            related_norms=list(data.get("related_norms", []) or []),
            book_scope=list(data.get("book_scope", []) or []),
            likely_questions=list(data.get("likely_questions", []) or []),
            pitfalls=list(data.get("pitfalls", []) or []),
            evidence=list(data.get("evidence", []) or []),
            compiler=dict(data["compiler"]) if isinstance(data.get("compiler"), dict) else None,
        )
