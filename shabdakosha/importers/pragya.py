"""Importer for the canonical kosha-pragya structured JSON gzip source."""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path
from typing import Iterator

from shabdakosha.models import Entry
from shabdakosha.text import normalize_text


NEPALI_DIGITS = "०१२३४५६७८९"


def int_to_nepali_numeral(value: int) -> str:
    return "".join(NEPALI_DIGITS[int(digit)] for digit in str(value))


def trim_trailing_punctuation(word: str) -> str:
    return re.sub(r"[।;(),-]+$", "", normalize_text(word).strip()).strip()


def build_definition(definition: dict) -> str:
    parts: list[str] = []
    grammar = normalize_text(definition.get("grammar", ""))
    etymology = normalize_text(definition.get("etymology", ""))
    if grammar:
        parts.append(grammar)
    if etymology:
        parts.append(etymology)
    parts.extend(normalize_text(sense) for sense in definition.get("senses", []) if sense)
    return " ".join(parts).strip()


def build_part_of_speech(definition: dict) -> str | None:
    parts = []
    if definition.get("grammar"):
        parts.append(normalize_text(definition["grammar"]))
    if definition.get("etymology"):
        parts.append(normalize_text(definition["etymology"]))
    return " ".join(parts) if parts else None


def build_split_definitions(definition: dict) -> str:
    part_of_speech = build_part_of_speech(definition)
    senses = definition.get("senses", [])
    if not senses:
        rows = [{"number": None, "text": "", "part_of_speech": part_of_speech}]
    else:
        rows = []
        for sense in senses:
            sense = normalize_text(sense)
            match = re.match(r"^([०-९]+[.])\s*(.*)$", sense)
            if match:
                rows.append(
                    {
                        "number": match.group(1),
                        "text": match.group(2).strip(),
                        "part_of_speech": part_of_speech,
                    }
                )
            else:
                rows.append({"number": None, "text": sense, "part_of_speech": part_of_speech})
    return json.dumps(rows, ensure_ascii=False)


def load_source(dictionary_dir: Path) -> list[dict]:
    source_path = dictionary_dir / "source" / "sabdakosh.json.gz"
    with gzip.open(source_path, "rt", encoding="utf-8") as file:
        return json.load(file)


def iter_entries(dictionary_dir: Path) -> Iterator[Entry]:
    for source_index, item in enumerate(load_source(dictionary_dir), 1):
        word = trim_trailing_punctuation(item.get("word", ""))
        if not word:
            continue

        definitions = item.get("definitions", [])
        if not definitions:
            continue

        if len(definitions) == 1:
            definition = definitions[0]
            text = build_definition(definition)
            if not text:
                continue
            yield Entry(
                word=word,
                base_word=word,
                variant_number=None,
                part_of_speech=build_part_of_speech(definition),
                definition=text,
                split_definitions=build_split_definitions(definition),
                source_file=f"source/sabdakosh.json.gz#{source_index}",
            )
            continue

        for variant_number, definition in enumerate(definitions, 1):
            text = build_definition(definition)
            if not text:
                continue
            yield Entry(
                word=f"{word}({int_to_nepali_numeral(variant_number)})",
                base_word=word,
                variant_number=variant_number,
                part_of_speech=build_part_of_speech(definition),
                definition=text,
                split_definitions=build_split_definitions(definition),
                source_file=f"source/sabdakosh.json.gz#{source_index}",
            )
