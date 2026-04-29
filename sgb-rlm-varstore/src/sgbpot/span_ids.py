"""ID-Hilfsfunktionen für Normen und Spans."""

from __future__ import annotations

import re




def normalize_paragraph_id(paragraph: str) -> str:
    """Normalize paragraph labels.

    Beispiele:
    - ``§ 24`` -> ``§24``
    - ``§ 24a`` -> ``§24a``
    - ``Art. 1`` -> ``Art.1``
    """

    if not isinstance(paragraph, str):
        raise TypeError("paragraph must be a string")

    value = paragraph.strip()
    if not value:
        return value

    # Mehrfachräume nach § oder Art. entfernen
    value = re.sub(r"^(§)\s*", r"\1", value)
    value = re.sub(r"^(Art\.)\s*", r"\1", value, flags=re.IGNORECASE)
    return value.replace(" ", "")


def norm_id(book_id: str, paragraph: str) -> str:
    """Kombiniere Buch-ID und normiertes Paragraphenkürzel."""

    if not isinstance(book_id, str):
        raise TypeError("book_id must be a string")
    return f"{book_id}:{normalize_paragraph_id(paragraph)}"


def paragraph_span_id(norm_id: str, abs_no: int) -> str:
    """Erzeuge Abschnitts-ID: ``SGB_X:§24:Abs1``."""

    return f"{norm_id}:Abs{int(abs_no)}"


def sentence_span_id(norm_id: str, abs_no: int, sent_no: int) -> str:
    """Erzeuge Satz-ID: ``SGB_X:§24:Abs1:S1``."""

    return f"{norm_id}:Abs{int(abs_no)}:S{int(sent_no)}"
