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
from shabdakosha.text import normalize_text


NEPALI_DIGITS = "०१२३४५६७८९"
IMPORTERS = {
    "kosha-brihat": brihat,
    "kosha-pragya": pragya,
}
APPROVED_RESOLUTION_STATUSES = {"approved"}


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
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS entries")
    cursor.execute("DROP TABLE IF EXISTS source_entries")
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
        CREATE TABLE source_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dictionary_id TEXT NOT NULL,
            display_headword TEXT NOT NULL,
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
            source_entry_id INTEGER NOT NULL,
            entry_kind TEXT NOT NULL,
            FOREIGN KEY(dictionary_id) REFERENCES dictionaries(id),
            FOREIGN KEY(source_entry_id) REFERENCES source_entries(id)
        )
        """
    )
    cursor.execute("CREATE UNIQUE INDEX idx_entries_dictionary_word ON entries(dictionary_id, word)")
    cursor.execute("CREATE INDEX idx_entries_dictionary_base_word ON entries(dictionary_id, base_word)")
    cursor.execute("CREATE INDEX idx_entries_word ON entries(word)")
    cursor.execute("CREATE INDEX idx_entries_base_word ON entries(base_word)")
    cursor.execute("CREATE INDEX idx_entries_source_entry ON entries(source_entry_id)")
    cursor.execute("CREATE INDEX idx_source_entries_dictionary_headword ON source_entries(dictionary_id, display_headword)")
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


def insert_source_entry(
    cursor: sqlite3.Cursor,
    dictionary_id: str,
    display_headword: str,
    base_word: str,
    variant_number: int | None,
    part_of_speech: str | None,
    definition: str,
    split_definitions: str,
    source_file: str,
) -> int:
    cursor.execute(
        """
        INSERT INTO source_entries
        (dictionary_id, display_headword, base_word, variant_number, part_of_speech,
         definition, split_definitions, source_file)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dictionary_id,
            display_headword,
            base_word,
            variant_number,
            part_of_speech,
            definition,
            split_definitions,
            source_file,
        ),
    )
    return int(cursor.lastrowid)


def insert_lookup_entry(
    cursor: sqlite3.Cursor,
    dictionary_id: str,
    word: str,
    base_word: str,
    variant_number: int | None,
    part_of_speech: str | None,
    definition: str,
    split_definitions: str,
    source_file: str,
    source_entry_id: int,
    entry_kind: str,
) -> None:
    cursor.execute(
        """
        INSERT INTO entries
        (dictionary_id, word, base_word, variant_number, part_of_speech,
         definition, split_definitions, source_file, source_entry_id, entry_kind)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dictionary_id,
            word,
            base_word,
            variant_number,
            part_of_speech,
            definition,
            split_definitions,
            source_file,
            source_entry_id,
            entry_kind,
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

        source_entry_id = insert_source_entry(
            cursor,
            dictionary_id,
            word,
            base_word,
            variant_number,
            entry.part_of_speech,
            entry.definition,
            split_definitions,
            entry.source_file,
        )

        try:
            insert_lookup_entry(
                cursor,
                dictionary_id,
                word,
                base_word,
                variant_number,
                entry.part_of_speech,
                entry.definition,
                split_definitions,
                entry.source_file,
                source_entry_id,
                "source_headword",
            )
            inserted += 1
        except sqlite3.IntegrityError:
            cursor.execute("DELETE FROM source_entries WHERE id = ?", (source_entry_id,))
            if word == previous_word:
                cursor.execute(
                    """
                    SELECT id, source_entry_id, LENGTH(definition)
                    FROM entries
                    WHERE dictionary_id = ? AND word = ?
                    """,
                    (dictionary_id, word),
                )
                row = cursor.fetchone()
                if row and len(entry.definition) > row[2]:
                    cursor.execute(
                        """
                        UPDATE entries
                        SET part_of_speech = ?, definition = ?, split_definitions = ?, source_file = ?
                        WHERE id = ?
                        """,
                        (entry.part_of_speech, entry.definition, split_definitions, entry.source_file, row[0]),
                    )
                    cursor.execute(
                        """
                        UPDATE source_entries
                        SET part_of_speech = ?, definition = ?, split_definitions = ?, source_file = ?
                        WHERE id = ?
                        """,
                        (entry.part_of_speech, entry.definition, split_definitions, entry.source_file, row[1]),
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
                        cursor.execute(
                            """
                            UPDATE source_entries
                            SET base_word = ?, variant_number = ?
                            WHERE id = (SELECT source_entry_id FROM entries WHERE id = ?)
                            """,
                            (word, 1, existing[0]),
                        )
                    duplicate_counts[word] = 1

                duplicate_counts[word] += 1
                count = duplicate_counts[word]
                numbered_word = f"{word}({int_to_nepali_numeral(count)})"
                numbered_source_entry_id = insert_source_entry(
                    cursor,
                    dictionary_id,
                    word,
                    word,
                    count,
                    entry.part_of_speech,
                    entry.definition,
                    split_definitions,
                    entry.source_file,
                )
                insert_lookup_entry(
                    cursor,
                    dictionary_id,
                    numbered_word,
                    word,
                    count,
                    entry.part_of_speech,
                    entry.definition,
                    split_definitions,
                    entry.source_file,
                    numbered_source_entry_id,
                    "source_headword",
                )
                numbered += 1

        previous_word = word

    conn.commit()
    return inserted, updated, numbered, skipped


def iter_resolution_files(data_dir: Path, resolutions_path: Path | None = None) -> Iterable[Path]:
    if resolutions_path is not None:
        if resolutions_path.is_file():
            yield resolutions_path
            return
        if resolutions_path.is_dir():
            yield from sorted(resolutions_path.glob("*/headword_resolutions.jsonl"))
            return

    yield from sorted(data_dir.glob("*/headword_resolutions.jsonl"))


def resolution_headword(resolution_item: str | dict) -> str:
    if isinstance(resolution_item, str):
        return normalize_text(resolution_item).strip()
    return normalize_text(resolution_item.get("headword") or "").strip()


def insert_reviewed_headwords(conn: sqlite3.Connection, json_paths: Iterable[Path]) -> int:
    paths = list(json_paths)
    if not paths:
        return 0

    cursor = conn.cursor()
    inserted = 0

    for json_path in paths:
        groups = [
            json.loads(line)
            for line in json_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for group in groups:
            dictionary_id = (group.get("dictionary_id") or json_path.parent.name).strip()
            source_file = (group.get("source_file") or "").strip()
            source_headword = normalize_text(group.get("source_headword") or "").strip()
            if not dictionary_id or not source_headword:
                continue

            group_status = (
                group.get("status")
                or group.get("review_status")
                or ""
            ).strip()

            source_entry = None
            if source_file:
                source_entry = cursor.execute(
                    """
                    SELECT id, display_headword, part_of_speech, definition,
                           split_definitions, source_file
                    FROM source_entries
                    WHERE dictionary_id = ? AND source_file = ? AND display_headword = ?
                    ORDER BY COALESCE(variant_number, 0), display_headword
                    LIMIT 1
                    """,
                    (dictionary_id, source_file, source_headword),
                ).fetchone()
            if source_entry is None:
                source_entry = cursor.execute(
                    """
                    SELECT id, display_headword, part_of_speech, definition,
                           split_definitions, source_file
                    FROM source_entries
                    WHERE dictionary_id = ? AND display_headword = ?
                    ORDER BY COALESCE(variant_number, 0), display_headword
                    LIMIT 1
                    """,
                    (dictionary_id, source_headword),
                ).fetchone()
            if source_entry is None:
                continue

            if group_status not in APPROVED_RESOLUTION_STATUSES:
                continue

            for resolution_item in group.get("headwords") or group.get("resolutions", []):
                headword = resolution_headword(resolution_item)
                if not headword:
                    continue

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO entries
                    (dictionary_id, word, base_word, variant_number, part_of_speech,
                     definition, split_definitions, source_file, source_entry_id, entry_kind)
                    VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dictionary_id,
                        headword,
                        source_entry["display_headword"],
                        source_entry["part_of_speech"],
                        source_entry["definition"],
                        source_entry["split_definitions"],
                        source_entry["source_file"],
                        source_entry["id"],
                        "resolved_headword",
                    ),
                )
                inserted += cursor.rowcount

    conn.commit()
    return inserted


def build_database(data_dir: Path, db_path: Path, resolutions_path: Path | None = None):
    conn = setup_database(db_path)
    summaries = {}
    reviewed_headword_count = 0
    try:
        for dictionary_dir in iter_dictionary_dirs(data_dir):
            info = load_dictionary_info(dictionary_dir)
            importer = IMPORTERS.get(info.id)
            if importer is None:
                print(f"Skipping {info.id}: no importer registered")
                continue
            insert_dictionary(conn, info)
            summaries[info.id] = insert_entries(conn, info.id, importer.iter_entries(dictionary_dir))

        reviewed_headword_count = insert_reviewed_headwords(
            conn,
            iter_resolution_files(data_dir, resolutions_path),
        )
        totals = dict(
            conn.execute(
                "SELECT dictionary_id, COUNT(*) FROM entries GROUP BY dictionary_id ORDER BY dictionary_id"
            ).fetchall()
        )
    finally:
        conn.close()
    return summaries, totals, reviewed_headword_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Build data/dictionary.db from curated dictionary sources.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/dictionaries"))
    parser.add_argument("--db-path", type=Path, default=Path("data/dictionary.db"))
    parser.add_argument(
        "--resolutions-path",
        type=Path,
        default=None,
        help=(
            "Optional resolution JSONL file or directory containing "
            "*/headword_resolutions.jsonl files. Defaults to --data-dir discovery."
        ),
    )
    args = parser.parse_args()

    if not args.data_dir.is_dir():
        raise SystemExit(f"Data directory not found: {args.data_dir}")

    summaries, totals, reviewed_headword_count = build_database(
        args.data_dir,
        args.db_path,
        args.resolutions_path,
    )
    print(f"Database path: {args.db_path}")
    for dictionary_id, total in totals.items():
        inserted, updated, numbered, skipped = summaries[dictionary_id]
        print(f"{dictionary_id}: {total}")
        print(f"  Inserted: {inserted}, updated: {updated}, numbered: {numbered}, skipped: {skipped}")
    print(f"Entries: {sum(totals.values())}")
    print(f"Approved reviewed headwords: {reviewed_headword_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
