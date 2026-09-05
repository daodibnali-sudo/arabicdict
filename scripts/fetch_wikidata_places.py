"""Pull a world gazetteer (countries, populous cities, mountains, rivers)
from Wikidata's public SPARQL endpoint, keeping only items that have both an
English and an Arabic label — that pair is exactly what a reverse (EN->AR)
place-name lookup needs, and Wikidata's labels are already the real localized
Arabic name (e.g. "طورا بورا"), not a transliteration we'd have to invent.

License: Wikidata content is CC0 (public domain) — no attribution required,
commercial use unrestricted. Safe for a "public product" the same way the
existing CC BY-SA/CC BY/GPL sources were vetted for.

Usage: python3 scripts/fetch_wikidata_places.py <out_dir>
Writes one raw JSON file per category to <out_dir>, plus a merged
places_raw.json of deduped (ar, en, kind) triples for ingest_places.py.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ENDPOINT = "https://query.wikidata.org/sparql"
UA = "arabicdict-research/1.0 (local project, contact: n/a)"


def _single_class_query(qid):
    return (f'SELECT ?item ?enLabel ?arLabel WHERE {{ '
            f'?item wdt:P31 wd:{qid} . '
            f'?item rdfs:label ?enLabel . FILTER(LANG(?enLabel)="en") '
            f'?item rdfs:label ?arLabel . FILTER(LANG(?arLabel)="ar") }}')


QUERIES = {
    "countries": ("country", 'SELECT ?item ?enLabel ?arLabel WHERE { '
                  '?item wdt:P31 wd:Q6256 . '
                  '?item rdfs:label ?enLabel . FILTER(LANG(?enLabel)="en") '
                  '?item rdfs:label ?arLabel . FILTER(LANG(?arLabel)="ar") }'),
    "cities": ("city", 'SELECT ?item ?enLabel ?arLabel WHERE { '
               'VALUES ?cls { wd:Q515 wd:Q3957 wd:Q1549591 } '
               '?item wdt:P31 ?cls . '
               '?item wdt:P1082 ?pop . FILTER(?pop > 50000) '
               '?item rdfs:label ?enLabel . FILTER(LANG(?enLabel)="en") '
               '?item rdfs:label ?arLabel . FILTER(LANG(?arLabel)="ar") }'),
    "mountains": ("mountain", 'SELECT ?item ?enLabel ?arLabel WHERE { '
                  '?item wdt:P31 wd:Q8502 . '
                  '?item rdfs:label ?enLabel . FILTER(LANG(?enLabel)="en") '
                  '?item rdfs:label ?arLabel . FILTER(LANG(?arLabel)="ar") }'),
    "rivers": ("river", 'SELECT ?item ?enLabel ?arLabel WHERE { '
               '?item wdt:P31 wd:Q4022 . '
               '?item rdfs:label ?enLabel . FILTER(LANG(?enLabel)="en") '
               '?item rdfs:label ?arLabel . FILTER(LANG(?arLabel)="ar") }'),
    # Single-QID categories below (region, lake, island, ...) each cover the
    # "notable but not simply a mountain/river/city/country" gap — e.g. Tora
    # Bora is classified on Wikidata as P31=region (Q82794), not mountain.
    "regions": ("region", _single_class_query("Q82794")),
    "mountain_ranges": ("mountain range", _single_class_query("Q1907114")),
    "lakes": ("lake", _single_class_query("Q23397")),
    "islands": ("island", _single_class_query("Q23442")),
    "deserts": ("desert", _single_class_query("Q8514")),
    "peninsulas": ("peninsula", _single_class_query("Q34763")),
    "seas": ("sea", _single_class_query("Q165")),
    "straits": ("strait", _single_class_query("Q173387")),
    "valleys": ("valley", _single_class_query("Q39816")),
    "archipelagos": ("archipelago", _single_class_query("Q179049")),
}


def run_query(query, retries=3):
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": query})
    req = urllib.request.Request(url, headers={"Accept": "application/sparql-results+json", "User-Agent": UA})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except Exception as e:
            print(f"  attempt {attempt+1} failed: {e}")
            time.sleep(5)
    raise RuntimeError(f"query failed after {retries} retries")


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    merged = []
    seen = set()

    for name, (kind, query) in QUERIES.items():
        print(f"fetching {name}...")
        data = run_query(query)
        bindings = data["results"]["bindings"]
        print(f"  {len(bindings)} rows")
        with open(os.path.join(out_dir, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(bindings, f, ensure_ascii=False)

        for row in bindings:
            en = row.get("enLabel", {}).get("value", "").strip()
            ar = row.get("arLabel", {}).get("value", "").strip()
            if not en or not ar:
                continue
            key = (ar, en, kind)
            if key in seen:
                continue
            seen.add(key)
            merged.append({"ar": ar, "en": en, "kind": kind})

    out_path = os.path.join(out_dir, "places_raw.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False)
    print(f"\n{len(merged)} deduped (ar,en,kind) triples -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1])
