"""Hilfsfunktionen für Text-Normalisierung und Hashing."""

from __future__ import annotations

import hashlib
import re


_WS_RE = re.compile(r"\s+")


def normalize_ws(text: str) -> str:
    """Normalisiere Whitespace für stabile Vergleiche.

    - ersetzt alle Whitespaces durch ein einzelnes Leerzeichen
    - entfernt führende und abschließende Whitespaces
    """

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return _WS_RE.sub(" ", text).strip()


def sha256_text(text: str) -> str:
    """Erzeuge SHA-256 über den normalisierten Text.

    Rückgabeformat: ``sha256:<hex>``.
    """

    normalized = normalize_ws(text)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
