import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from shabdakosha.build_db import insert_entries, setup_database
from shabdakosha.importers.brihat import natural_sort_key, split_definitions as split_brihat_definitions
from shabdakosha.importers.pragya import build_part_of_speech, build_split_definitions
from shabdakosha.models import Entry


class BrihatImportTests(unittest.TestCase):
    def test_page_bucket_files_sort_numerically(self) -> None:
        files = [Path(name) for name in ["100.txt", "1000.txt", "1400.txt", "200.txt", "notes.txt"]]

        self.assertEqual(
            [path.name for path in sorted(files, key=natural_sort_key)],
            ["100.txt", "200.txt", "1000.txt", "1400.txt", "notes.txt"],
        )

    def test_consecutive_brihat_duplicate_keeps_longer_definition(self) -> None:
        with temp_database() as conn:
            summary = insert_entries(
                conn,
                "kosha-brihat",
                [
                    Entry("उड्नु", "क्रि.", "छोटो।", "100.txt"),
                    Entry("उड्नु", "क्रि.", "धेरै लामो अर्थ।", "101.txt"),
                ],
            )

            row = lookup_entry(conn, "kosha-brihat", "उड्नु")
            self.assertEqual(summary, (1, 1, 0, 0))
            self.assertEqual(row["definition"], "धेरै लामो अर्थ।")

    def test_non_consecutive_brihat_duplicates_are_numbered(self) -> None:
        with temp_database() as conn:
            summary = insert_entries(
                conn,
                "kosha-brihat",
                [
                    Entry("उड्नु", "क्रि.", "पहिलो अर्थ।", "100.txt"),
                    Entry("बीचको", "वि.", "अर्को शब्द।", "100.txt"),
                    Entry("उड्नु", "क्रि.", "दोस्रो अर्थ।", "200.txt"),
                ],
            )

            rows = conn.execute(
                """
                SELECT word, base_word, variant_number, definition
                FROM entries
                WHERE dictionary_id = ? AND base_word = ?
                ORDER BY variant_number
                """,
                ("kosha-brihat", "उड्नु"),
            ).fetchall()
            self.assertEqual(summary, (2, 0, 1, 0))
            self.assertEqual(
                [(row["word"], row["base_word"], row["variant_number"], row["definition"]) for row in rows],
                [
                    ("उड्नु(१)", "उड्नु", 1, "पहिलो अर्थ।"),
                    ("उड्नु(२)", "उड्नु", 2, "दोस्रो अर्थ।"),
                ],
            )

    def test_non_consecutive_brihat_duplicate_keys_strip_base_whitespace(self) -> None:
        with temp_database() as conn:
            summary = insert_entries(
                conn,
                "kosha-brihat",
                [
                    Entry("जड ", "वि.", "पहिलो अर्थ।", "100.txt"),
                    Entry("बीचको", "वि.", "अर्को शब्द।", "100.txt"),
                    Entry("जड", "वि.", "दोस्रो अर्थ।", "200.txt"),
                ],
            )

            rows = conn.execute(
                """
                SELECT word, base_word, variant_number
                FROM entries
                WHERE dictionary_id = ? AND base_word = ?
                ORDER BY variant_number
                """,
                ("kosha-brihat", "जड"),
            ).fetchall()
            self.assertEqual(summary, (2, 0, 1, 0))
            self.assertEqual(
                [(row["word"], row["base_word"], row["variant_number"]) for row in rows],
                [("जड(१)", "जड", 1), ("जड(२)", "जड", 2)],
            )

    def test_brihat_split_definitions_expand_per_sense_abbreviations(self) -> None:
        definition = (
            "१. सधिएका हात्ती, घोडा आदिको आँखामा लगाइने पर्दा। वि. "
            "२. कृष्णपक्षको; कालो; घाम नछिरी अँध्यारो हुने।"
        )

        self.assertEqual(
            json.loads(split_brihat_definitions(definition)),
            [
                {
                    "number": "१.",
                    "text": "सधिएका हात्ती, घोडा आदिको आँखामा लगाइने पर्दा।",
                    "part_of_speech": None,
                },
                {
                    "number": "२.",
                    "text": "कृष्णपक्षको; कालो; घाम नछिरी अँध्यारो हुने।",
                    "part_of_speech": "विशेषण",
                },
            ],
        )


class PragyaImportTests(unittest.TestCase):
    def test_split_definitions_keep_grammar_at_entry_level_only(self) -> None:
        definition = {
            "grammar": "सक्रि.",
            "etymology": "[प्रा. कर+नु]",
            "senses": [
                "१. काम थाल्नु; काममा हात हाल्नु।",
                "२. काम फत्ते पार्ने प्रयासमा लाग्नु।",
            ],
        }

        self.assertEqual(build_part_of_speech(definition), "सकर्मक क्रिया [प्रा. कर+नु]")
        self.assertEqual(
            json.loads(build_split_definitions(definition)),
            [
                {
                    "number": "१.",
                    "text": "काम थाल्नु; काममा हात हाल्नु।",
                    "part_of_speech": None,
                },
                {
                    "number": "२.",
                    "text": "काम फत्ते पार्ने प्रयासमा लाग्नु।",
                    "part_of_speech": None,
                },
            ],
        )

    def test_structured_pragya_duplicate_keeps_first_normalized_row(self) -> None:
        with temp_database() as conn:
            summary = insert_entries(
                conn,
                "kosha-pragya",
                [
                    Entry(
                        word="कल्यान",
                        base_word="कल्यान",
                        variant_number=None,
                        part_of_speech="नाम [कथ्य]",
                        definition="ना. [कथ्य] हे. कल्याण।",
                        split_definitions=json.dumps(
                            [{"number": None, "text": "हे. कल्याण।", "part_of_speech": None}],
                            ensure_ascii=False,
                        ),
                        source_file="source/sabdakosh.json.gz#18536",
                    ),
                    Entry(
                        word="कल्यान",
                        base_word="कल्यान",
                        variant_number=None,
                        part_of_speech="नाम",
                        definition="ना. १. तह परेका खेतका पाटा। २. पानी अड्याउन लगाइएको आली।",
                        split_definitions=json.dumps(
                            [
                                {
                                    "number": "१.",
                                    "text": "तह परेका खेतका पाटा।",
                                    "part_of_speech": None,
                                },
                                {
                                    "number": "२.",
                                    "text": "पानी अड्याउन लगाइएको आली।",
                                    "part_of_speech": None,
                                },
                            ],
                            ensure_ascii=False,
                        ),
                        source_file="source/sabdakosh.json.gz#18537",
                    ),
                ],
            )

            row = lookup_entry(conn, "kosha-pragya", "कल्यान")
            self.assertEqual(summary, (1, 0, 0, 1))
            self.assertEqual(row["part_of_speech"], "नाम [कथ्य]")
            self.assertEqual(row["definition"], "ना. [कथ्य] हे. कल्याण।")

    def test_pragya_part_of_speech_expands_compound_abbreviations(self) -> None:
        self.assertEqual(
            build_part_of_speech({"grammar": "ना./वि.", "etymology": "[सं.]", "senses": ["अर्थ।"]}),
            "नाम/ विशेषण [सं.]",
        )


class temp_database:
    def __enter__(self) -> sqlite3.Connection:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = setup_database(Path(self.temp_dir.name) / "dictionary.db")
        return self.conn

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.conn.close()
        self.temp_dir.cleanup()


def lookup_entry(conn: sqlite3.Connection, dictionary_id: str, word: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT *
        FROM entries
        WHERE dictionary_id = ? AND word = ?
        """,
        (dictionary_id, word),
    ).fetchone()
    if row is None:
        raise AssertionError(f"entry not found: {dictionary_id} {word}")
    return row


if __name__ == "__main__":
    unittest.main()
