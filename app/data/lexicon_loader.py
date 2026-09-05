"""Loads lexicon.json (hand-curated, grouped by root) plus three bulk imports
— lexicon_bulk.json (Wiktionary), freedict_bulk.json (FreeDict/Arabeyes.org),
and places_bulk.json (Wikidata gazetteer: countries/cities/mountains/rivers,
see scripts/fetch_wikidata_places.py + ingest_places.py) — and builds unified
lookup indexes.

Merge priority on a lemma collision: curated > Wiktionary > FreeDict >
places. Curated wins because it carries richer conjugation hints
(mudari3_medial, madi_contraction_vowel) the bulk imports can't derive;
Wiktionary wins over FreeDict because FreeDict's entries are a reversed old
wordlist (no POS, and much of it filtered already — see
scripts/ingest_freedict.py) rather than a dictionary written Arabic-first;
places is last because it's the least descriptive of the four (just a name
+ English gloss, no definitions) and should only fill in places nothing
else already covers.
"""
import json
import os
import re

from ..morphology.normalize import strip_diacritics
from ..morphology.roots import root_key, classify_weakness

_CURATED_PATH = os.path.join(os.path.dirname(__file__), "lexicon.json")
_BULK_PATH = os.path.join(os.path.dirname(__file__), "lexicon_bulk.json")
_FREEDICT_PATH = os.path.join(os.path.dirname(__file__), "freedict_bulk.json")
_PLACES_PATH = os.path.join(os.path.dirname(__file__), "places_bulk.json")
_EXAMPLES_PATH = os.path.join(os.path.dirname(__file__), "examples.json")

_EN_WORD_RE = re.compile(r"[a-zA-Z']+")


class Lexicon:
    def __init__(self, curated_path=_CURATED_PATH, bulk_path=_BULK_PATH, freedict_path=_FREEDICT_PATH, places_path=_PLACES_PATH):
        self.by_root = {}          # root_key -> {"letters":[...], "weakness":str, "entries":[...]}
        self.by_lemma_bare = {}    # bare lemma -> list of (root_key_or_None, entry)
        self.by_english_word = {}  # lowercase english word -> list of (root_key_or_None, entry, gloss)

        seen_bare = set()
        with open(curated_path, encoding="utf-8") as f:
            curated = json.load(f)
        for group in curated["roots"]:
            letters = tuple(group["letters"])
            key = root_key(letters)
            bucket = self.by_root.setdefault(key, {"letters": letters, "weakness": classify_weakness(letters), "entries": []})
            for entry in group["entries"]:
                bucket["entries"].append(entry)
                self._register(key, entry)
                seen_bare.add(strip_diacritics(entry["lemma"]))

        self._load_bulk(bulk_path, seen_bare)
        self._load_bulk(freedict_path, seen_bare)
        self._load_bulk(places_path, seen_bare)
        self._load_pronominal_prepositions()
        self._load_core_function_words()

    def _load_core_function_words(self):
        """A handful of extremely common closed-class words that, unlike most
        of the demonstrative/interrogative pronoun set (هذا, هذه, ذلك, من,
        كيف, أين, متى, ما, هل, أي, كم, ...), are missing from the Wiktionary
        bulk import specifically. Checked against app/data/vocab_gap.json
        (2026-08-30 measurement): هؤلاء alone accounts for 27,617 unmatched
        corpus occurrences; other candidates in this family (هذان, هذين,
        أولئك, إياه, كلا, ...) had zero measured occurrences there and are
        already covered, so aren't added speculatively.
        """
        words = [
            {"lemma": "هَؤُلَاءِ", "pos": "pronoun", "glosses": ["these (demonstrative, plural)"], "source": "curated"},
            # وَيْح/وَيْل are exclamation particles that fuse directly with a
            # pronoun suffix (ويحك "woe to you", ويلهم "woe unto them") — with
            # no bare-form entry at all, that suffix stripping had nowhere to
            # land, so e.g. ويحك fell through to an unrelated false match on
            # ح-ك-ك ("to rub") instead of surfacing "woe" at all.
            {"lemma": "وَيْح", "pos": "particle", "glosses": ["woe! (exclamation of pity/sympathy, mild — often for someone undeserving of blame)"], "source": "curated"},
            {"lemma": "وَيْل", "pos": "particle", "glosses": ["woe! (exclamation of doom/threat, severe — e.g. Quranic \"woe to those who...\")"], "source": "curated"},
        ]
        for entry in words:
            self._register(None, entry)

    def _load_pronominal_prepositions(self):
        """بِ (with/in/by) and لِ (to/for) fused with a pronoun suffix, e.g. به,
        لها. These are closed-class function words, not root-and-pattern
        derived, and their 1-letter preposition can never survive clitic
        stripping (MIN_STEM_LEN=2 rejects a 1-letter remainder) — so without
        an explicit entry they never resolve at all despite being some of the
        most frequent tokens in real text (به alone: ~145K occurrences/20M
        UNPC sentences).
        """
        prepositions = [("ب", "بِ", "with/in/by"), ("ل", "لِ", "to/for")]
        pronouns = [
            ("ه", "هُ", "him/it"), ("ها", "هَا", "her/it"),
            ("هم", "هُمْ", "them (m.)"), ("هن", "هُنَّ", "them (f.)"),
            ("هما", "هُمَا", "them (dual)"),
            ("ك", "كَ", "you"), ("كم", "كُمْ", "you all (m.)"), ("كن", "كُنَّ", "you all (f.)"),
            ("نا", "نَا", "us"), ("ي", "ي", "me"),
        ]
        for prep_bare, prep_dia, prep_gloss in prepositions:
            for suf_bare, suf_dia, suf_gloss in pronouns:
                entry = {
                    "lemma": prep_dia + suf_dia,
                    "pos": "preposition+pronoun",
                    "glosses": [f"{prep_gloss} {suf_gloss}"],
                    "source": "curated",
                }
                self._register(None, entry)

    def _load_bulk(self, path, seen_bare):
        if not path or not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            bulk = json.load(f)
        # Two different homograph entries in the SAME file (e.g. نَعَمْ "yes" and
        # نِعْمَ "how excellent!", both bare "نعم") must NOT dedupe against each
        # other — only against entries from a higher-priority source already
        # loaded. So new bare forms are staged here and merged into seen_bare
        # only after this whole file is done, not as each entry is seen.
        newly_seen = set()
        for entry in bulk.get("entries", []):
            bare = strip_diacritics(entry["lemma"])
            if bare in seen_bare:
                continue
            newly_seen.add(bare)
            root_letters = entry.get("root")
            if root_letters:
                letters = tuple(root_letters)
                key = root_key(letters)
                bucket = self.by_root.setdefault(key, {"letters": letters, "weakness": classify_weakness(letters), "entries": []})
                bucket["entries"].append(entry)
                self._register(key, entry)
            else:
                self._register(None, entry)
        seen_bare.update(newly_seen)

    def _register(self, rk, entry):
        bare = strip_diacritics(entry["lemma"])
        self.by_lemma_bare.setdefault(bare, []).append((rk, entry))
        for gloss in entry.get("glosses", []):
            words = {w.lower() for w in _EN_WORD_RE.findall(gloss)}
            for w in words:
                if len(w) < 2:
                    continue
                self.by_english_word.setdefault(w, []).append((rk, entry, gloss))

    def lookup_root(self, letters):
        return self.by_root.get(root_key(letters))

    def lookup_lemma(self, bare_word):
        return self.by_lemma_bare.get(bare_word, [])

    def lookup_english_word(self, word):
        return self.by_english_word.get(word.lower(), [])


_lexicon = None


def get_lexicon():
    global _lexicon
    if _lexicon is None:
        _lexicon = Lexicon()
    return _lexicon


_examples = None


def get_examples():
    """bare lemma -> list of {ar, en, source} — real sentences from Quran/Tatoeba."""
    global _examples
    if _examples is None:
        if os.path.exists(_EXAMPLES_PATH):
            with open(_EXAMPLES_PATH, encoding="utf-8") as f:
                _examples = json.load(f)
        else:
            _examples = {}
    return _examples
