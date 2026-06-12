# Source And Extraction Notes

`shabdakosha` keeps each dictionary source in the shape best suited to its
provenance and review workflow. Some dictionaries are maintained as reviewed
text files; others keep a structured source artifact.

## kosha-brihat

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
python3 scripts/extract_gemini.py path/to/pdf-chunks --project YOUR_PROJECT
```

It expects Google Vertex AI credentials in the local environment.

## kosha-pragya

`kosha-pragya` is imported from the compressed JSON source at:

```text
data/dictionaries/kosha-pragya/source/sabdakosh.json.gz
```

Its `metadata.json` records the upstream repository, download URL, checksum, and
the local naming note. The gzip file should be treated as a source artifact, not
as review text. Do not edit it directly.
