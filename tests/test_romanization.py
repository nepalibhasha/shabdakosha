import sqlite3
import tempfile
import unittest
from pathlib import Path

from shabdakosha.build_db import (
    insert_dictionary,
    insert_entries,
    insert_generated_roman_aliases,
    setup_database,
)
from shabdakosha.models import DictionaryInfo, Entry
from shabdakosha.romanization import normalize_roman_alias, roman_aliases, transliterate_iast


def alias_map(word: str) -> dict[str, int]:
    return {alias.text: alias.weight for alias in roman_aliases(word)}


class RomanizationTests(unittest.TestCase):
    def test_iast_transliteration_is_the_reproducible_base(self) -> None:
        self.assertEqual(transliterate_iast("पानी"), "pānī")
        self.assertEqual(transliterate_iast("शब्द"), "śabda")
        self.assertEqual(transliterate_iast("वचन"), "vacana")
        self.assertEqual(transliterate_iast("संसार"), "saṃsāra")

    def test_casual_aliases_cover_common_nepali_search_typing(self) -> None:
        pani = alias_map("पानी")
        self.assertIn("paani", pani)
        self.assertIn("pani", pani)
        self.assertGreaterEqual(pani["paani"], pani["pani"])

        shabda = alias_map("शब्द")
        self.assertIn("shabda", shabda)
        self.assertIn("sabda", shabda)
        self.assertIn("shabd", shabda)

        vachan = alias_map("वचन")
        self.assertIn("vachan", vachan)
        self.assertIn("wachan", vachan)
        self.assertIn("bachan", vachan)

        sansar = alias_map("संसार")
        self.assertIn("sansaar", sansar)
        self.assertIn("samsaar", sansar)
        self.assertIn("sansar", sansar)

    def test_aliases_are_capped_deduplicated_and_skip_slash_headwords(self) -> None:
        aliases = roman_aliases("संसार")
        self.assertLessEqual(len(aliases), 24)
        self.assertEqual(len({alias.text for alias in aliases}), len(aliases))
        self.assertEqual(roman_aliases("आजकल/काल"), [])

    def test_roman_query_normalization_matches_generated_aliases(self) -> None:
        self.assertEqual(normalize_roman_alias("Śabda"), "sabda")
        self.assertEqual(normalize_roman_alias("  shabd! "), "shabd")


class RomanAliasDatabaseTests(unittest.TestCase):
    def test_generated_aliases_are_build_metadata_not_corpus_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = setup_database(Path(temp_dir) / "dictionary.db")
            try:
                insert_dictionary(
                    conn,
                    DictionaryInfo(
                        id="test-kosha",
                        name="Test Kosha",
                        name_en=None,
                        source_language="Nepali",
                        target_language="Nepali",
                        script="Devanagari",
                        metadata_json="{}",
                    ),
                )
                insert_entries(
                    conn,
                    "test-kosha",
                    [
                        Entry(
                            word="पानी",
                            part_of_speech="ना.",
                            definition="जल।",
                            source_file="test.txt",
                        ),
                        Entry(
                            word="शब्द(१)",
                            base_word="शब्द",
                            variant_number=1,
                            part_of_speech="ना.",
                            definition="ध्वनि।",
                            source_file="test.txt",
                        ),
                    ],
                )
                inserted = insert_generated_roman_aliases(conn)

                self.assertGreater(inserted, 0)
                self.assertIsNotNone(alias_entry(conn, "test-kosha", "paani"))
                self.assertIsNotNone(alias_entry(conn, "test-kosha", "shabd"))
                self.assertIsNone(entry_word(conn, "test-kosha", "paani"))
                self.assertEqual(entry_word(conn, "test-kosha", "पानी")["word"], "पानी")
            finally:
                conn.close()


def alias_entry(conn: sqlite3.Connection, dictionary_id: str, alias: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT *
        FROM roman_aliases
        WHERE dictionary_id = ? AND alias = ?
        LIMIT 1
        """,
        (dictionary_id, alias),
    ).fetchone()


def entry_word(conn: sqlite3.Connection, dictionary_id: str, word: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT *
        FROM entries
        WHERE dictionary_id = ? AND word = ?
        LIMIT 1
        """,
        (dictionary_id, word),
    ).fetchone()


if __name__ == "__main__":
    unittest.main()
