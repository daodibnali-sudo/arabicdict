"""Build app/data/examples.json: real example sentences matched to lexicon entries.

Sources:
  - Quran (Uthmani text + Sahih International translation, via api.alquran.cloud,
    itself sourced from the Tanzil project — https://tanzil.net). Verse-aligned,
    which is a reliable join key (unlike the OPUS "Tanzil" package, whose Arabic
    side turned out to be tafsir/commentary text misaligned against the literal
    English verse — checked and rejected).
  - Tatoeba (https://tatoeba.org), CC-licensed, human-translated sentence pairs.

Matching: for each Arabic word token in a sentence, run the exact same
clitic/verb-affix stripping used at live-search time and require an EXACT
lemma match (no wazn-pattern guessing) — a false-positive pattern match would
silently attach a sentence to the wrong word with nobody reviewing it, which
is worse than just having fewer examples.

Usage: python3 scripts/ingest_examples.py <tatoeba_dir> <quran_ar.json> <quran_en.json>
"""
import sys
import os
import re
import json
import bz2
import html
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.morphology.normalize import strip_diacritics, fold
from app.morphology.clitics import strip_proclitics, strip_enclitic, strip_verb_affixes, strip_noun_suffix
from app.data.lexicon_loader import get_lexicon

# Matches a whole word INCLUDING diacritics (base letters + combining marks +
# alef wasla), run over the ORIGINAL text — so we can recover the exact
# surface substring that triggered a match, for highlighting in the UI.
TOKEN_WITH_DIACRITICS_RE = re.compile("[\u0621-\u065F\u0670\u0671]+")


def clean_text(text):
    # Unescapes HTML entities (raw in the UNPC dump, e.g. &quot;/&apos;), folds
    # legacy Arabic presentation-form ligatures (seen in the older UN typesetting)
    # back to standard letter sequences, and drops tatweel (justification padding
    # with no semantic value, left over from the original document layout).
    text = unicodedata.normalize("NFKC", html.unescape(text))
    return text.replace("ـ", "")


MAX_EXAMPLES_PER_LEMMA = 12
MAX_SENTENCE_CHARS = 200  # skip pathologically long sentences as examples


def load_quran(ar_path, en_path):
    ar = json.load(open(ar_path, encoding="utf-8"))
    en = json.load(open(en_path, encoding="utf-8"))
    pairs = []
    for surah_ar, surah_en in zip(ar["data"]["surahs"], en["data"]["surahs"]):
        for ayah_ar, ayah_en in zip(surah_ar["ayahs"], surah_en["ayahs"]):
            ar_text = ayah_ar["text"].lstrip("﻿").strip()
            en_text = ayah_en["text"].strip()
            meta = {
                "surah_number": surah_ar["number"],
                "surah_name_ar": surah_ar["name"],
                "surah_name_en": surah_ar["englishName"],
                "ayah_number": ayah_ar["numberInSurah"],
            }
            pairs.append((ar_text, en_text, "quran", meta))
    return pairs


def iter_unpc(ar_path, en_path):
    """Streamed, not materialized — UNPC is ~20M lines, too big to hold as a list."""
    with open(ar_path, encoding="utf-8") as fa, open(en_path, encoding="utf-8") as fe:
        for ar_line, en_line in zip(fa, fe):
            ar_text = clean_text(ar_line.strip())
            en_text = clean_text(en_line.strip())
            if ar_text and en_text:
                yield (ar_text, en_text, "unpc", None)


def load_tatoeba(tatoeba_dir):
    links_path = os.path.join(tatoeba_dir, "ara-eng_links.tsv.bz2")
    ara_path = os.path.join(tatoeba_dir, "ara_sentences.tsv.bz2")
    eng_path = os.path.join(tatoeba_dir, "eng_sentences.tsv.bz2")

    needed_eng_ids = set()
    ar_id_to_en_id = {}
    with bz2.open(links_path, "rt", encoding="utf-8") as f:
        for line in f:
            a, b = line.rstrip("\n").split("\t")
            ar_id_to_en_id[a] = b
            needed_eng_ids.add(b)

    ar_text_by_id = {}
    with bz2.open(ara_path, "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                ar_text_by_id[parts[0]] = parts[2]

    en_text_by_id = {}
    with bz2.open(eng_path, "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t", 2)
            if len(parts) >= 3 and parts[0] in needed_eng_ids:
                en_text_by_id[parts[0]] = parts[2]

    pairs = []
    for ar_id, en_id in ar_id_to_en_id.items():
        ar_text = ar_text_by_id.get(ar_id)
        en_text = en_text_by_id.get(en_id)
        if ar_text and en_text:
            pairs.append((ar_text, en_text, "tatoeba", None))
    return pairs


def _best_match_pass(word, lexicon):
    best = None
    for proclitic_label, rem1 in strip_proclitics(word):
        for enclitic_label, rem2 in strip_enclitic(rem1):
            for stem, verb_features in strip_verb_affixes(rem2):
                base_stripped = len(proclitic_label.replace("+", "")) + len(enclitic_label) + (len(rem2) - len(stem))
                for rk, entry in lexicon.lookup_lemma(stem):
                    score = -base_stripped
                    if best is None or score > best[0]:
                        best = (score, entry["lemma"])
                if not verb_features:
                    for suffix_label, noun_stem in strip_noun_suffix(stem):
                        for rk, entry in lexicon.lookup_lemma(noun_stem):
                            score = -(base_stripped + len(stem) - len(noun_stem))
                            if best is None or score > best[0]:
                                best = (score, entry["lemma"])
    return best[1] if best else None


def best_match(word, lexicon):
    """Same pipeline as live search (clitics + verb affixes + noun plural/nisba
    stripping), with a fuzzy-fold fallback (ى/أ/إ/آ/ة variants) for the same
    reason analyze() has one: real corpus text isn't always written with the
    exact letter variant our lexicon happens to store.
    """
    match = _best_match_pass(word, lexicon)
    if match is not None:
        return match
    folded = fold(word)
    if folded != word:
        return _best_match_pass(folded, lexicon)
    return None


# Once a lemma already has this many candidate examples, stop appending more —
# we only keep the shortest MAX_EXAMPLES_PER_LEMMA at the end anyway, and without
# this a common word like "في" would accumulate millions of hits across UNPC.
CANDIDATE_CAP_PER_LEMMA = 25


CANDIDATES_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "data", "examples_candidates.json")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "data", "examples.json")


def trim(examples):
    """Round-robin across sources (shortest-first within each) so a common word
    shows several examples AND every source that matched gets represented —
    otherwise Tatoeba's abundant short sentences silently crowd out every other
    source for any common word, and volume alone doesn't fix that on its own."""
    trimmed = {}
    for bare_lemma, by_source in examples.items():
        for lst in by_source.values():
            lst.sort(key=lambda e: e["len"])

        sources = list(by_source.keys())
        picked = []  # list of (source, candidate)
        idx = 0
        while len(picked) < MAX_EXAMPLES_PER_LEMMA and any(by_source[s] for s in sources):
            s = sources[idx % len(sources)]
            if by_source[s]:
                picked.append((s, by_source[s].pop(0)))
            idx += 1

        out = []
        for s, e in picked:
            item = {"ar": e["ar"], "en": e["en"], "source": s, "matched": e["matched"]}
            for k in ("surah_number", "surah_name_ar", "surah_name_en", "ayah_number"):
                if k in e:
                    item[k] = e[k]
            out.append(item)
        trimmed[bare_lemma] = out
    return trimmed


def scan(tatoeba_dir, quran_ar, quran_en, unpc_ar=None, unpc_en=None):
    """The expensive step (rescans every corpus) — writes the full candidate pool
    (up to CANDIDATE_CAP_PER_LEMMA per lemma, across all sources) to disk so the
    selection strategy in trim() can be revised later without rescanning."""
    lexicon = get_lexicon()
    examples = {}

    def all_pairs():
        yield from load_quran(quran_ar, quran_en)
        yield from load_tatoeba(tatoeba_dir)
        if unpc_ar and unpc_en:
            yield from iter_unpc(unpc_ar, unpc_en)

    i = 0
    for ar_text, en_text, source, meta in all_pairs():
        i += 1
        if len(ar_text) > MAX_SENTENCE_CHARS:
            continue
        seen = set()
        for tok_orig in TOKEN_WITH_DIACRITICS_RE.findall(ar_text):
            tok_bare = strip_diacritics(tok_orig)
            if len(tok_bare) < 2:
                continue
            lemma = best_match(tok_bare, lexicon)
            if lemma is None:
                continue
            bare_lemma = strip_diacritics(lemma)
            if bare_lemma in seen:
                continue
            seen.add(bare_lemma)
            # Capped PER SOURCE, not shared across sources — sources are scanned in a
            # fixed order (Quran, then Tatoeba, then UNPC), so a shared cap meant a
            # word extremely frequent in Quran (e.g. "book") filled the whole cap
            # before Tatoeba/UNPC ever got a turn, silently starving them out.
            bucket = examples.setdefault(bare_lemma, {}).setdefault(source, [])
            if len(bucket) >= CANDIDATE_CAP_PER_LEMMA:
                continue
            candidate = {"ar": ar_text, "en": en_text, "len": len(ar_text), "matched": tok_orig}
            if meta:
                candidate.update(meta)
            bucket.append(candidate)
        if i % 500000 == 0:
            print(f"  processed {i}, {len(examples)} lemmas matched so far")

    with open(CANDIDATES_PATH, "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False)
    print(f"scanned {i} sentence pairs, {len(examples)} lemmas -> {CANDIDATES_PATH}")
    return examples


def main(tatoeba_dir=None, quran_ar=None, quran_en=None, unpc_ar=None, unpc_en=None, trim_only=False):
    if trim_only:
        with open(CANDIDATES_PATH, encoding="utf-8") as f:
            examples = json.load(f)
    else:
        examples = scan(tatoeba_dir, quran_ar, quran_en, unpc_ar, unpc_en)

    trimmed = trim(examples)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False)
    print(f"matched examples for {len(trimmed)} lemmas -> {OUT_PATH}")


if __name__ == "__main__":
    kwargs = {}
    positional = []
    for a in sys.argv[1:]:
        if a == "--trim-only":
            kwargs["trim_only"] = True
        else:
            positional.append(a)
    main(*positional, **kwargs)
