#!/usr/bin/env python3
"""Generate a grouped review file for slash-headword resolution mappings."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shabdakosha.build_db import (
    IMPORTERS,
    insert_dictionary,
    insert_entries,
    iter_dictionary_dirs,
    load_dictionary_info,
    setup_database,
)
from shabdakosha.headword_aliases import (
    generate_slash_headword_aliases,
    part_looks_like_full_alternate,
)


DEFAULT_REVIEW_STATUS = "pending"
NEEDS_REVIEW_STATUS = "needs_review"


def iter_resolution_files(path: Path) -> list[Path]:
    if not path.is_file():
        return sorted(path.glob("*/headword_resolutions.jsonl"))
    return [path]


def resolution_headword(resolution_item: str | dict) -> str:
    if isinstance(resolution_item, str):
        return resolution_item.strip()
    return (resolution_item.get("headword") or "").strip()


def normalize_status(value: str | None) -> str:
    status = (value or "").strip()
    if not status or status == "generated":
        return DEFAULT_REVIEW_STATUS
    return status


def normalize_existing_group(group: dict, dictionary_id: str, source_file: str, source_headword: str) -> dict:
    status = normalize_status(group.get("review_status") or group.get("status"))
    if status == DEFAULT_REVIEW_STATUS:
        resolution_statuses = [
            normalize_status(item.get("review_status") or item.get("status"))
            for item in group.get("headwords") or group.get("resolutions", [])
            if isinstance(item, dict)
        ]
        if resolution_statuses and all(status == "approved" for status in resolution_statuses):
            status = "approved"

    resolutions = []
    exact_entries = set(group.get("exact_entries") or [])
    seen = set()
    for resolution_item in group.get("headwords") or group.get("resolutions", []):
        headword = resolution_headword(resolution_item)
        if not headword or headword in seen:
            continue
        seen.add(headword)
        resolutions.append(headword)
        if isinstance(resolution_item, dict) and resolution_item.get("exact_entry_exists"):
            exact_entries.add(headword)

    normalized = {
        "dictionary_id": dictionary_id,
        "source_file": source_file,
        "source_headword": source_headword,
        "status": status,
        "headwords": resolutions,
    }
    note = (group.get("notes") or group.get("note") or "").strip()
    if note:
        normalized["note"] = note
    if exact_entries:
        normalized["exact_entries"] = sorted(exact_entries)
    return normalized


def load_existing(path: Path) -> dict[tuple[str, str, str], dict]:
    files = iter_resolution_files(path)
    if not files:
        return {}

    import json

    groups_by_source: dict[tuple[str, str, str], dict] = {}
    for file_path in files:
        groups = [
            json.loads(line)
            for line in file_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for group in groups:
            dictionary_id = (group.get("dictionary_id") or file_path.parent.name).strip()
            source_file = (group.get("source_file") or "").strip()
            source_headword = (group.get("source_headword") or "").strip()
            if not dictionary_id or not source_headword:
                continue
            key = (dictionary_id, source_file, source_headword)
            groups_by_source[key] = normalize_existing_group(
                group,
                dictionary_id,
                source_file,
                source_headword,
            )
    return groups_by_source


def build_temp_database(data_dir: Path, db_path: Path) -> None:
    conn = setup_database(db_path)
    try:
        for dictionary_dir in iter_dictionary_dirs(data_dir):
            info = load_dictionary_info(dictionary_dir)
            importer = IMPORTERS.get(info.id)
            if importer is None:
                continue
            insert_dictionary(conn, info)
            insert_entries(conn, info.id, importer.iter_entries(dictionary_dir))
    finally:
        conn.close()


def legacy_reduplicated_aliases(source_headword: str) -> set[str]:
    parts = [part.strip() for part in source_headword.split("/") if part.strip()]
    if len(parts) < 2:
        return set()

    left = parts[0]
    aliases = set()
    for part in parts[1:]:
        if not part or not part_looks_like_full_alternate(left, part):
            continue
        index = left.rfind(part[0])
        if index < 0:
            continue
        alias = left[:index] + part
        if alias != part:
            aliases.add(alias)
            aliases.add(alias.replace(" ", ""))
    return aliases


def generate_groups(data_dir: Path, existing: dict[tuple[str, str, str], dict]) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "dictionary.db"
        build_temp_database(data_dir, db_path)

        import sqlite3

        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            slash_rows = cursor.execute(
                """
                SELECT dictionary_id, word, base_word, source_file
                FROM entries
                WHERE word LIKE '%/%' OR base_word LIKE '%/%'
                ORDER BY dictionary_id, source_file, word
                """
            ).fetchall()

            groups: dict[tuple[str, str, str], dict] = {}
            for dictionary_id, word, base_word, source_file in slash_rows:
                source_headword = base_word or word
                if "/" not in source_headword:
                    continue

                group_key = (dictionary_id, source_file, source_headword)
                if group_key not in groups:
                    existing_group = existing.get(group_key) or existing.get(
                        (dictionary_id, "", source_headword),
                        {},
                    )
                    groups[group_key] = existing_group or {
                        "dictionary_id": dictionary_id,
                        "source_file": source_file,
                        "source_headword": source_headword,
                        "status": DEFAULT_REVIEW_STATUS,
                        "headwords": [],
                    }

                group = groups[group_key]
                current_resolutions = generate_slash_headword_aliases(source_headword)
                stale_aliases = legacy_reduplicated_aliases(source_headword)
                if group["status"] == DEFAULT_REVIEW_STATUS and stale_aliases:
                    group["headwords"] = [
                        headword
                        for headword in group["headwords"]
                        if headword not in stale_aliases
                    ]
                seen_headwords = set(group["headwords"])
                appended_resolution = False

                for resolution in current_resolutions:
                    if resolution.alias in seen_headwords:
                        continue
                    seen_headwords.add(resolution.alias)
                    appended_resolution = True

                    exact_entry_exists = cursor.execute(
                        """
                        SELECT 1
                        FROM entries
                        WHERE dictionary_id = ? AND word = ?
                        LIMIT 1
                        """,
                        (dictionary_id, resolution.alias),
                    ).fetchone()

                    group["headwords"].append(resolution.alias)
                    if exact_entry_exists:
                        group.setdefault("exact_entries", []).append(resolution.alias)

                if appended_resolution and group["status"] == "approved":
                    group["status"] = NEEDS_REVIEW_STATUS

            return [
                groups[key]
                for key in sorted(
                    groups,
                    key=lambda item: (item[0], item[1], item[2]),
                )
            ]
        finally:
            conn.close()


def write_groups(output_dir: Path, groups: list[dict]) -> None:
    import json

    by_dictionary: dict[str, list[dict]] = {}
    for group in groups:
        by_dictionary.setdefault(group["dictionary_id"], []).append(group)

    for dictionary_id, dictionary_groups in sorted(by_dictionary.items()):
        path = output_dir / dictionary_id / "headword_resolutions.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(
                json.dumps(
                    {
                        "source_file": group["source_file"],
                        "source_headword": group["source_headword"],
                        "status": group["status"],
                        "headwords": group["headwords"],
                        **({"note": group["note"]} if group.get("note") else {}),
                        **(
                            {"exact_entries": sorted(set(group["exact_entries"]))}
                            if group.get("exact_entries")
                            else {}
                        ),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
                for group in dictionary_groups
            ),
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or refresh per-dictionary headword_resolutions.jsonl files."
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data/dictionaries"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/dictionaries"),
        help="Directory containing dictionary subdirectories.",
    )
    args = parser.parse_args()

    existing = load_existing(args.output_dir)
    groups = generate_groups(args.data_dir, existing)
    headword_count = sum(len(group["headwords"]) for group in groups)
    write_groups(args.output_dir, groups)
    print(
        f"Wrote {len(groups)} groups and {headword_count} headwords "
        f"under {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
