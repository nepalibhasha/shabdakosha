"""Build SQLite dictionary artifacts from curated dictionary sources."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from shabdakosha.importers import brihat, pragya
from shabdakosha.models import DictionaryInfo, Entry


NEPALI_DIGITS = "०१२३४५६७८९"
IMPORTERS = {
    "kosha-brihat": brihat,
    "kosha-pragya": pragya,
}


def int_to_nepali_numeral(value: int) -> str:
    return "".join(NEPALI_DIGITS[int(digit)] for digit in str(value))


def extract_base_word_and_variant(word: str) -> tuple[str, int | None]:
    match = re.match(r"^(.+)\(([०-९]+)\)$", word)
    if not match:
        return word, None
    number = int("".join(str(NEPALI_DIGITS.index(digit)) for digit in match.group(2)))
    return match.group(1), number


def load_dictionary_info(dictionary_dir: Path) -> DictionaryInfo:
    metadata_path = dictionary_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return DictionaryInfo(
        id=metadata["id"],
        name=metadata["name"],
        name_en=metadata.get("name_en"),
        source_language=metadata.get("source_language"),
        target_language=metadata.get("target_language"),
        script=metadata.get("script"),
        metadata_json=json.dumps(metadata, ensure_ascii=False, sort_keys=True),
    )


def iter_dictionary_dirs(data_dir: Path) -> Iterable[Path]:
    for dictionary_dir in sorted(data_dir.iterdir()):
        if dictionary_dir.is_dir() and (dictionary_dir / "metadata.json").is_file():
            yield dictionary_dir


def setup_database(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS entries")
    cursor.execute("DROP TABLE IF EXISTS dictionaries")
    cursor.execute(
        """
        CREATE TABLE dictionaries (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            name_en TEXT,
            source_language TEXT,
            target_language TEXT,
            script TEXT,
            metadata_json TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dictionary_id TEXT NOT NULL,
            word TEXT NOT NULL,
            base_word TEXT NOT NULL,
            variant_number INTEGER,
            part_of_speech TEXT,
            definition TEXT NOT NULL,
            split_definitions TEXT NOT NULL,
            source_file TEXT NOT NULL,
            FOREIGN KEY(dictionary_id) REFERENCES dictionaries(id)
        )
        """
    )
    cursor.execute("CREATE UNIQUE INDEX idx_entries_dictionary_word ON entries(dictionary_id, word)")
    cursor.execute("CREATE INDEX idx_entries_dictionary_base_word ON entries(dictionary_id, base_word)")
    cursor.execute("CREATE INDEX idx_entries_word ON entries(word)")
    cursor.execute("CREATE INDEX idx_entries_base_word ON entries(base_word)")
    return conn


def insert_dictionary(conn: sqlite3.Connection, info: DictionaryInfo):
    conn.execute(
        """
        INSERT INTO dictionaries
        (id, name, name_en, source_language, target_language, script, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            info.id,
            info.name,
            info.name_en,
            info.source_language,
            info.target_language,
            info.script,
            info.metadata_json,
        ),
    )


def insert_entries(conn: sqlite3.Connection, dictionary_id: str, entries: Iterable[Entry]):
    cursor = conn.cursor()
    previous_word: str | None = None
    duplicate_counts: dict[str, int] = {}
    inserted = updated = numbered = skipped = 0

    for entry in entries:
        word = entry.word
        base_word, variant_number = (
            (entry.base_word, entry.variant_number)
            if entry.base_word is not None
            else extract_base_word_and_variant(word)
        )
        split_definitions = entry.split_definitions or brihat.split_definitions(entry.definition)

        try:
            cursor.execute(
                """
                INSERT INTO entries
                (dictionary_id, word, base_word, variant_number, part_of_speech,
                 definition, split_definitions, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dictionary_id,
                    word,
                    base_word,
                    variant_number,
                    entry.part_of_speech,
                    entry.definition,
                    split_definitions,
                    entry.source_file,
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            if word == previous_word:
                cursor.execute(
                    """
                    SELECT id, LENGTH(definition)
                    FROM entries
                    WHERE dictionary_id = ? AND word = ?
                    """,
                    (dictionary_id, word),
                )
                row = cursor.fetchone()
                if row and len(entry.definition) > row[1]:
                    cursor.execute(
                        """
                        UPDATE entries
                        SET part_of_speech = ?, definition = ?, split_definitions = ?, source_file = ?
                        WHERE id = ?
                        """,
                        (entry.part_of_speech, entry.definition, split_definitions, entry.source_file, row[0]),
                    )
                    updated += 1
                else:
                    skipped += 1
            else:
                if word not in duplicate_counts:
                    cursor.execute(
                        "SELECT id FROM entries WHERE dictionary_id = ? AND word = ?",
                        (dictionary_id, word),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        first_word = f"{word}(१)"
                        cursor.execute(
                            """
                            UPDATE entries
                            SET word = ?, base_word = ?, variant_number = ?
                            WHERE id = ?
                            """,
                            (first_word, word, 1, existing[0]),
                        )
                    duplicate_counts[word] = 1

                duplicate_counts[word] += 1
                count = duplicate_counts[word]
                numbered_word = f"{word}({int_to_nepali_numeral(count)})"
                cursor.execute(
                    """
                    INSERT INTO entries
                    (dictionary_id, word, base_word, variant_number, part_of_speech,
                     definition, split_definitions, source_file)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dictionary_id,
                        numbered_word,
                        word,
                        count,
                        entry.part_of_speech,
                        entry.definition,
                        split_definitions,
                        entry.source_file,
                    ),
                )
                numbered += 1

        previous_word = word

    conn.commit()
    return inserted, updated, numbered, skipped


def build_database(data_dir: Path, db_path: Path):
    conn = setup_database(db_path)
    summaries = {}
    try:
        for dictionary_dir in iter_dictionary_dirs(data_dir):
            info = load_dictionary_info(dictionary_dir)
            importer = IMPORTERS.get(info.id)
            if importer is None:
                print(f"Skipping {info.id}: no importer registered")
                continue
            insert_dictionary(conn, info)
            summaries[info.id] = insert_entries(conn, info.id, importer.iter_entries(dictionary_dir))

        totals = dict(
            conn.execute(
                "SELECT dictionary_id, COUNT(*) FROM entries GROUP BY dictionary_id ORDER BY dictionary_id"
            ).fetchall()
        )
    finally:
        conn.close()
    return summaries, totals


def main() -> int:
    parser = argparse.ArgumentParser(description="Build data/dictionary.db from curated dictionary sources.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/dictionaries"))
    parser.add_argument("--db-path", type=Path, default=Path("data/dictionary.db"))
    args = parser.parse_args()

    if not args.data_dir.is_dir():
        raise SystemExit(f"Data directory not found: {args.data_dir}")

    summaries, totals = build_database(args.data_dir, args.db_path)
    print(f"Database path: {args.db_path}")
    for dictionary_id, total in totals.items():
        inserted, updated, numbered, skipped = summaries[dictionary_id]
        print(f"{dictionary_id}: {total}")
        print(f"  Inserted: {inserted}, updated: {updated}, numbered: {numbered}, skipped: {skipped}")
    print(f"Entries: {sum(totals.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
