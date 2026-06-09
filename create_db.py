#!/usr/bin/env python3
"""Build a local SQLite database from the reviewed text corpus."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path


ENTRY_SEP = " --- "
NEPALI_DIGITS = "०१२३४५६७८९"


def natural_sort_key(path: Path):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", str(path))]


def int_to_nepali_numeral(value: int) -> str:
    return "".join(NEPALI_DIGITS[int(digit)] for digit in str(value))


def trim_headword(word: str) -> str:
    word = word.strip()
    variant = re.search(r"\([०-९]+\)$", word)
    if variant:
        base = re.sub(r"[।;(),-]+$", "", word[: variant.start()]).strip()
        return base + variant.group()
    return re.sub(r"[।;(),-]+$", "", word).strip()


def extract_base_word_and_variant(word: str) -> tuple[str, int | None]:
    match = re.match(r"^(.+)\(([०-९]+)\)$", word)
    if not match:
        return word, None
    number = int("".join(str(NEPALI_DIGITS.index(digit)) for digit in match.group(2)))
    return match.group(1), number


def parse_entry(line: str) -> tuple[str, str | None, str] | None:
    line = line.strip()
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


def iter_entries(input_dir: Path):
    for path in sorted(input_dir.glob("*/*.txt"), key=natural_sort_key):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            parsed = parse_entry(line)
            if parsed is None:
                if line.strip():
                    print(f"Skipping malformed line: {path}:{line_no}: {line[:100]}")
                continue
            word, pos, definition = parsed
            yield {
                "word": word,
                "part_of_speech": pos,
                "definition": definition,
                "source_file": str(path.relative_to(input_dir)),
            }


def setup_database(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS entries")
    cursor.execute(
        """
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            base_word TEXT NOT NULL,
            variant_number INTEGER,
            part_of_speech TEXT,
            definition TEXT NOT NULL,
            split_definitions TEXT NOT NULL,
            source_file TEXT NOT NULL
        )
        """
    )
    cursor.execute("CREATE UNIQUE INDEX idx_entries_word ON entries(word)")
    cursor.execute("CREATE INDEX idx_entries_base_word ON entries(base_word)")
    return conn


def insert_entries(conn, entries):
    cursor = conn.cursor()
    previous_word: str | None = None
    duplicate_counts: dict[str, int] = {}
    inserted = updated = numbered = skipped = 0

    for entry in entries:
        word = entry["word"]
        definition = entry["definition"]
        split_json = split_definitions(definition)
        base_word, variant_number = extract_base_word_and_variant(word)

        try:
            cursor.execute(
                """
                INSERT INTO entries
                (word, base_word, variant_number, part_of_speech, definition, split_definitions, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    word,
                    base_word,
                    variant_number,
                    entry["part_of_speech"],
                    definition,
                    split_json,
                    entry["source_file"],
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            if word == previous_word:
                cursor.execute("SELECT id, LENGTH(definition) FROM entries WHERE word = ?", (word,))
                row = cursor.fetchone()
                if row and len(definition) > row[1]:
                    cursor.execute(
                        """
                        UPDATE entries
                        SET part_of_speech = ?, definition = ?, split_definitions = ?, source_file = ?
                        WHERE id = ?
                        """,
                        (entry["part_of_speech"], definition, split_json, entry["source_file"], row[0]),
                    )
                    updated += 1
                else:
                    skipped += 1
            else:
                if word not in duplicate_counts:
                    cursor.execute("SELECT id FROM entries WHERE word = ?", (word,))
                    existing = cursor.fetchone()
                    if existing:
                        first_word = f"{word}(१)"
                        cursor.execute(
                            "UPDATE entries SET word = ?, base_word = ?, variant_number = ? WHERE id = ?",
                            (first_word, word, 1, existing[0]),
                        )
                    duplicate_counts[word] = 1

                duplicate_counts[word] += 1
                count = duplicate_counts[word]
                numbered_word = f"{word}({int_to_nepali_numeral(count)})"
                cursor.execute(
                    """
                    INSERT INTO entries
                    (word, base_word, variant_number, part_of_speech, definition, split_definitions, source_file)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        numbered_word,
                        word,
                        count,
                        entry["part_of_speech"],
                        definition,
                        split_json,
                        entry["source_file"],
                    ),
                )
                numbered += 1

        previous_word = word

    conn.commit()
    return inserted, updated, numbered, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Build data/dictionary.db from reviewed text files.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/dictionaries/kosha-brihat/entries"),
    )
    parser.add_argument("--db-path", type=Path, default=Path("data/dictionary.db"))
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {args.input_dir}")

    conn = setup_database(args.db_path)
    try:
        summary = insert_entries(conn, iter_entries(args.input_dir))
        total = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    finally:
        conn.close()

    inserted, updated, numbered, skipped = summary
    print(f"Database path: {args.db_path}")
    print(f"Entries: {total}")
    print(f"Inserted: {inserted}, updated: {updated}, numbered: {numbered}, skipped: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
