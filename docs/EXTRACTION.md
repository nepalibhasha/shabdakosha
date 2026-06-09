# Extraction Notes

The maintained text files are reviewed corpus files. Contributors normally edit
those files directly rather than rerunning extraction.

The original extraction method for `kosha-brihat` used two-page PDF chunks and a
Gemini prompt that:

- read each two-page chunk in column order,
- emitted one entry per line,
- used ` --- ` as the field separator,
- passed the last three entries from the previous chunk as context for page
  boundary continuations,
- wrote chunk markers like `### kosha_0001_0002.pdf ###` before later splitting
  into review files.

The reproducibility script is:

```bash
python scripts/extract_gemini.py path/to/pdf-chunks --project YOUR_PROJECT
```

It expects Google Vertex AI credentials in the local environment.
