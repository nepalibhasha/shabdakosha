# Dictionary Text Format

Reviewed dictionary files live under:

```text
data/dictionaries/<dictionary-id>/entries/
```

For `kosha-brihat`, each file covers two PDF pages:

```text
data/dictionaries/kosha-brihat/entries/100/kosha_0001_0002.txt
```

Each non-empty line should contain one dictionary entry:

```text
headword --- part_of_speech_or_etymology --- definition
```

If no part-of-speech or etymology is visible, leave the middle field empty:

```text
अ(१) --- --- १. देवनागरी वर्णमालाको स्वरवर्णमध्ये पहिलो स्वरवर्ण...
```

Do not include extraction markers, markdown fences, or comments in reviewed
entry files.
