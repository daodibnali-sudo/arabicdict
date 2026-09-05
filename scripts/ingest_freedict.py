"""Build app/data/freedict_bulk.json from FreeDict's Arabic-English dictionary
(TEI XML), sourced from the Arabeyes.org Wordlist project.

License: GPL 2.0+. This is data compiled by Arabeyes.org, distributed via the
FreeDict project — keep attribution with any distribution of this data.

Quality note: this dictionary reads as an old English-headword wordlist that
was reversed into Arabic-headword form — many entries have a multi-word
Arabic *phrase* standing in for an obscure English headword (e.g. "غلاف
الكتاب" -> "Vincture"), not a real single-word dictionary entry. We only
keep single-word Arabic headwords, which cuts ~53k entries down to the
subset that's actually usable as real vocabulary (checked: ~31.6k, of which
~26.5k aren't already covered by the curated+Wiktionary lexicon).

Usage: python3 scripts/ingest_freedict.py <ara-eng.tei>
"""
import sys
import os
import json
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from app.morphology.normalize import strip_diacritics
from ingest_wiktionary import guess_root_from_lemma  # reuses the same root-guess + sanity filter

NS = {"tei": "http://www.tei-c.org/ns/1.0"}
MAX_GLOSSES = 6


def main(tei_path):
    tree = ET.parse(tei_path)
    root = tree.getroot()

    glosses_by_orth = {}
    for entry in root.findall(".//tei:entry", NS):
        orth_el = entry.find(".//tei:orth", NS)
        if orth_el is None or not orth_el.text:
            continue
        orth = orth_el.text.strip()
        if " " in orth or len(orth) < 2:
            continue  # skip reversed multi-word phrase entries — see module docstring
        quotes = [q.text.strip() for q in entry.findall(".//tei:quote", NS) if q.text and q.text.strip()]
        if not quotes:
            continue
        bucket = glosses_by_orth.setdefault(orth, [])
        for q in quotes:
            gloss = q[0].lower() + q[1:] if q else q
            if gloss not in bucket:
                bucket.append(gloss)

    out = []
    for orth, glosses in glosses_by_orth.items():
        bare = strip_diacritics(orth)
        entry = {
            "lemma": orth,
            "pos": None,
            "glosses": glosses[:MAX_GLOSSES],
            "source": "freedict",
        }
        root_guess = guess_root_from_lemma(bare)
        if root_guess:
            entry["root"] = list(root_guess)
        out.append(entry)

    out_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "freedict_bulk.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"entries": out}, f, ensure_ascii=False)

    with_root = sum(1 for e in out if "root" in e)
    print(f"{len(out)} single-word entries written ({with_root} with a guessed root) -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1])
