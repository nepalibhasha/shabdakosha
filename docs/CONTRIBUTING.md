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

Some dictionaries use structured source artifacts instead of editable review
text. For example, `kosha-pragya` currently keeps
`data/dictionaries/kosha-pragya/source/sabdakosh.json.gz` as its source file. Do
not edit compressed source files directly. Corrections for those dictionaries
should use a reviewable patch layer once one exists, or be reported with the
dictionary id, source reference, headword, and incorrect text.
