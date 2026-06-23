"""Generated romanized search aliases for Nepali Devanagari headwords."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from shabdakosha.text import normalize_text


GENERATOR_VERSION = "iast-casual-nepali-v1"
SOURCE_SCHEME = "IAST"
MAX_ALIASES_PER_WORD = 24
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
VARIANT_SUFFIX_RE = re.compile(r"\([०-९]+\)$")
NON_ROMAN_RE = re.compile(r"[^a-z0-9]+")

VIRAMA = "्"
NUKTA = "़"

INDEPENDENT_VOWELS = {
    "अ": "a",
    "आ": "ā",
    "इ": "i",
    "ई": "ī",
    "उ": "u",
    "ऊ": "ū",
    "ऋ": "ṛ",
    "ॠ": "ṝ",
    "ऌ": "ḷ",
    "ॡ": "ḹ",
    "ए": "e",
    "ऐ": "ai",
    "ओ": "o",
    "औ": "au",
}

VOWEL_SIGNS = {
    "ा": "ā",
    "ि": "i",
    "ी": "ī",
    "ु": "u",
    "ू": "ū",
    "ृ": "ṛ",
    "ॄ": "ṝ",
    "ॢ": "ḷ",
    "ॣ": "ḹ",
    "े": "e",
    "ै": "ai",
    "ो": "o",
    "ौ": "au",
}

CONSONANTS = {
    "क": "k",
    "ख": "kh",
    "ग": "g",
    "घ": "gh",
    "ङ": "ṅ",
    "च": "c",
    "छ": "ch",
    "ज": "j",
    "झ": "jh",
    "ञ": "ñ",
    "ट": "ṭ",
    "ठ": "ṭh",
    "ड": "ḍ",
    "ढ": "ḍh",
    "ण": "ṇ",
    "त": "t",
    "थ": "th",
    "द": "d",
    "ध": "dh",
    "न": "n",
    "प": "p",
    "फ": "ph",
    "ब": "b",
    "भ": "bh",
    "म": "m",
    "य": "y",
    "र": "r",
    "ल": "l",
    "व": "v",
    "श": "ś",
    "ष": "ṣ",
    "स": "s",
    "ह": "h",
    "ळ": "ḷ",
    "क्ष": "kṣ",
    "ज्ञ": "jñ",
}

NUKTA_CONSONANTS = {
    "क़": "q",
    "ख़": "ḵẖ",
    "ग़": "ġ",
    "ज़": "z",
    "ड़": "ṛ",
    "ढ़": "ṛh",
    "फ़": "f",
    "य़": "ẏ",
    "क़": "q",
    "ख़": "ḵẖ",
    "ग़": "ġ",
    "ज़": "z",
    "ड़": "ṛ",
    "ढ़": "ṛh",
    "फ़": "f",
    "य़": "ẏ",
}

SIGNS = {
    "ं": "ṃ",
    "ँ": "m̐",
    "ः": "ḥ",
    "ऽ": "'",
    "।": ".",
    "॥": ".",
    "ॐ": "oṃ",
}

DIGITS = {
    "०": "0",
    "१": "1",
    "२": "2",
    "३": "3",
    "४": "4",
    "५": "5",
    "६": "6",
    "७": "7",
    "८": "8",
    "९": "9",
}

CASUAL_VOWELS = {
    "a": (("a", 0),),
    "ā": (("aa", 0), ("a", 2)),
    "i": (("i", 0),),
    "ī": (("i", 0), ("ee", 5), ("ii", 8)),
    "u": (("u", 0),),
    "ū": (("u", 0), ("oo", 5), ("uu", 8)),
    "ṛ": (("ri", 0), ("r", 8)),
    "ṝ": (("ri", 4),),
    "ḷ": (("lri", 4),),
    "ḹ": (("lri", 6),),
    "e": (("e", 0),),
    "ai": (("ai", 0),),
    "o": (("o", 0),),
    "au": (("au", 0),),
}

CASUAL_CONSONANTS = {
    "क": (("k", 0),),
    "ख": (("kh", 0),),
    "ग": (("g", 0),),
    "घ": (("gh", 0),),
    "ङ": (("ng", 0), ("n", 4)),
    "च": (("ch", 0), ("c", 8)),
    "छ": (("chh", 0), ("ch", 6)),
    "ज": (("j", 0),),
    "झ": (("jh", 0),),
    "ञ": (("ny", 0), ("n", 4)),
    "ट": (("t", 0),),
    "ठ": (("th", 0),),
    "ड": (("d", 0),),
    "ढ": (("dh", 0),),
    "ण": (("n", 0),),
    "त": (("t", 0),),
    "थ": (("th", 0),),
    "द": (("d", 0),),
    "ध": (("dh", 0),),
    "न": (("n", 0),),
    "प": (("p", 0),),
    "फ": (("ph", 0), ("f", 3)),
    "ब": (("b", 0),),
    "भ": (("bh", 0),),
    "म": (("m", 0),),
    "य": (("y", 0),),
    "र": (("r", 0),),
    "ल": (("l", 0),),
    "व": (("v", 0), ("w", 2), ("b", 6)),
    "श": (("sh", 0), ("s", 3)),
    "ष": (("sh", 0), ("s", 3)),
    "स": (("s", 0), ("sh", 5)),
    "ह": (("h", 0),),
    "ळ": (("l", 0),),
}

CASUAL_NUKTA_CONSONANTS = {
    "क़": (("q", 0), ("k", 5)),
    "ख़": (("kh", 0),),
    "ग़": (("g", 0),),
    "ज़": (("z", 0), ("j", 6)),
    "ड़": (("d", 0), ("r", 5)),
    "ढ़": (("dh", 0), ("rh", 5)),
    "फ़": (("f", 0), ("ph", 4)),
    "य़": (("y", 0),),
    "क़": (("q", 0), ("k", 5)),
    "ख़": (("kh", 0),),
    "ग़": (("g", 0),),
    "ज़": (("z", 0), ("j", 6)),
    "ड़": (("d", 0), ("r", 5)),
    "ढ़": (("dh", 0), ("rh", 5)),
    "फ़": (("f", 0), ("ph", 4)),
    "य़": (("y", 0),),
}

CASUAL_SIGNS = {
    "ं": (("m", 0), ("n", 1), ("ng", 4)),
    "ँ": (("m", 0), ("n", 2)),
    "ः": (("h", 4), ("", 8)),
    "ऽ": (("", 0),),
}


@dataclass(frozen=True)
class RomanAlias:
    text: str
    kind: str
    weight: int
    generator_version: str = GENERATOR_VERSION
    source_scheme: str = SOURCE_SCHEME


def strip_variant_suffix(word: str) -> str:
    return VARIANT_SUFFIX_RE.sub("", word).strip()


def has_devanagari(word: str) -> bool:
    return bool(DEVANAGARI_RE.search(word))


def normalize_roman_alias(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = NON_ROMAN_RE.sub(" ", normalized.lower())
    return " ".join(normalized.split())


def joined_alias(value: str) -> str:
    return value.replace(" ", "")


def transliterate_iast(word: str) -> str:
    text = normalize_text(word) or ""
    output: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""

        if char in CONSONANTS or char + next_char in NUKTA_CONSONANTS:
            consonant_key = char
            consonant = CONSONANTS.get(char)
            if char + next_char in NUKTA_CONSONANTS:
                consonant_key = char + next_char
                consonant = NUKTA_CONSONANTS[consonant_key]
                index += 1

            lookahead = text[index + 1] if index + 1 < len(text) else ""
            output.append(consonant or "")
            if lookahead in VOWEL_SIGNS:
                output.append(VOWEL_SIGNS[lookahead])
                index += 1
            elif lookahead == VIRAMA:
                index += 1
            elif consonant_key:
                output.append("a")
        elif char in INDEPENDENT_VOWELS:
            output.append(INDEPENDENT_VOWELS[char])
        elif char in VOWEL_SIGNS:
            output.append(VOWEL_SIGNS[char])
        elif char in SIGNS:
            output.append(SIGNS[char])
        elif char in DIGITS:
            output.append(DIGITS[char])
        elif char == NUKTA:
            pass
        else:
            output.append(char)
        index += 1
    return "".join(output)


def iast_ascii_long(iast: str) -> str:
    replacements = {
        "ā": "aa",
        "ī": "ii",
        "ū": "uu",
        "ṛ": "ri",
        "ṝ": "ri",
        "ḷ": "lri",
        "ḹ": "lri",
        "ṅ": "ng",
        "ñ": "ny",
        "ṇ": "n",
        "ṭ": "t",
        "ḍ": "d",
        "ś": "sh",
        "ṣ": "sh",
        "ṃ": "m",
        "ḥ": "h",
    }
    text = iast
    for source, replacement in replacements.items():
        text = text.replace(source, replacement)
    return normalize_roman_alias(text)


def _casual_units(word: str) -> list[tuple[tuple[str, int], ...]]:
    text = normalize_text(word) or ""
    units: list[tuple[tuple[str, int], ...]] = []
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""

        consonant_options = CASUAL_CONSONANTS.get(char)
        if char + next_char in CASUAL_NUKTA_CONSONANTS:
            consonant_options = CASUAL_NUKTA_CONSONANTS[char + next_char]
            index += 1

        if consonant_options:
            units.append(consonant_options)
            lookahead = text[index + 1] if index + 1 < len(text) else ""
            if lookahead in VOWEL_SIGNS:
                units.append(CASUAL_VOWELS[VOWEL_SIGNS[lookahead]])
                index += 1
            elif lookahead == VIRAMA:
                index += 1
            else:
                units.append(CASUAL_VOWELS["a"])
        elif char in INDEPENDENT_VOWELS:
            units.append(CASUAL_VOWELS[INDEPENDENT_VOWELS[char]])
        elif char in VOWEL_SIGNS:
            units.append(CASUAL_VOWELS[VOWEL_SIGNS[char]])
        elif char in CASUAL_SIGNS:
            units.append(CASUAL_SIGNS[char])
        elif char in DIGITS:
            units.append(((DIGITS[char], 0),))
        elif char.isspace():
            units.append(((" ", 0),))
        elif char in "-_/":
            units.append(((" ", 2),))
        elif char == NUKTA:
            pass
        elif char.isascii() and char.isalnum():
            units.append(((char.lower(), 0),))
        index += 1
    return units


def _expand_units(units: list[tuple[tuple[str, int], ...]], beam_size: int = 96) -> list[tuple[str, int]]:
    candidates = [("", 0)]
    for unit in units:
        next_candidates: dict[str, int] = {}
        for prefix, prefix_penalty in candidates:
            for text, penalty in unit:
                candidate = prefix + text
                total_penalty = prefix_penalty + penalty
                if candidate not in next_candidates or total_penalty < next_candidates[candidate]:
                    next_candidates[candidate] = total_penalty
        candidates = sorted(next_candidates.items(), key=lambda item: (item[1], item[0]))[:beam_size]
    return candidates


def _with_final_a_drop(candidates: list[tuple[str, int]]) -> list[tuple[str, int]]:
    expanded = list(candidates)
    for text, penalty in candidates:
        if len(text) > 2 and text.endswith("a"):
            expanded.append((text[:-1], penalty + 2))
    return expanded


def roman_aliases(word: str, max_aliases: int = MAX_ALIASES_PER_WORD) -> list[RomanAlias]:
    source_word = strip_variant_suffix(normalize_text(word) or "")
    if not source_word or "/" in source_word or not has_devanagari(source_word):
        return []

    aliases: dict[str, RomanAlias] = {}

    def add(text: str, kind: str, weight: int) -> None:
        normalized = normalize_roman_alias(text)
        if not normalized:
            return
        existing = aliases.get(normalized)
        alias = RomanAlias(normalized, kind, max(1, min(100, weight)))
        if existing is None or alias.weight > existing.weight:
            aliases[normalized] = alias

        joined = joined_alias(normalized)
        if joined != normalized:
            joined_existing = aliases.get(joined)
            joined_alias_item = RomanAlias(joined, f"{kind}_joined", max(1, min(100, weight - 4)))
            if joined_existing is None or joined_alias_item.weight > joined_existing.weight:
                aliases[joined] = joined_alias_item

    iast = transliterate_iast(source_word)
    add(iast, "iast", 100)
    add(iast_ascii_long(iast), "iast_ascii", 94)
    add(normalize_roman_alias(iast), "iast_ascii_folded", 92)

    casual_candidates = _with_final_a_drop(_expand_units(_casual_units(source_word)))
    for text, penalty in casual_candidates:
        add(text, "casual", 100 - penalty)

    return sorted(
        aliases.values(),
        key=lambda alias: (-alias.weight, alias.kind, alias.text),
    )[:max_aliases]
