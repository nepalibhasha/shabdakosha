## Shabdakosha

This project maintains source data and reviewed corpora for Nepali dictionaries.
Each dictionary lives under `data/dictionaries/<dictionary-id>/` with metadata
describing its source, format, provenance, and curation status.

Current dictionaries:

- `kosha-brihat`: reviewed text corpus based on the Nepali Brihat Shabdakosh.
- `kosha-pragya`: structured JSON gzip source for the Pragya Nepali Brihat
  Shabdakosh.

### How to Contribute

The main way to contribute today is by correcting reviewable text files located
in a dictionary's `entries/` directory. These files may contain extraction
errors.

1.  **Fork** this repository to your own GitHub account.
2.  **Clone** your fork to your local machine.
3.  Navigate to a dictionary's reviewable `entries/` directory. For example:
    `data/dictionaries/kosha-brihat/entries/300/kosha_0247_0248.txt`.
4.  **Edit** the `.txt` files to correct mistakes in the headwords, parts of
    speech, etymology, or definitions. Keep the format described in
    `docs/FORMAT.md`.
    - **Important:** Compare the text file with the corresponding pages in the
      source PDF. The numbers in the filename correspond to the PDF pages.
5.  **Commit** your changes with clear messages describing what you fixed (e.g., "Corrected typos on page 25").
6.  **Push** the changes back to your fork on GitHub.
7.  Submit a **Pull Request** (PR) from your fork back to this main repository.

Alternatively, if you find an error but don't have time to fix it yourself,
please file an issue. Include the dictionary id, filename, page number, and the
incorrect entry text.

Some dictionaries use structured source artifacts instead of editable review
text. For example, `kosha-pragya` keeps its compressed JSON source under
`data/dictionaries/kosha-pragya/source/`. Do not edit compressed source files
directly; corrections should be represented as reviewable patch data when that
workflow is added.

We'll review your changes and merge them. Thank you for helping improve this resource!

### Running the Database Creation Script

After corrections are made and merged, you can regenerate the database using the provided script.

- Validate the reviewed text files: `python3 scripts/validate.py`
- Build the local database: `python3 create_db.py`
- This will generate or update the `data/dictionary.db` file.

Validation failures indicate repository-shape or generated-artifact problems.
Corpus-quality issues in reviewed text are reported as warnings by default; use
`python3 scripts/validate.py --strict` when you want warnings to fail.

## Database Structure

The `create_db.py` script generates a SQLite database file located at
`data/dictionary.db`. This database contains a `dictionaries` table for source
metadata and an `entries` table for normalized dictionary entries.

The `dictionaries` table includes:

| Column Name      | Data Type | Description                                  |
| ---------------- | --------- | -------------------------------------------- |
| `id`             | TEXT      | Stable dictionary id, such as `kosha-brihat` |
| `name`           | TEXT      | Dictionary name                              |
| `name_en`        | TEXT      | English dictionary name, if available        |
| `source_language`| TEXT      | Source language                              |
| `target_language`| TEXT      | Target language                              |
| `script`         | TEXT      | Primary script                               |
| `metadata_json`  | TEXT      | Full source metadata as JSON                 |

The `entries` table includes:

| Column Name      | Data Type | Description                                                               |
| ---------------- | --------- | ------------------------------------------------------------------------- |
| `dictionary_id`  | TEXT      | Source dictionary id.                                                     |
| `word`           | TEXT      | The dictionary word or term extracted from the source.                    |
| `base_word`      | TEXT      | The unnumbered word used for variant grouping.                            |
| `variant_number` | INTEGER   | Variant number for duplicate headwords, if applicable.                    |
| `part_of_speech` | TEXT      | The part of speech, etymology, or grammatical note if identified.         |
| `definition`     | TEXT      | The definition or explanation of the word.                                |
| `split_definitions` | TEXT   | Definition senses as JSON.                                                |
| `source_file`    | TEXT      | Source reference for the entry.                                           |

**Notes:**

- The script parses reviewed `.txt` files using ` --- ` as the field separator.
- `kosha-pragya/source/sabdakosh.json.gz` is treated as a source artifact.
  Corrections should be represented in reviewable patch data rather than by
  editing the compressed source directly.
- `kosha-brihat` files are processed in numeric page order so duplicate handling
  follows the original dictionary sequence.
- Consecutive duplicate `kosha-brihat` headwords are treated as likely
  page-boundary continuations; the longer definition is kept.
- Non-consecutive duplicate `kosha-brihat` headwords are numbered with
  Devanagari numerals.
- `kosha-pragya` entries with multiple definition groups are emitted as numbered
  variants such as `शब्द(१)`, `शब्द(२)`.
