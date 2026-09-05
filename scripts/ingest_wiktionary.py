"""One-off ingestion: kaikki.org's wiktextract JSONL (English Wiktionary's
Arabic-language coverage) -> app/data/lexicon_bulk.json.

Source: https://kaikki.org/dictionary/Arabic/kaikki.org-dictionary-Arabic.jsonl
License: Wiktionary content is CC-BY-SA — this data is redistributed/used
under that license; attribution to Wiktionary/kaikki.org must ship with any
public build using lexicon_bulk.json.

Usage: python3 scripts/ingest_wiktionary.py /path/to/wiktionary_ar.jsonl
"""
import sys
import os
import re
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.morphology.normalize import strip_diacritics
from app.morphology.patterns import match_stem

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
# Ordered longest-alternative-first so e.g. "VIII" isn't cut short by "V".
ARG1_RE = re.compile(r"^(VIII|VII|III|VI|IV|IX|II|I|V|X)(?:/([aui])~([aui]))?")
MAX_GLOSSES = 4
MAX_SYN = 6
GLOSS_MAXLEN = 160


def canonical_lemma(entry):
    for f in entry.get("forms", []):
        if "canonical" in f.get("tags", []):
            return f["form"]
    return entry.get("word", "")


def extract_glosses(entry):
    out = []
    for sense in entry.get("senses", []):
        glosses = sense.get("glosses")
        if not glosses:
            continue
        g = glosses[0].strip()
        if len(g) > GLOSS_MAXLEN:
            g = g[:GLOSS_MAXLEN].rsplit(" ", 1)[0] + "…"
        if g and g not in out:
            out.append(g)
        if len(out) >= MAX_GLOSSES:
            break
    return out


def extract_syn_ant(entry, key):
    out = []
    for sense in entry.get("senses", []):
        for item in sense.get(key, []) or []:
            w = item.get("word")
            if w and w not in out:
                out.append(w)
        if len(out) >= MAX_SYN:
            break
    return out[:MAX_SYN]


def extract_plural(entry):
    for f in entry.get("forms", []):
        tags = f.get("tags", [])
        if "plural" in tags and "romanization" not in tags:
            return f["form"]
    return None


def extract_rootbox(entry):
    for t in entry.get("etymology_templates", []):
        if t.get("name") == "ar-rootbox":
            letters = t.get("args", {}).get("1", "").split()
            if len(letters) == 3:
                return tuple(letters)
    return None


def is_plausible_root(root):
    # ى/ا/ة are never true root radicals — a guess containing one means a heuristic
    # misfired (an irregular verb like رأى, or a feminine ة read as a 3rd radical),
    # not that we found a real root.
    return all(c not in ("ا", "ى", "ة") for c in root)


def guess_root_from_nonpast(entry):
    # The principal-part listing (tags == exactly ["non-past"], no "source" key) is the
    # bare 3ms citation form. Every other conjugated present-tense form in the full table
    # ALSO carries the "non-past" tag, so matching on the tag alone would walk into e.g.
    # a plural ("...ون") form and misread its person/number suffix as the root.
    for f in entry.get("forms", []):
        if f.get("tags") == ["non-past"] and "source" not in f:
            bare = strip_diacritics(f["form"])
            if bare.startswith("ي") and len(bare) > 1:
                stem = bare[1:]
                for m in match_stem(stem):
                    if len(m.root) == 3 and is_plausible_root(m.root):
                        return m.root
    return None


def guess_root_from_lemma(bare_lemma):
    # ة (feminine marker) is never a root letter — strip it before pattern-matching,
    # or e.g. a Form-V-shaped noun like تقية would read its ة as the 3rd radical.
    if bare_lemma.endswith("ة") and len(bare_lemma) > 3:
        bare_lemma = bare_lemma[:-1]
    for m in match_stem(bare_lemma):
        if len(m.root) == 3 and is_plausible_root(m.root):
            return m.root
    return None


def extract_form_and_vowel(entry):
    for t in entry.get("head_templates", []):
        if t.get("name") == "ar-verb":
            arg1 = t.get("args", {}).get("1", "")
            m = ARG1_RE.match(arg1)
            if m:
                form = ROMAN.get(m.group(1))
                vowel = m.group(3)
                return form, vowel
    return None, None


def is_real_entry(entry):
    return any(s.get("glosses") for s in entry.get("senses", []))


def convert(entry):
    pos = entry.get("pos")
    ht_name = entry["head_templates"][0]["name"] if entry.get("head_templates") else None
    if ht_name and ht_name.endswith(" form"):
        return None
    if not is_real_entry(entry):
        return None

    lemma = canonical_lemma(entry)
    bare = strip_diacritics(lemma)
    glosses = extract_glosses(entry)
    if not glosses:
        return None

    root = extract_rootbox(entry)
    form, vowel = (None, None)
    if pos == "verb":
        form, vowel = extract_form_and_vowel(entry)
        if root is None:
            root = guess_root_from_nonpast(entry)
    if root is None and pos in ("noun", "adj"):
        root = guess_root_from_lemma(bare)
    if root is not None and len(root) != 3:
        root = None

    out = {
        "lemma": lemma,
        "pos": pos,
        "glosses": glosses,
        "source": "wiktionary",
    }
    if root:
        out["root"] = list(root)
    if pos == "verb" and form:
        out["form"] = form
        out["mudari3_vowel"] = vowel or "u"
    syn = extract_syn_ant(entry, "synonyms")
    ant = extract_syn_ant(entry, "antonyms")
    if syn:
        out["synonyms"] = syn
    if ant:
        out["antonyms"] = ant
    if pos in ("noun", "adj"):
        # Only nouns/adjectives — verb conjugation tables also tag their "we" person
        # as "plural", which is not a plural noun form and must not leak in here.
        plural = extract_plural(entry)
        if plural:
            out["plural"] = plural
    return out


def main(path):
    out = []
    seen = set()
    total = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            total += 1
            entry = json.loads(line)
            converted = convert(entry)
            if converted is None:
                continue
            dedupe_key = (converted["lemma"], converted["pos"])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            out.append(converted)

    out_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "lexicon_bulk.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"entries": out}, f, ensure_ascii=False)

    with_root = sum(1 for e in out if "root" in e)
    print(f"read {total} lines -> {len(out)} entries written ({with_root} with a root) -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1])
