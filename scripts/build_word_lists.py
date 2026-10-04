#!/usr/bin/env python3
"""Build the frozen English word lists that the word games load from ``textarena/utils/data/``.

The sources are the UK and US Hunspell dictionaries in ``scripts/word_list_sources/`` (``en_GB.dic`` and
``en_US.dic`` share the affix rules in ``en.aff``) and ``textarena/utils/data/blocked_words.txt``. Each list
holds one lowercase word per line, sorted:

- ``english_words.txt``: every word either dictionary accepts, i.e. every entry with its affix rules applied.
- ``headwords.txt``: base entries of three or more letters that carry at least one flag. The dictionaries
  list abbreviations and irregular inflected forms without flags, so this drops them (along with a few base
  words that never inflect).
- ``common_words.txt``: headwords of three to eight letters that both dictionaries list and that take a
  regular inflection (plural, -ed, -ing, -er or -est), which leaves out long rare words and spellings that
  differ between British and American English.

Only words made of the letters a-z are kept, so proper nouns, possessives and entries with digits are
dropped, and of the single letters only "a" and "i" count as words. Blocked words and the entries the
dictionaries flag as offensive (``!``) are never headwords or common words, but stay in ``english_words.txt``.

Usage:
    python scripts/build_word_lists.py          # rewrite the lists
    python scripts/build_word_lists.py --check  # exit 1 if a list is stale
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "scripts" / "word_list_sources"
DATA = ROOT / "textarena" / "utils" / "data"

WORD = re.compile(r"[a-z]+")
SINGLE_LETTER_WORDS = {"a", "i"}
# en.aff flags of the regular inflections: plural (S), past tense (D), -ing (G), comparative (R), superlative (T).
INFLECTION_FLAGS = frozenset("SDGRT")


class Rule(NamedTuple):
    strip: str
    affix: str
    condition: "re.Pattern[str]"
    cross_product: bool


Rules = Dict[str, List[Rule]]


def read_affixes(path: Path) -> Tuple[Rules, Rules]:
    """The prefix and suffix rules of a Hunspell .aff file, keyed by flag.

    Each class is a header ``PFX|SFX <flag> <Y|N> <count>`` followed by ``count`` rules
    ``PFX|SFX <flag> <strip> <affix>[/flags] <condition>``, where ``0`` is an empty strip or affix and
    ``Y`` lets the class combine with classes of the other kind that also have ``Y``.
    """
    rules: Dict[str, Rules] = {"PFX": defaultdict(list), "SFX": defaultdict(list)}
    pending: Dict[Tuple[str, str], Tuple[bool, int]] = {}  # (kind, flag) -> (cross product, rules left to read)
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        fields = line.split()
        if not fields or fields[0] not in rules:
            continue
        kind, flag = fields[0], fields[1]
        cross_product, remaining = pending.get((kind, flag), (False, 0))
        if remaining == 0:
            if len(fields) != 4 or fields[2] not in ("Y", "N") or not fields[3].isdigit():
                raise ValueError(f"{path.name}:{number}: expected a class header, got {line!r}")
            pending[(kind, flag)] = (fields[2] == "Y", int(fields[3]))
            continue
        pending[(kind, flag)] = (cross_product, remaining - 1)
        strip, affix = fields[2], fields[3]
        condition = fields[4] if len(fields) > 4 else "."
        affix, _, continuation = affix.partition("/")
        if continuation:
            raise ValueError(f"{path.name}:{number}: continuation classes are not supported")
        # The condition uses regular-expression syntax ([abc], [^abc], ., literals) and must match the end
        # of the word for a suffix and its start for a prefix.
        pattern = re.compile(f"(?:{condition})$" if kind == "SFX" else condition)
        rules[kind][flag].append(
            Rule("" if strip == "0" else strip, "" if affix == "0" else affix, pattern, cross_product)
        )
    unfinished = sorted(f"{kind} {flag}" for (kind, flag), (_, remaining) in pending.items() if remaining)
    if unfinished:
        raise ValueError(f"{path.name}: classes with missing rules: {', '.join(unfinished)}")
    return rules["PFX"], rules["SFX"]


def read_dictionary(path: Path) -> Dict[str, Set[str]]:
    """Map every entry of a Hunspell .dic file to its flags, merged when a word is listed twice."""
    entries: Dict[str, Set[str]] = defaultdict(set)
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:  # the first line is the entry count
        if line.strip():
            word, _, flags = line.split()[0].partition("/")
            entries[word].update(flags)
    return entries


def add_suffix(rule: Rule, word: str) -> Optional[str]:
    if len(word) > len(rule.strip) and word.endswith(rule.strip) and rule.condition.search(word):
        return word[: len(word) - len(rule.strip)] + rule.affix
    return None


def add_prefix(rule: Rule, word: str) -> Optional[str]:
    if len(word) > len(rule.strip) and word.startswith(rule.strip) and rule.condition.match(word):
        return rule.affix + word[len(rule.strip):]
    return None


def expand(word: str, flags: Set[str], prefixes: Rules, suffixes: Rules) -> Set[str]:
    """The entry with every form its flags derive."""
    forms = {word}
    combinable = [word]  # forms that cross-product prefixes apply to
    for flag in flags:
        for rule in suffixes.get(flag, ()):
            form = add_suffix(rule, word)
            if form is not None:
                forms.add(form)
                if rule.cross_product:
                    combinable.append(form)
    for flag in flags:
        for rule in prefixes.get(flag, ()):
            for base in combinable if rule.cross_product else [word]:
                form = add_prefix(rule, base)
                if form is not None:
                    forms.add(form)
    return forms


def build() -> Dict[str, str]:
    """The text of every frozen list, keyed by file name."""
    prefixes, suffixes = read_affixes(SOURCES / "en.aff")
    uk, us = read_dictionary(SOURCES / "en_GB.dic"), read_dictionary(SOURCES / "en_US.dic")
    blocked = {
        line.strip()
        for line in (DATA / "blocked_words.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }

    forms = set()
    for entries in (uk, us):
        for word, flags in entries.items():
            forms |= expand(word, flags, prefixes, suffixes)
    words = {form for form in forms if WORD.fullmatch(form) and (len(form) > 1 or form in SINGLE_LETTER_WORDS)}

    excluded = blocked | {word for entries in (uk, us) for word, flags in entries.items() if "!" in flags}
    uk_base = {word: flags for word, flags in uk.items() if WORD.fullmatch(word) and word not in excluded}
    us_base = {word: flags for word, flags in us.items() if WORD.fullmatch(word) and word not in excluded}
    headwords = {
        word
        for word in uk_base.keys() | us_base.keys()
        if len(word) >= 3 and uk_base.get(word, set()) | us_base.get(word, set())
    }
    common_words = {
        word
        for word in uk_base.keys() & us_base.keys()
        if 3 <= len(word) <= 8 and (uk_base[word] | us_base[word]) & INFLECTION_FLAGS
    }
    lists = {"english_words.txt": words, "headwords.txt": headwords, "common_words.txt": common_words}
    return {name: "".join(f"{word}\n" for word in sorted(words)) for name, words in lists.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the frozen English word lists in textarena/utils/data/.")
    parser.add_argument("--check", action="store_true", help="exit 1 if a list is stale instead of rewriting it")
    args = parser.parse_args()
    stale = []
    for name, text in build().items():
        path = DATA / name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
            continue
        path.write_text(text, encoding="utf-8", newline="\n")
        count = text.count("\n")
        print(f"{path.relative_to(ROOT)}: {count} words")
    if stale:
        print(f"Stale word lists: {', '.join(stale)}. Run: python scripts/build_word_lists.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
