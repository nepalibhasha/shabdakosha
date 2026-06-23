import unittest

from shabdakosha.headword_aliases import generate_slash_headword_aliases


def aliases_for(headword: str) -> list[str]:
    return [alias.alias for alias in generate_slash_headword_aliases(headword)]


class SlashHeadwordAliasTests(unittest.TestCase):
    def test_full_alternates_with_shared_prefix_are_not_prefixed_again(self) -> None:
        self.assertEqual(aliases_for("बाइबल/बाइबिल"), ["बाइबल", "बाइबिल"])
        self.assertEqual(aliases_for("बसोबास/बसोबासो"), ["बसोबास", "बसोबासो"])
        self.assertEqual(aliases_for("लोलाक्षिका/लोलाक्षी"), ["लोलाक्षिका", "लोलाक्षी"])

    def test_compact_suffix_alternates_borrow_left_prefix(self) -> None:
        self.assertEqual(aliases_for("बडाबा/बाबु"), ["बडाबा", "बडाबाबु"])
        self.assertEqual(aliases_for("भातभान्छा/भान्सा"), ["भातभान्छा", "भातभान्सा"])


if __name__ == "__main__":
    unittest.main()
