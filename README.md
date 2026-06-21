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

### Running the Resource Browser

The repository includes a read-only web browser for inspecting dictionary
metadata, generated entries, source references, and cross-dictionary base-word
matches.

Run it locally:

```bash
uv run uvicorn shabdakosha.web.app:app --reload --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

If `data/dictionary.db` is missing, the browser builds it from
`data/dictionaries/` before serving requests.

Run it with Docker:

```bash
docker compose up --build
```

The browser is intentionally separate from product applications. It is for
inspecting and validating this repository's dictionary sources and generated
artifacts.

## Database Structure

The `create_db.py` script generates a SQLite database file located at
`data/dictionary.db`. This database contains a `dictionaries` table for source
metadata, a `source_entries` table that preserves dictionary entries as curated,
and an `entries` table for user-facing lookup headwords.

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

The `source_entries` table includes:

| Column Name      | Data Type | Description                                                               |
| ---------------- | --------- | ------------------------------------------------------------------------- |
| `dictionary_id`  | TEXT      | Source dictionary id.                                                     |
| `display_headword` | TEXT    | The dictionary headword exactly as maintained, including slash notation.  |
| `base_word`      | TEXT      | The unnumbered word used for variant grouping.                            |
| `variant_number` | INTEGER   | Variant number for duplicate headwords, if applicable.                    |
| `part_of_speech` | TEXT      | The part of speech, etymology, or grammatical note if identified.         |
| `definition`     | TEXT      | The definition or explanation of the word.                                |
| `split_definitions` | TEXT   | Definition senses as JSON.                                                |
| `source_file`    | TEXT      | Source reference for the entry.                                           |

The `entries` table is the canonical lookup table. It duplicates the definition
fields for simple consumers and links each lookup row back to its preserved
source row:

| Column Name       | Data Type | Description                                                              |
| ----------------- | --------- | ------------------------------------------------------------------------ |
| `dictionary_id`   | TEXT      | Source dictionary id.                                                    |
| `word`            | TEXT      | Searchable lookup headword.                                              |
| `base_word`       | TEXT      | Grouping word. For approved slash rows, this is the source slash headword. |
| `variant_number`  | INTEGER   | Variant number for duplicate source headwords, if applicable.            |
| `part_of_speech`  | TEXT      | Copied from the source entry.                                            |
| `definition`      | TEXT      | Copied from the source entry.                                            |
| `split_definitions` | TEXT    | Copied definition senses as JSON.                                        |
| `source_file`     | TEXT      | Source reference for the entry.                                          |
| `source_entry_id` | INTEGER   | Link to `source_entries.id`.                                             |
| `entry_kind`      | TEXT      | `source_headword` or `resolved_headword`.                                |

Slash-headword mappings are reviewed in each dictionary's
`headword_resolutions.jsonl` file before they materialize extra lookup rows.
Generate or refresh those worksheets with:

```bash
python3 scripts/generate_headword_resolutions.py
```

Each review file uses JSON Lines: one compact JSON object per source slash
headword. Each line starts as `status:"pending"` and contains the candidate
resolved headwords for that source entry:

```json
{"source_file":"100/kosha_0001_0002.txt","source_headword":"अँगरखा/अँगर्खा","status":"pending","headwords":["अँगरखा","अँगर्खा"]}
```

Review line keys:

| Key                  | Meaning                                                         |
| -------------------- | --------------------------------------------------------------- |
| `source_file`        | Source reference for disambiguating repeated slash headwords.   |
| `source_headword`    | Original slash headword from the source dictionary.             |
| `status`             | `pending`, `approved`, `needs_review`, or another review state such as `rejected`. |
| `headwords`          | Searchable headwords to materialize for the source slash entry. |
| `note`               | Reviewer note.                                                  |
| `exact_entries`      | Generated when one or more resolved forms already exist as entries. |

Reviewers should inspect one JSONL line at a time. To materialize all reviewed
headwords on that line into `entries`, change the line status to `approved`.
If a refresh adds a new generated headword to an already approved line, the
generator changes that line to `needs_review` so it is checked again before
database build.

For example,
`data/dictionaries/kosha-brihat/headword_resolutions.jsonl`
contains `अँगरखा/अँगर्खा`, which should resolve to both `अँगरखा` and
`अँगर्खा`. Compact forms such as `आजकल/काल` need review because the second form
is `आजकाल`, not bare `काल`. Set the line's `status` to `approved` only after
checking that every resolved form on the line should point at the slash entry.
Leave pending, rejected, or needs-review lines out of the consumer contract.
Consumers search only `entries.word`; they can join `entries.source_entry_id` to
`source_entries.id` to display the original slash headword and show that sibling
lookup headwords share the same dictionary source entry.

**Notes:**

- The script parses reviewed `.txt` files using ` --- ` as the field separator.
- Refreshing `headword_resolutions.jsonl` preserves reviewer-added resolution
  headwords for the same dictionary, source file, and source headword, then adds
  newly generated candidates.
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
- Slash headwords such as `आजकल/काल` are preserved in `source_entries`.
  Approved per-dictionary `headword_resolutions.jsonl` lines materialize
  additional `entries.word` lookup rows that point back to the same source entry.
- Future improvement: once a slash headword has approved split lookup rows,
  consider suppressing the original slash form from ordinary `entries.word`
  search results while keeping it in `source_entries.display_headword` for
  faithful dictionary display.
