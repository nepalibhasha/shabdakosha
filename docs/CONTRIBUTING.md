# Contributing Corrections

Corrections should be made in the smallest relevant text file under
`data/dictionaries/<dictionary-id>/entries/`.

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
python scripts/validate.py
```

Validation may print warnings for existing extraction issues. Fix warnings when
they are part of your review area. Pull requests should not introduce new
validation failures.

If you are reporting an issue instead of editing a file, include the dictionary
id, filename, page number, and the incorrect entry text.
