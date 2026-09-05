"""Stage A (proclitics/enclitics) and Stage B (verb subject affixes) stripping.

Both stages are generative-candidate producers, not deterministic parsers:
Arabic without diacritics is genuinely ambiguous, so each function returns
every plausible split and lets the pattern matcher + lexicon lookup downstream
decide which ones are real.
"""
from itertools import product

PROCLITIC_L1 = ["و", "ف"]          # wa-, fa- (conjunctions)
PROCLITIC_L2 = ["ب", "ك", "ل"]      # bi-, ka-, li- (particles)
DEFINITE_ARTICLE = "ال"

ENCLITICS = ["كما", "نني", "ني", "نا", "كم", "كن", "ها", "هما", "هم", "هن", "ك", "ه", "ي"]

MADI_SUFFIXES = ["تما", "تا", "تم", "تن", "نا", "وا", "ت", "ا", "ن", ""]
MUDARI_PREFIXES = ["أ", "ن", "ت", "ي"]
MUDARI_SUFFIXES = ["ان", "ون", "ين", "ن", ""]

MIN_STEM_LEN = 2

NOUN_PLURAL_SUFFIXES = ["ون", "ين", "ات"]  # sound masc plural, sound fem plural
NISBA_SUFFIX = "ي"                          # relational adjective, e.g. مصر -> مصري
NISBA_FEMININE_SUFFIX = "ية"                # nisba + feminine/abstract-noun marker,
                                             # e.g. إداري -> إدارية "administrative(f.)"


def strip_proclitics(word):
    """Return list of (clitic_label, remainder) candidates, including ("", word)."""
    results = {("", word)}
    for l1, l2, art in product([None] + PROCLITIC_L1, [None] + PROCLITIC_L2, [None, DEFINITE_ARTICLE]):
        parts = [p for p in (l1, l2, art) if p]
        if not parts:
            continue
        if l2 == "ل" and art == DEFINITE_ARTICLE:
            prefix = (l1 or "") + "لل"
        else:
            prefix = "".join(parts)
        if word.startswith(prefix) and len(word) - len(prefix) >= MIN_STEM_LEN:
            remainder = word[len(prefix):]
            results.add(("+".join(parts), remainder))
    return sorted(results, key=lambda x: len(x[0]))


def strip_enclitic(word):
    """Return list of (enclitic_label, remainder) candidates, including ("", word)."""
    results = [("", word)]
    for suf in ENCLITICS:
        if word.endswith(suf) and len(word) - len(suf) >= MIN_STEM_LEN:
            remainder = word[: -len(suf)]
            results.append((suf, remainder))
            if remainder.endswith("ت"):
                # Taa marbuta surfaces as plain taa before any pronoun suffix
                # (مدرسة "school" -> مدرستها "her school"), so the citation
                # form of a feminine noun ends in ة, not the ت seen here.
                results.append((suf, remainder[:-1] + "ة"))
    return results


def strip_verb_affixes(word):
    """Return list of (core_stem, features) candidates for a citation-form-or-inflected verb.

    features is a dict like {"tense": "madi", "suffix": "وا"} or {} if no
    subject affix was stripped (i.e. the word is being read as a bare
    lemma/citation form).
    """
    candidates = [(word, {})]

    for suf in MADI_SUFFIXES:
        if suf and word.endswith(suf) and len(word) - len(suf) >= MIN_STEM_LEN:
            candidates.append((word[: -len(suf)], {"tense": "madi", "suffix": suf}))

    for futures, base in (("", word), ("س", word[1:] if word.startswith("س") else None), ("سوف", word[3:] if word.startswith("سوف") else None)):
        if base is None or len(base) < MIN_STEM_LEN:
            continue
        for pre in MUDARI_PREFIXES:
            if base.startswith(pre) and len(base) - len(pre) >= MIN_STEM_LEN:
                rest = base[len(pre):]
                candidates.append((rest, {"tense": "mudari3", "future": futures, "prefix": pre, "suffix": ""}))
                for suf in MUDARI_SUFFIXES:
                    if suf and rest.endswith(suf) and len(rest) - len(suf) >= MIN_STEM_LEN:
                        candidates.append((rest[: -len(suf)], {"tense": "mudari3", "future": futures, "prefix": pre, "suffix": suf}))

    # Imperative (أمر): hamzat-wasl "ا" glued to a Form-I jussive stem, e.g. اكتب.
    if word.startswith("ا") and len(word) >= MIN_STEM_LEN + 1:
        candidates.append((word[1:], {"tense": "amr", "form_hint": 1}))
    for suf in ["ي", "وا", "ن", ""]:
        if suf and word.endswith(suf) and len(word) - len(suf) >= MIN_STEM_LEN:
            base = word[: -len(suf)]
            if base.startswith("ا"):
                candidates.append((base[1:], {"tense": "amr", "form_hint": 1, "suffix": suf}))

    seen = set()
    unique = []
    for stem, feat in candidates:
        key = (stem, tuple(sorted(feat.items())))
        if key not in seen:
            seen.add(key)
            unique.append((stem, feat))
    return unique


def strip_noun_suffix(word):
    """Candidates for sound-plural / nisba-adjective stripping on nouns and
    adjectives, one level of chaining deep (covers a plural built on a nisba
    noun, e.g. استشهاديون -> استشهادي -> استشهاد). Returns (suffix_label,
    remainder) pairs, NOT including ("", word) — callers already have the
    unstripped stem from elsewhere in the pipeline.
    """
    def one_pass(w):
        out = []
        for suf in NOUN_PLURAL_SUFFIXES:
            if w.endswith(suf) and len(w) - len(suf) >= MIN_STEM_LEN:
                base = w[: -len(suf)]
                out.append((suf, base))
                if suf == "ات":
                    # Sound feminine plural drops the singular's ة before
                    # adding ات (فِئَة -> فِئ+ات), so the citation form is
                    # usually base+ة, not the bare consonants alone.
                    out.append((suf, base + "ة"))
        if w.endswith(NISBA_FEMININE_SUFFIX) and len(w) - 2 >= MIN_STEM_LEN:
            base = w[:-2]
            out.append((NISBA_FEMININE_SUFFIX, base))
            # Nisba formation elides a base noun's ة before adding ي (إدارة -> إداري),
            # so the true base is often base+ة, not the bare consonants alone.
            out.append((NISBA_FEMININE_SUFFIX, base + "ة"))
        elif w.endswith(NISBA_SUFFIX) and len(w) - 1 >= MIN_STEM_LEN:
            base = w[:-1]
            out.append((NISBA_SUFFIX, base))
            out.append((NISBA_SUFFIX, base + "ة"))
        return out

    results = {}
    for suf1, w1 in one_pass(word):
        results[(suf1, w1)] = True
        for suf2, w2 in one_pass(w1):
            results[(suf1 + "+" + suf2, w2)] = True
    return list(results.keys())
