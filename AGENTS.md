# Agent Notes

This repository builds reviewable Nepali dictionary datasets. Treat the data in
`data/dictionaries/` as source material that downstream applications consume.

## Repository Shape

- Dictionary metadata lives in `data/dictionaries/<dictionary-id>/metadata.json`.
- Reviewable text corpora live in `data/dictionaries/<dictionary-id>/entries/`.
- Structured upstream artifacts, such as
  `data/dictionaries/kosha-pragya/source/sabdakosh.json.gz`, are source files.
  Do not edit compressed source artifacts directly.
- Per-dictionary slash-headword review worksheets live at
  `data/dictionaries/<dictionary-id>/headword_resolutions.jsonl`.

## Data Rules

- Keep reviewed `.txt` entries in the format documented in `docs/FORMAT.md`:
  one entry per line using `headword --- part_of_speech_or_etymology ---
  definition`.
- Preserve original dictionary headwords, including slash notation, in source
  data. Do not silently replace `A/B` with only `A` or only `B`.
- Resolve slash headwords through `headword_resolutions.jsonl`, one JSON object
  per source line. Reviewers inspect and approve the whole line, not individual
  headwords inside the line.
- A pending resolution does not change the generated consumer database. Only
  `status:"approved"` lines materialize additional lookup rows in `entries`.
- `entries.word` is the canonical consumer lookup field. Use
  `entries.source_entry_id` to join back to `source_entries` when displaying the
  original slash headword or sibling lookup context.
- Headwords, definitions, and resolution worksheet text are normalized to
  Unicode NFC via `shabdakosha/text.normalize_text` during the build, and
  search/lookup queries are normalized the same way at request time. This
  guards against precomposed vs. decomposed Unicode forms (for example nukta
  letters) silently failing to match. Reviewers do not need to manually fix
  Unicode composition differences.

## Common Commands

```bash
python3 scripts/validate.py
python3 scripts/generate_headword_resolutions.py
python3 create_db.py
uv run uvicorn shabdakosha.web.app:app --reload --host 127.0.0.1 --port 8000
docker compose up --build
```

Use `python3 scripts/validate.py --strict` when corpus warnings should fail the
run.

## Editing Guidance

- Prefer focused data corrections and preserve surrounding entries unchanged.
- When regenerating `headword_resolutions.jsonl`, keep reviewer decisions for
  existing lines intact. The generator is designed to preserve reviewer-edited
  headwords and statuses for matching dictionary/source/headword lines.
- If generated slash candidates are uncertain, leave the line `pending` or set a
  review state such as `needs_review`; do not approve by guesswork.
- Do not commit generated `data/dictionary.db`; it is rebuilt from the source
  data.
