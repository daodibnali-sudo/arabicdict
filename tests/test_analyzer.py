import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.morphology.analyzer import analyze

CASES = [
    "كتاب",           # direct lemma, book
    "والكتاب",         # wa + al + kitab
    "بالمكتبة",         # bi + al + library
    "يكتبون",          # mudari3 3mp of kataba
    "وسيكتبونها",       # wa + sa-future + mudari3 3mp + object suffix
    "تعلمت",           # madi 1s of Form V ta'allama (shadda stripped by diacritic removal anyway)
    "اتصلت",           # madi 1s/2ms of Form VIII ittasala (assimilated وصل)
    "قالوا",           # madi 3mp of hollow qala
    "دعا",             # madi 3ms defective da'a
    "المدرسة",          # al + madrasa
    "صغير",            # direct adjective
    "لعب",             # ambiguous: la'iba root or la+"عب"? just check it doesn't crash
]

for word in CASES:
    result = analyze(word)
    print("=" * 60)
    print("QUERY:", word)
    if not result.get("found"):
        print("  NOT FOUND:", result.get("message"))
        continue
    for r in result["results"][:3]:
        print(f"  -> {r['lemma']} ({r['pos']}) root={r['root']} glosses={r['glosses']} "
              f"via={r['match_type']} proclitic={r['breakdown']['proclitic']!r} enclitic={r['breakdown']['enclitic']!r}")
