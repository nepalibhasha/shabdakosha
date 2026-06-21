# Contributing Corrections

Corrections to reviewed text corpora should be made in the smallest relevant
text file under `data/dictionaries/<dictionary-id>/entries/`.

For `kosha-brihat`, filenames contain the PDF pages they came from. For example:

```text
data/dictionaries/kosha-brihat/entries/300/kosha_0247_0248.txt
```

Review workflow:

1. Open the text file for the relevant page range.
2. Compare it with the same pages in the source PDF.
3. Edit only the affected entries.
4. Keep one entry per line using the format in `docs/FORMAT.md`.
5. Run validation before opening a pull request:

```bash
python3 scripts/validate.py
```

Validation may print warnings for existing extraction issues. Fix warnings when
they are part of your review area. Pull requests should not introduce new
validation failures.

If you are reporting an issue instead of editing a file, include the dictionary
id, filename, page number, and the incorrect entry text.

## Reviewing Slash Headwords

Some dictionary headwords contain slashes, such as `अँगरखा/अँगर्खा`.
Do not rewrite those source entries in the `.txt` files just to make lookup
forms. The original slash form is part of the dictionary record and should be
preserved.

Slash lookup forms are reviewed in each dictionary's JSON Lines worksheet:

```text
data/dictionaries/<dictionary-id>/headword_resolutions.jsonl
```

Each line represents one source dictionary entry. Review the whole line at once:

```json
{"source_file":"100/kosha_0001_0002.txt","source_headword":"अँगरखा/अँगर्खा","status":"pending","headwords":["अँगरखा","अँगर्खा"]}
```

- Keep `source_headword` as the exact source dictionary headword.
- Edit `headwords` to the searchable lookup forms that should point to that
  source entry.
- Leave uncertain lines as `pending` or mark them `needs_review`.
- Change `status` to `approved` only when every headword on the line has been
  checked.

Approved lines materialize additional rows in the generated `entries` table.
Pending, rejected, or needs-review lines do not affect consumer lookup rows.
Refresh worksheets with:

```bash
python3 scripts/generate_headword_resolutions.py
```

The refresh keeps reviewer decisions for existing dictionary/source/headword
lines and adds new candidates when source data changes.

Some dictionaries use structured source artifacts instead of editable review
text. For example, `kosha-pragya` currently keeps
`data/dictionaries/kosha-pragya/source/sabdakosh.json.gz` as its source file. Do
not edit compressed source files directly. Corrections for those dictionaries
should use a reviewable patch layer once one exists, or be reported with the
dictionary id, source reference, headword, and incorrect text.
