#!/usr/bin/env python3
"""Extract dictionary entries from two-page PDF chunks with Gemini.

This script is provided for reproducibility. The maintained corpus is the text
under ``data/dictionaries/<dictionary-id>/entries``; contributors normally edit
those files directly.
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import re
import time
from pathlib import Path

from google import genai
from google.genai import types


def natural_sort_key(value: str):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", value)]


def get_last_entries(output_file: Path, num_lines: int) -> str:
    if not output_file.exists():
        return ""
    lines = output_file.read_text(encoding="utf-8").splitlines()
    entries = [line.strip() for line in lines if " --- " in line and line.strip()]
    return "\n".join(entries[-num_lines:])


def build_prompt(previous_context: str = "") -> str:
    base_prompt = """Instructions:

1. This is a Nepali dictionary PDF with TWO COLUMNS per page.
2. Read and extract entries in SEQUENTIAL ORDER:
   - First: Page 1, LEFT column (top to bottom)
   - Then: Page 1, RIGHT column (top to bottom)
   - Then: Page 2, LEFT column (top to bottom)
   - Then: Page 2, RIGHT column (top to bottom)
3. EXCLUDE headers and footers.
4. Extract: Word, Part of Speech/Etymology, and Definition.
5. If Part of Speech/Etymology is missing, leave that field empty.
6. Combine word entries that span across lines within the same column.
7. Output format, one entry per line:

Word --- Part of Speech/Etymology --- Definition(s)

IMPORTANT:
- Output ONLY dictionary entries in plain text, one per line
- Use exactly " --- " as separator
- Follow the sequential column order strictly
- NO markdown, NO bullets, NO backticks, NO code blocks
- NO explanations or commentary

HOMOGRAPH INDEXING:
- Preserve repeated headword indexes as part of the headword using Devanagari
  numerals in parentheses: अ(१), अ(२), अ(३).
- Do not confuse these with definition numbering."""

    if not previous_context:
        return base_prompt

    return (
        base_prompt
        + f"""

CONTEXT FROM PREVIOUS FILE:
These are the last entries from the previous PDF chunk:

{previous_context}

PAGE BOUNDARY:
- The first visible text may continue an entry from the previous file.
- If it is continuation text, output the complete merged entry first.
- Then continue extracting new entries in sequential column order.
- Duplication of the merged entry is acceptable and expected."""
    )


def generate(client, model: str, pdf_file: Path, output_file: Path, previous_context: str):
    logging.info("Processing: %s", pdf_file)
    pdf_data = pdf_file.read_bytes()
    document = types.Part.from_bytes(data=pdf_data, mime_type="application/pdf")
    prompt = build_prompt(previous_context)
    system_instruction = (
        "You are a dictionary data extractor. Extract word entries from Nepali "
        "dictionary PDFs. Output only plain text entries in the exact format requested."
    )
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text="Extract all dictionary entries from this PDF:"),
                document,
                types.Part.from_text(text=prompt),
            ],
        )
    ]
    config = types.GenerateContentConfig(
        temperature=0.2,
        top_p=0.95,
        max_output_tokens=16384,
        response_modalities=["TEXT"],
        system_instruction=[types.Part.from_text(text=system_instruction)],
    )

    with output_file.open("a", encoding="utf-8") as outfile:
        outfile.write(f"\n### {pdf_file.name} ###\n")
        for chunk in client.models.generate_content_stream(model=model, contents=contents, config=config):
            if chunk.text:
                outfile.write(chunk.text)
        outfile.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract entries from two-page PDF chunks.")
    parser.add_argument("input_dir", type=Path, help="Directory containing two-page PDF chunks")
    parser.add_argument("-o", "--output-dir", type=Path, help="Output directory")
    parser.add_argument("--model", default=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))
    parser.add_argument("--project", default=os.environ.get("GCLOUD_PROJECT"))
    parser.add_argument("--location", default=os.environ.get("GCLOUD_LOCATION", "us-central1"))
    parser.add_argument("--context-lines", type=int, default=3)
    parser.add_argument("--sleep", type=int, default=3)
    args = parser.parse_args()

    if not args.project:
        raise SystemExit("Set GCLOUD_PROJECT or pass --project")
    if not args.input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {args.input_dir}")

    output_dir = args.output_dir or Path(str(args.input_dir).replace("/chunks/", "/extracted/"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "output.txt"
    log_file = output_dir / "output.log"
    output_file.write_text("", encoding="utf-8")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file, mode="w")],
        force=True,
    )
    logging.info("Input directory: %s", args.input_dir)
    logging.info("Output directory: %s", output_dir)
    logging.info("Model: %s", args.model)

    pdf_files = sorted(glob.glob(str(args.input_dir / "*.pdf")), key=natural_sort_key)
    if not pdf_files:
        raise SystemExit(f"No PDF files found in {args.input_dir}")

    client = genai.Client(vertexai=True, project=args.project, location=args.location)
    for index, pdf_name in enumerate(pdf_files):
        previous_context = get_last_entries(output_file, args.context_lines) if index else ""
        if previous_context:
            logging.info("Passing %s entries as context", args.context_lines)
        generate(client, args.model, Path(pdf_name), output_file, previous_context)
        if index < len(pdf_files) - 1:
            time.sleep(args.sleep)

    logging.info("Complete. Output: %s", output_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
