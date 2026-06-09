## Shabdakosha

This project maintains reviewed text corpora for Nepali dictionaries extracted
from scanned sources. The first corpus is `kosha-brihat`, based on the Nepali
Brihat Shabdakosh.

### How to Contribute

The main way to contribute is by correcting the extracted text files located in
`data/dictionaries/<dictionary-id>/entries/`. These files may contain extraction
errors.

1.  **Fork** this repository to your own GitHub account.
2.  **Clone** your fork to your local machine.
3.  Navigate to a dictionary's `entries/` directory. For example:
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

We'll review your changes and merge them. Thank you for helping improve this resource!

### Running the Database Creation Script

After corrections are made and merged, you can regenerate the database using the provided script.

- Validate the text files: `python scripts/validate.py`
- Build the local database: `python create_db.py`
- This will generate or update the `data/dictionary.db` file.

Validation failures indicate repository-shape or generated-artifact problems.
Corpus-quality issues in the extracted text are reported as warnings by default;
use `python scripts/validate.py --strict` when you want warnings to fail.

## Database Structure

The `create_db.py` script generates a SQLite database file located at
`data/dictionary.db`. This database contains a single table named `entries` with
the following core fields:

| Column Name      | Data Type | Description                                                               |
| ---------------- | --------- | ------------------------------------------------------------------------- |
| `word`           | TEXT      | The dictionary word or term extracted from the source.                    |
| `base_word`      | TEXT      | The unnumbered word used for variant grouping.                            |
| `variant_number` | INTEGER   | Variant number for duplicate headwords, if applicable.                    |
| `part_of_speech` | TEXT      | The part of speech, etymology, or grammatical note if identified.         |
| `definition`     | TEXT      | The definition or explanation of the word.                                |
| `source_file`    | TEXT      | The reviewed text file the entry came from.                               |

**Notes:**

- The script parses reviewed `.txt` files using ` --- ` as the field separator.
- Files are processed in numeric page order so duplicate handling follows the
  original dictionary sequence.
- Consecutive duplicate headwords are treated as likely page-boundary
  continuations; the longer definition is kept.
- Non-consecutive duplicate headwords are numbered with Devanagari numerals.
