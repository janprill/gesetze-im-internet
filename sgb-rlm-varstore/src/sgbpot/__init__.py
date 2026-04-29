"""sgbpot: lokale RLM-Varstore-Implementierung für SGB/SGG."""

from .normalize import normalize_ws, sha256_text
from .span_ids import (
    normalize_paragraph_id,
    norm_id,
    paragraph_span_id,
    sentence_span_id,
)
from .schemas import BookRecord, NormRecord, SpanRecord, CardRecord, TopicRecord
from .varstore import SGBMemory

__all__ = [
    "normalize_ws",
    "sha256_text",
    "normalize_paragraph_id",
    "norm_id",
    "paragraph_span_id",
    "sentence_span_id",
    "BookRecord",
    "NormRecord",
    "SpanRecord",
    "CardRecord",
    "TopicRecord",
    "SGBMemory",
]
