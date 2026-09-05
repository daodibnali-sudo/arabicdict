"""Build app/data/places_bulk.json from the Wikidata gazetteer dump produced
by fetch_wikidata_places.py (countries, populous cities, mountains, rivers —
each with a real Wikidata-localized Arabic name, not an invented
transliteration).

Rootless entries, same shape as the other bulk sources: merge priority in
lexicon_loader.py puts this last (after curated/Wiktionary/FreeDict), so any
place Wiktionary already covers more richly (e.g. بغداد) is left alone —
this only fills in what nothing else has.

Usage: python3 scripts/ingest_places.py <places_raw.json>
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.morphology.normalize import strip_diacritics

KIND_LABEL = {"country": "country", "city": "city", "mountain": "mountain", "river": "river"}


def main(raw_path):
    with open(raw_path, encoding="utf-8") as f:
        rows = json.load(f)

    by_bare = {}
    for row in rows:
        ar, en, kind = row["ar"].strip(), row["en"].strip(), row["kind"]
        if not ar or not en or len(ar) < 2:
            continue
        bare = strip_diacritics(ar)
        by_bare.setdefault(bare, {}).setdefault(kind, set()).add(en)

    out = []
    for bare, kinds in by_bare.items():
        glosses = []
        for kind, en_names in kinds.items():
            label = KIND_LABEL.get(kind, kind)
            for en in sorted(en_names)[:3]:
                glosses.append(f"{en} ({label})")
        out.append({
            "lemma": bare,  # Wikidata Arabic labels are already undiacritized
            "pos": "name",
            "glosses": glosses[:6],
            "source": "wikidata",
        })

    out_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "places_bulk.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"entries": out}, f, ensure_ascii=False)

    print(f"{len(out)} place entries written -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1])
