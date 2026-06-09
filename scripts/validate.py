#!/usr/bin/env python3
"""Validate reviewed dictionary text files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ENTRY_SEP = " --- "
FILENAME_RE = re.compile(r"^[A-Za-z0-9_-]+_(\d{4})_(\d{4})\.txt$")
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
BAD_MARKERS = ("```", "CARRY_", "###", "file:", "-------------------")


def iter_files(root: Path):
    yield from sorted(root.glob("*/*.txt"), key=lambda p: (p.parent.name, p.name))


def validate_file(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    match = FILENAME_RE.match(path.name)
    if not match:
        errors.append(f"{path}: filename must look like prefix_0001_0002.txt")
    else:
        start, end = map(int, match.groups())
        if end != start + 1:
            errors.append(f"{path}: filename should cover exactly two pages")
        expected_bucket = str(((start - 1) // 100 + 1) * 100)
        if path.parent.name != expected_bucket:
            errors.append(f"{path}: expected parent directory {expected_bucket}")

    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        if any(marker in stripped for marker in BAD_MARKERS):
            errors.append(f"{path}:{line_no}: contains extraction marker or markdown junk")
            continue

        parts = stripped.split(ENTRY_SEP)
        if len(parts) < 2:
            warnings.append(f"{path}:{line_no}: missing separator {ENTRY_SEP!r}")
            continue
        if len(parts) == 2:
            word, definition = parts
            pos = ""
        else:
            word, pos, definition = parts[0], parts[1], ENTRY_SEP.join(parts[2:])

        word = word.strip()
        definition = definition.strip()
        if not word:
            warnings.append(f"{path}:{line_no}: empty headword")
        if not definition:
            warnings.append(f"{path}:{line_no}: empty definition")
        if "(None)" in word:
            errors.append(f"{path}:{line_no}: bad duplicate suffix '(None)'")
        if not DEVANAGARI_RE.search(word):
            warnings.append(f"{path}:{line_no}: headword has no Devanagari characters: {word!r}")
        if pos.count("[") != pos.count("]"):
            warnings.append(f"{path}:{line_no}: unbalanced brackets in part-of-speech field")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dictionary review files.")
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path("data/dictionaries/kosha-brihat/entries"),
    )
    parser.add_argument("--max-errors", type=int, default=50)
    parser.add_argument("--max-warnings", type=int, default=25)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat corpus-quality warnings as validation failures.",
    )
    args = parser.parse_args()

    if not args.root.is_dir():
        raise SystemExit(f"Directory not found: {args.root}")

    files = list(iter_files(args.root))
    if not files:
        raise SystemExit(f"No review .txt files found under {args.root}")

    errors: list[str] = []
    warnings: list[str] = []
    for path in files:
        file_errors, file_warnings = validate_file(path)
        errors.extend(file_errors)
        warnings.extend(file_warnings)

    print(f"Checked {len(files)} files.")
    if warnings:
        print(f"Found {len(warnings)} corpus-quality warnings.")
        for warning in warnings[: args.max_warnings]:
            print(warning)
        if len(warnings) > args.max_warnings:
            print(f"... {len(warnings) - args.max_warnings} more")

    if errors:
        print(f"Found {len(errors)} validation errors.")
        for error in errors[: args.max_errors]:
            print(error)
        if len(errors) > args.max_errors:
            print(f"... {len(errors) - args.max_errors} more")
        return 1

    if args.strict and warnings:
        print("Strict validation failed because warnings are present.")
        return 1

    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
