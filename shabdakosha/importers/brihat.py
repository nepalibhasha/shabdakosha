"""Importer for the reviewed kosha-brihat text corpus."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator

from shabdakosha.models import Entry
from shabdakosha.text import normalize_text


ENTRY_SEP = " --- "
NEPALI_DIGITS = "०१२३४५६७८९"


def natural_sort_key(path: Path):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", str(path))]


def trim_headword(word: str) -> str:
    word = word.strip()
    variant = re.search(r"\([०-९]+\)$", word)
    if variant:
        base = re.sub(r"[।;(),-]+$", "", word[: variant.start()]).strip()
        return base + variant.group()
    return re.sub(r"[।;(),-]+$", "", word).strip()


def parse_entry(line: str) -> tuple[str, str | None, str] | None:
    line = normalize_text(line).strip()
    if not line:
        return None
    match = re.match(r"(.+?)\s+---(.+?)---(.+)", line)
    if match:
        word = match.group(1).strip()
        pos = match.group(2).strip() or None
        definition = match.group(3).strip()
    else:
        match = re.match(r"(.+?)\s+---(.+)", line)
        if not match:
            return None
        word = match.group(1).strip()
        pos = None
        definition = match.group(2).strip()
    if not word or not definition:
        return None
    return trim_headword(word), pos, definition


def split_definitions(definition: str) -> str:
    pattern = r"([०-९]+[.])\s*(.*?)(?=(?:\s+[०-९]+[.])|$)"
    matches = re.findall(pattern, definition)
    if not matches:
        return json.dumps(
            [{"number": None, "text": definition.strip(), "part_of_speech": None}],
            ensure_ascii=False,
        )
    return json.dumps(
        [
            {"number": number, "text": text.strip(), "part_of_speech": None}
            for number, text in matches
        ],
        ensure_ascii=False,
    )


def iter_entries(dictionary_dir: Path) -> Iterator[Entry]:
    input_dir = dictionary_dir / "entries"
    for path in sorted(input_dir.glob("*/*.txt"), key=natural_sort_key):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            parsed = parse_entry(line)
            if parsed is None:
                if line.strip():
                    print(f"Skipping malformed line: {path}:{line_no}: {line[:100]}")
                continue
            word, pos, definition = parsed
            yield Entry(
                word=word,
                part_of_speech=pos,
                definition=definition,
                source_file=str(path.relative_to(input_dir)),
            )
