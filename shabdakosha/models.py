"""Shared data models for dictionary importers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DictionaryInfo:
    id: str
    name: str
    name_en: str | None
    source_language: str | None
    target_language: str | None
    script: str | None
    metadata_json: str


@dataclass(frozen=True)
class Entry:
    word: str
    part_of_speech: str | None
    definition: str
    source_file: str
    split_definitions: str | None = None
    base_word: str | None = None
    variant_number: int | None = None
