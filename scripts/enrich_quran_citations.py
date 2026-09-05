"""Patches surah/ayah citation metadata onto quran-sourced entries in an
already-built examples.json / examples_candidates.json, without rescanning
the (slow) UNPC corpus. Quran parsing itself is cheap (6236 verses), so this
runs in seconds — used when the citation schema changes after a scan already
ran, instead of paying for a full rescan just to add three extra fields.

Usage: python3 scripts/enrich_quran_citations.py <quran_ar.json>
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def build_citation_lookup(quran_ar_path):
    ar = json.load(open(quran_ar_path, encoding="utf-8"))
    lookup = {}
    for surah_ar in ar["data"]["surahs"]:
        for ayah_ar in surah_ar["ayahs"]:
            ar_text = ayah_ar["text"].lstrip("﻿").strip()
            lookup[ar_text] = {
                "surah_number": surah_ar["number"],
                "surah_name_ar": surah_ar["name"],
                "surah_name_en": surah_ar["englishName"],
                "ayah_number": ayah_ar["numberInSurah"],
            }
    return lookup


def patch_flat(path, lookup):
    """examples.json shape: {bare_lemma: [example, ...]}"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    patched = 0
    missing = 0
    for exs in data.values():
        for e in exs:
            if e.get("source") == "quran":
                meta = lookup.get(e["ar"])
                if meta:
                    e.update(meta)
                    patched += 1
                else:
                    missing += 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"{path}: patched {patched}, no citation found for {missing}")


def patch_candidates(path, lookup):
    """examples_candidates.json shape: {bare_lemma: {source: [candidate, ...]}}"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    patched = 0
    missing = 0
    for by_source in data.values():
        for e in by_source.get("quran", []):
            meta = lookup.get(e["ar"])
            if meta:
                e.update(meta)
                patched += 1
            else:
                missing += 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"{path}: patched {patched}, no citation found for {missing}")


def main(quran_ar_path):
    lookup = build_citation_lookup(quran_ar_path)
    base = os.path.join(os.path.dirname(__file__), "..", "app", "data")
    patch_flat(os.path.join(base, "examples.json"), lookup)
    patch_candidates(os.path.join(base, "examples_candidates.json"), lookup)


if __name__ == "__main__":
    main(sys.argv[1])
