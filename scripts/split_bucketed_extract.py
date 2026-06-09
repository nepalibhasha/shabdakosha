#!/usr/bin/env python3
"""Split bucketed extraction files into smaller review files.

Input files are expected to contain markers like:

    ### kosha_0001_0002.pdf ###

Each marker starts a new output text file named ``kosha_0001_0002.txt``.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


MARKER_RE = re.compile(r"^###\s+([A-Za-z0-9_-]+)_(\d{4})_(\d{4})\.pdf\s+###$")


def bucket_for_page(page: int) -> str:
    return str(((page - 1) // 100 + 1) * 100)


def split_file(path: Path) -> list[tuple[str, int, list[str]]]:
    chunks: list[tuple[str, int, list[str]]] = []
    current_name: str | None = None
    current_start_page: int | None = None
    current_lines: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        marker = MARKER_RE.match(raw_line.strip())
        if marker:
            if current_name is not None:
                chunks.append((current_name, current_start_page or 1, current_lines))
            current_name = f"{marker.group(1)}_{marker.group(2)}_{marker.group(3)}"
            current_start_page = int(marker.group(2))
            current_lines = []
            continue

        if current_name is None:
            if raw_line.strip():
                raise ValueError(f"{path}: content before first marker: {raw_line[:80]}")
            continue

        if raw_line.strip():
            current_lines.append(raw_line.rstrip())

    if current_name is not None:
        chunks.append((current_name, current_start_page or 1, current_lines))

    return chunks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Split marker-delimited bucket files into two-page text files."
    )
    parser.add_argument("input_dir", type=Path, help="Directory containing 100.txt, 200.txt, ...")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("data/dictionaries/kosha-brihat/entries"),
        help="Output directory for review files",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing extracted .txt files under the output directory first",
    )
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {args.input_dir}")

    bucket_files = sorted(
        args.input_dir.glob("[0-9]*.txt"),
        key=lambda p: int(p.stem),
    )
    if not bucket_files:
        raise SystemExit(f"No bucket files found in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.replace:
        for old_file in args.output_dir.glob("*/*.txt"):
            old_file.unlink()

    written = 0
    for bucket_file in bucket_files:
        for chunk_name, start_page, lines in split_file(bucket_file):
            bucket_dir = args.output_dir / bucket_for_page(start_page)
            bucket_dir.mkdir(parents=True, exist_ok=True)
            output_file = bucket_dir / f"{chunk_name}.txt"
            output_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
            written += 1

    print(f"Wrote {written} two-page files to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
