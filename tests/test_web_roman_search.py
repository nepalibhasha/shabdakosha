import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

if importlib.util.find_spec("fastapi") is None:
    raise unittest.SkipTest("FastAPI is not installed in this Python environment")

from shabdakosha.build_db import (
    insert_dictionary,
    insert_entries,
    insert_generated_roman_aliases,
    setup_database,
)
from shabdakosha.models import DictionaryInfo, Entry


class WebRomanSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "dictionary.db"
        conn = setup_database(self.db_path)
        try:
            insert_dictionary(
                conn,
                DictionaryInfo(
                    id="test-kosha",
                    name="Test Kosha",
                    name_en="Test Dictionary",
                    source_language="Nepali",
                    target_language="Nepali",
                    script="Devanagari",
                    metadata_json="{}",
                ),
            )
            insert_dictionary(
                conn,
                DictionaryInfo(
                    id="kosha-brihat",
                    name="Brihat",
                    name_en="Brihat",
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
                    )
                ],
            )
            insert_entries(
                conn,
                "kosha-brihat",
                [
                    Entry("जड ", "वि.", "पहिलो अर्थ।", "100.txt"),
                    Entry("बीचको", "वि.", "अर्को शब्द।", "100.txt"),
                    Entry("जड", "वि.", "दोस्रो अर्थ।", "200.txt"),
                ],
            )
            insert_generated_roman_aliases(conn)
        finally:
            conn.close()

        self.previous_db_path = os.environ.get("SHABDAKOSHA_DB_PATH")
        os.environ["SHABDAKOSHA_DB_PATH"] = str(self.db_path)

    def tearDown(self) -> None:
        if self.previous_db_path is None:
            os.environ.pop("SHABDAKOSHA_DB_PATH", None)
        else:
            os.environ["SHABDAKOSHA_DB_PATH"] = self.previous_db_path
        self.temp_dir.cleanup()

    def test_grouped_search_matches_paani_to_pani_result(self) -> None:
        from shabdakosha.web.app import grouped_search

        groups = grouped_search("paani")

        self.assertEqual(groups[0]["lookup_word"], "पानी")
        self.assertEqual(groups[0]["matched_roman_alias"], "paani")

    def test_autocomplete_returns_roman_match_metadata(self) -> None:
        from shabdakosha.web.app import suggest_words

        suggestions = suggest_words("paani")
        self.assertEqual(suggestions[0]["word"], "पानी")
        self.assertEqual(suggestions[0]["matched_roman_alias"], "paani")

    def test_grouped_search_normalizes_variant_suffix_spacing(self) -> None:
        from shabdakosha.web.app import grouped_search

        groups = grouped_search("जड (१)", dictionary_id="kosha-brihat")

        self.assertEqual(groups[0]["lookup_word"], "जड(१)")
        self.assertEqual(groups[0]["entries"][0]["word"], "जड(१)")

    def test_get_entry_normalizes_variant_suffix_spacing(self) -> None:
        from shabdakosha.web.app import get_entry

        entry = get_entry("kosha-brihat", "जड (२)")

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["word"], "जड(२)")


if __name__ == "__main__":
    unittest.main()
