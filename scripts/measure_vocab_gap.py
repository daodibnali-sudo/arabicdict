"""Diagnostic: scan the corpora and count words that resolve to NOTHING via
the current morphological pipeline — no new entries created, just measurement,
to size the actual vocabulary gap before deciding how (or whether) to fill it.

Note: an "unmatched surface form" can mean two different things — a genuinely
undefined word (needs a new dictionary entry), or an inflected form of a word
we DO define that the morphology engine still can't reduce to its lemma
(needs a smarter stripping rule, not a new entry — e.g. broken plurals, which
aren't handled at all yet). This script can't tell those apart automatically;
the frequency-sorted output is meant to be eyeballed for that split.

Usage: python3 scripts/measure_vocab_gap.py <tatoeba_dir> <quran_ar.json> <quran_en.json> <unpc_ar> <unpc_en>
"""
import sys
import os
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from app.morphology.normalize import strip_diacritics, fold
from app.morphology.analyzer import resolves
from app.data.lexicon_loader import get_lexicon
from ingest_examples import load_quran, load_tatoeba, iter_unpc, TOKEN_WITH_DIACRITICS_RE, MAX_SENTENCE_CHARS


def word_resolves(word, lexicon):
    """Same two-pass structure as live search: exact, then fuzzy-fold fallback."""
    if resolves(word, lexicon):
        return True
    folded = fold(word)
    return folded != word and resolves(folded, lexicon)


def main(tatoeba_dir, quran_ar, quran_en, unpc_ar, unpc_en):
    lexicon = get_lexicon()

    def all_pairs():
        yield from load_quran(quran_ar, quran_en)
        yield from load_tatoeba(tatoeba_dir)
        yield from iter_unpc(unpc_ar, unpc_en)

    unmatched = Counter()
    total_tokens = 0
    matched_tokens = 0
    i = 0
    for ar_text, en_text, source, meta in all_pairs():
        i += 1
        if len(ar_text) > MAX_SENTENCE_CHARS:
            continue
        for tok_orig in TOKEN_WITH_DIACRITICS_RE.findall(ar_text):
            tok_bare = strip_diacritics(tok_orig)
            if len(tok_bare) < 2:
                continue
            total_tokens += 1
            if word_resolves(tok_bare, lexicon):
                matched_tokens += 1
            else:
                unmatched[tok_bare] += 1
        if i % 1000000 == 0:
            print(f"  processed {i} sentences, {len(unmatched)} distinct unmatched so far")

    print()
    print(f"total word-tokens seen: {total_tokens}")
    print(f"matched: {matched_tokens} ({100*matched_tokens/total_tokens:.1f}%)")
    print(f"distinct unmatched surface forms: {len(unmatched)}")
    print(f"total unmatched occurrences: {sum(unmatched.values())}")
    print()
    print("top 100 most frequent unmatched forms:")
    for word, count in unmatched.most_common(100):
        print(f"  {count:>8}  {word}")

    out_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "vocab_gap.json")
    import json
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(unmatched.most_common(), f, ensure_ascii=False)
    print(f"\nfull list saved -> {out_path}")


if __name__ == "__main__":
    main(*sys.argv[1:6])
