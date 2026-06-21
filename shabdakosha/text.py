"""Shared text normalization helpers."""

from __future__ import annotations

import unicodedata


def normalize_text(value: str | None) -> str | None:
    """Normalize Devanagari (and other) text to NFC.

    Source PDFs, hand-edited review files, and user-typed search queries can
    represent the same word with different combining-mark sequences. Without
    normalization, an exact-match lookup can silently miss even though the
    word is present in the database.
    """
    if value is None:
        return None
    return unicodedata.normalize("NFC", value)
