"""Generate searchable aliases for compact dictionary headword notation."""

from __future__ import annotations

import re
from dataclasses import dataclass


DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


MANUAL_SLASH_HEADWORD_ALIASES: dict[str, tuple[str, ...]] = {
    "आजकल/काल": ("आजकल", "आजकाल"),
    "गलाइनु/नो": ("गलाइनु", "गलाइनो"),
    "गलाइन्/नो": ("गलाइन्", "गलाइन्नो"),
    "गाँठकोपी/गोभी": ("गाँठकोपी", "गाँठगोभी"),
    "गाँठकोपी/गोमी": ("गाँठकोपी", "गाँठगोमी"),
    "जिउँदोपन/पना": ("जिउँदोपन", "जिउँदोपना"),
    "दर्जावाल/वाला": ("दर्जावाल", "दर्जावाला"),
    "दर्बावाल/वाला": ("दर्बावाल", "दर्बावाला"),
    "दुईदुना/दुने": ("दुईदुना", "दुईदुने"),
    "दुइँदुना/दुने": ("दुइँदुना", "दुइँदुने"),
    "प्रौढता/त्व": ("प्रौढता", "प्रौढत्व"),
    "शीर्णता/त्व": ("शीर्णता", "शीर्णत्व"),
    "अनुशासनप्रिय/प्रेमी": ("अनुशासनप्रिय", "अनुशासनप्रेमी"),
    "अनुशीलनकर्ता/कारी": ("अनुशीलनकर्ता", "अनुशीलनकारी"),
    "औषधि/औषधी विज्ञान": ("औषधि विज्ञान", "औषधी विज्ञान"),
    "कठैबरा/बरी/बरै": ("कठैबरा", "कठैबरी", "कठैबरै"),
    "कपुरपत्ती/पाती": ("कपुरपत्ती", "कपुरपाती"),
    "कपुरी/कपुरे आँप": ("कपुरी आँप", "कपुरे आँप"),
    "चिठी/चिठ्ठी पुर्जी": ("चिठीपुर्जी", "चिठ्ठीपुर्जी"),
}


@dataclass(frozen=True)
class HeadwordAlias:
    alias: str
    alias_type: str


def _has_devanagari(value: str) -> bool:
    return bool(DEVANAGARI_RE.search(value))


def _common_prefix_length(left: str, part: str) -> int:
    common_prefix_length = 0
    for left_char, part_char in zip(left, part):
        if left_char != part_char:
            break
        common_prefix_length += 1
    return common_prefix_length


def part_looks_like_full_alternate(left: str, part: str) -> bool:
    common_prefix_length = _common_prefix_length(left, part)
    if not left or not part:
        return False
    return common_prefix_length >= 3 and common_prefix_length / min(len(left), len(part)) >= 0.5


def _replace_from_shared_initial(left: str, part: str) -> str | None:
    first = part[0] if part else ""
    if not first:
        return None

    if part_looks_like_full_alternate(left, part):
        return part

    index = left.rfind(first)
    if index < 0:
        return None
    return left[:index] + part


def generate_slash_headword_aliases(headword: str) -> list[HeadwordAlias]:
    """Expand slash headwords such as ``आजकल/काल`` into lookup aliases."""
    if "/" not in headword:
        return []

    manual_aliases = MANUAL_SLASH_HEADWORD_ALIASES.get(headword)
    if manual_aliases is not None:
        return [HeadwordAlias(alias, "manual") for alias in manual_aliases]

    parts = [part.strip() for part in headword.split("/") if part.strip()]
    if len(parts) < 2:
        return []

    aliases: list[HeadwordAlias] = []
    seen = {headword}

    def add(alias: str | None, alias_type: str) -> None:
        if not alias:
            return
        alias = alias.strip()
        if not alias or alias in seen or "/" in alias or not _has_devanagari(alias):
            return
        seen.add(alias)
        aliases.append(HeadwordAlias(alias, alias_type))

    left = parts[0]
    add(left, "slash_left")
    phrase_prefix = left.rsplit(" ", 1)[0] + " " if " " in left else ""

    for part in parts[1:]:
        part_words = part.split()

        if part == "त्व" and left.endswith("ता"):
            add(left[: -len("ता")] + "त्व", "ta_tva")
            continue

        if phrase_prefix and " " not in part:
            add(phrase_prefix + part, "phrase_prefix")

        if " " not in left and len(part_words) >= 2:
            tail = " ".join(part_words[1:])
            add(f"{left} {tail}", "phrase_tail")
            add(f"{left}{tail.replace(' ', '')}", "joined_phrase_tail")

        borrowed = _replace_from_shared_initial(left, part)
        if borrowed:
            add(borrowed, "shared_initial")
            add(borrowed.replace(" ", ""), "joined_shared_initial")
        elif not phrase_prefix and " " not in part:
            add(part, "literal_part")

    return aliases
