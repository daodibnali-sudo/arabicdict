"""Orchestrates the full search pipeline: query -> ranked list of analyses.

query -> normalize -> [proclitic strip] x [enclitic strip] x [verb-affix strip]
      -> for each resulting stem: (a) direct lemma lookup, (b) wazn pattern
         match -> root lookup
      -> dedupe by (root, lemma), rank by how little surface had to be
         explained away, attach a conjugation table for verb entries.
"""
import re

from ..data.lexicon_loader import get_lexicon, get_examples
from .normalize import (
    clean_query, fold, strip_diacritics, has_diacritics, align_clusters,
    clusters_bare, clusters_diacritized, normalize_spelling_variants,
)
from .clitics import strip_proclitics, strip_enclitic, strip_verb_affixes, strip_noun_suffix
from .patterns import match_stem
from .roots import root_key
from .conjugate import generate_paradigm, PERSON_ORDER, PERSON_LABELS_AR, PERSON_LABELS_EN

MAX_RESULTS = 10

_ASCII_QUERY_RE = re.compile(r"^[a-zA-Z\s'\-]+$")
_EN_WORD_RE = re.compile(r"[a-zA-Z']+")


def _looks_english(raw_query):
    return bool(_ASCII_QUERY_RE.match(raw_query.strip()))


def _root_display(letters):
    return "-".join(letters)


def _build_conjugation(root_letters, weakness, entry):
    form = entry.get("form")
    if not form or len(root_letters) != 3:
        return None
    paradigm = generate_paradigm(
        tuple(root_letters),
        form,
        weakness,
        mudari3_vowel=entry.get("mudari3_vowel", "u"),
        mudari3_medial=entry.get("mudari3_medial"),
        madi_contraction_vowel=entry.get("madi_contraction_vowel"),
    )
    persons = [
        {"code": p, "label_ar": PERSON_LABELS_AR[p], "label_en": PERSON_LABELS_EN[p]}
        for p in PERSON_ORDER
    ]
    return {"form": form, "weakness": weakness, "persons": persons, "paradigm": paradigm}


def _make_result(entry, root_letters, weakness, breakdown, match_type, extra_note=None):
    conjugation = None
    if entry.get("pos") == "verb":
        conjugation = _build_conjugation(root_letters, weakness, entry)

    notes = [n for n in [entry.get("note"), extra_note] if n]

    return {
        "lemma": entry["lemma"],
        "pos": entry.get("pos"),
        "derivation": entry.get("derivation"),
        "glosses": entry.get("glosses", []),
        "synonyms": entry.get("synonyms", []),
        "antonyms": entry.get("antonyms", []),
        "plural": entry.get("plural"),
        "source": entry.get("source", "curated"),
        "examples": get_examples().get(strip_diacritics(entry["lemma"]), []),
        "root": _root_display(root_letters) if root_letters else None,
        "root_letters": list(root_letters),
        "weakness": weakness,
        "breakdown": breakdown,
        "match_type": match_type,
        "notes": notes,
        "conjugation": conjugation,
    }


DIACRITIC_EXACT_BONUS = 10


def _verb_affix_prefix_len(verb_features):
    if not verb_features:
        return 0
    if verb_features.get("tense") == "amr":
        return 1  # hamzat-wasl ا, always exactly 1 char per strip_verb_affixes
    return len(verb_features.get("future") or "") + len(verb_features.get("prefix") or "")


def _verb_affix_suffix_len(verb_features):
    if not verb_features:
        return 0
    return len(verb_features.get("suffix") or "")


def _diacritic_bonus(clusters, total_len, proclitic_bare_len, enclitic_bare_len, verb_features, lookup_key, entry_lemma):
    """If the user typed full tashkeel, reward the one candidate whose
    citation-form diacritization is an exact (spelling-variant-tolerant)
    match for what they actually typed — e.g. typing هَمّ exactly should
    surface هَمّ itself unmistakably, not tie with هُمْ on bare consonants
    alone. clusters is None whenever the query had no diacritics at all, so
    this is a no-op for the overwhelming majority of ordinary searches.
    """
    if clusters is None:
        return 0
    start = proclitic_bare_len + _verb_affix_prefix_len(verb_features)
    end = total_len - enclitic_bare_len - _verb_affix_suffix_len(verb_features)
    if start < 0 or end > total_len or start >= end:
        return 0
    if clusters_bare(clusters, start, end) != lookup_key:
        # The scored stem isn't a pure substring of the original input (e.g.
        # nisba/plural ة-restoration synthesized a letter never typed) —
        # position math doesn't apply here, skip safely rather than guess.
        return 0
    typed = normalize_spelling_variants(clusters_diacritized(clusters, start, end))
    canonical = normalize_spelling_variants(entry_lemma)
    return DIACRITIC_EXACT_BONUS if typed == canonical else 0


def _score(breakdown, entry=None):
    # Proclitics (و ف ب ك ل, and doubly so ال) are the single most common
    # attachment in real Arabic text — a word carrying بـ+الـ is not "2-3
    # characters of speculative guessing" the way an enclitic pronoun or a
    # verb subject-affix is. Weighting them per-character like everything
    # else let a coincidental enclitic-only reading (e.g. بَال+هم "their
    # mind") systematically outrank the at-least-as-likely بـ+الـ+noun
    # reading (بـ+الـ+هَمّ "with the worry") purely because "بال" (3 chars,
    # 2 morphemes) costs more than "هم" (2 chars, 1 morpheme). Half-weighting
    # proclitic characters corrects that bias without touching enclitics.
    proclitic_cost = 0.5 * len(breakdown["proclitic"].replace("+", ""))
    stripped = proclitic_cost + len(breakdown["enclitic"]) + breakdown["affix_len"]
    bonus = 2 if breakdown["match_type"] == "direct_lemma" else 0
    penalty = 0
    if entry is not None and not entry.get("pos"):
        # No POS at all is a 100%-reliable FreeDict fingerprint (31,304/31,304
        # FreeDict entries have pos=None; 0/34,614 Wiktionary and 0/19,575
        # places entries do) — FreeDict is a reversed old wordlist with raw
        # inflected surface forms imported as if they were their own headword
        # (e.g. "يلين"/"mellows" sitting next to the real answer, لَانَ; or
        # "يحكّ"/"abrades" outranking a genuinely missing exclamation particle
        # like وَيْح just because ingest_freedict.py's root-guesser happened to
        # accept its own 3 letters as a "root" via the same trivial fallback
        # match_stem offers any bare triliteral). Checking root_letters too
        # would let exactly that guessed-root case slip the penalty, so this
        # checks pos alone. Rank these below anything the morphology engine
        # can actually explain, so a proper lemma reached via prefix/pattern
        # stripping — or a real curated entry — outranks a bare literal match
        # on an inflected-form duplicate.
        penalty = 4
    return bonus - stripped - penalty


def resolves(word, lexicon):
    """Cheap existence check with the SAME matching power as live search
    (direct lemma + noun-suffix stripping + wazn pattern matching), but no
    result-object construction — for bulk diagnostics over millions of
    tokens, where building full result dicts (conjugation tables etc.) per
    token would be far too slow. Deliberately kept as its own pass over the
    same candidate generators rather than reusing _search_once, so it can
    short-circuit on the first hit.
    """
    for proclitic_label, rem1 in strip_proclitics(word):
        for enclitic_label, rem2 in strip_enclitic(rem1):
            for stem, verb_features in strip_verb_affixes(rem2):
                if lexicon.lookup_lemma(stem):
                    return True
                if not verb_features:
                    for _suffix_label, noun_stem in strip_noun_suffix(stem):
                        if lexicon.lookup_lemma(noun_stem):
                            return True
                for match in match_stem(stem):
                    group = lexicon.by_root.get(root_key(match.root))
                    if not group:
                        continue
                    for entry in group["entries"]:
                        if match.form is not None and entry.get("form") != match.form:
                            continue
                        return True
    return False


def _search_once(word, lexicon, clusters=None):
    """Run the full clitic/affix/pattern pipeline over an already-normalized word.

    clusters, when given, is the diacritics-preserving alignment of the
    original raw query (see normalize.align_clusters) — used only to award
    an exact-tashkeel bonus; every bare-string match/lookup below is
    unaffected by whether it's present.
    """
    found = {}  # (root_key, lemma) -> (score, result)
    total_len = len(word)

    for proclitic_label, rem1 in strip_proclitics(word):
        proclitic_bare_len = len(proclitic_label.replace("+", ""))
        for enclitic_label, rem2 in strip_enclitic(rem1):
            enclitic_bare_len = len(enclitic_label)
            for stem, verb_features in strip_verb_affixes(rem2):
                affix_len = len(rem2) - len(stem)
                breakdown_base = {
                    "proclitic": proclitic_label,
                    "enclitic": enclitic_label,
                    "verb_features": verb_features,
                    "affix_len": affix_len,
                    "surface_stem": stem,
                }

                for rk, entry in lexicon.lookup_lemma(stem):
                    if rk is not None:
                        letters = lexicon.by_root[rk]["letters"]
                        weakness = lexicon.by_root[rk]["weakness"]
                    else:
                        letters, weakness = (), None
                    breakdown = dict(breakdown_base, match_type="direct_lemma")
                    result = _make_result(entry, letters, weakness, breakdown, "direct_lemma")
                    score = _score(breakdown, entry) + _diacritic_bonus(
                        clusters, total_len, proclitic_bare_len, enclitic_bare_len,
                        verb_features, stem, entry["lemma"],
                    )
                    dedupe_key = (rk, entry["lemma"])
                    if dedupe_key not in found or found[dedupe_key][0] < score:
                        found[dedupe_key] = (score, result)

                # Sound-plural / nisba-adjective stripping — only meaningful on a bare
                # citation-form candidate, not one already read as a verb inflection.
                if not verb_features:
                    for suffix_label, noun_stem in strip_noun_suffix(stem):
                        for rk, entry in lexicon.lookup_lemma(noun_stem):
                            if rk is not None:
                                letters = lexicon.by_root[rk]["letters"]
                                weakness = lexicon.by_root[rk]["weakness"]
                            else:
                                letters, weakness = (), None
                            noun_affix_len = affix_len + (len(stem) - len(noun_stem))
                            breakdown = dict(
                                breakdown_base, match_type="direct_lemma",
                                affix_len=noun_affix_len, surface_stem=noun_stem,
                            )
                            result = _make_result(
                                entry, letters, weakness, breakdown, "direct_lemma",
                                extra_note=f"matched after stripping {suffix_label} (plural/nisba)",
                            )
                            score = _score(breakdown, entry) + _diacritic_bonus(
                                clusters, total_len, proclitic_bare_len, enclitic_bare_len,
                                verb_features, noun_stem, entry["lemma"],
                            )
                            dedupe_key = (rk, entry["lemma"])
                            if dedupe_key not in found or found[dedupe_key][0] < score:
                                found[dedupe_key] = (score, result)

                for match in match_stem(stem):
                    # If subject affixes were already stripped in Stage B, this position is
                    # known to be a verb slot — a competing "maybe it's just a bare noun"
                    # reading only makes sense when nothing was stripped there.
                    if match.tag == "noun_bare_triliteral" and verb_features:
                        continue
                    group = lexicon.by_root.get(root_key(match.root))
                    if not group:
                        continue
                    for entry in group["entries"]:
                        # A pattern that confidently names a specific form (e.g. "verb_form_5")
                        # should only surface entries of that form as top-level hits; other
                        # words sharing the root still show up via root_family below. A pattern
                        # with no specific form (noun shapes, bare triliteral) can't narrow
                        # further, so every entry in the root stays a candidate.
                        if match.form is not None and entry.get("form") != match.form:
                            continue
                        breakdown = dict(breakdown_base, match_type=match.tag)
                        result = _make_result(entry, group["letters"], group["weakness"], breakdown, match.tag, extra_note=match.note)
                        score = _score(breakdown, entry) + _diacritic_bonus(
                            clusters, total_len, proclitic_bare_len, enclitic_bare_len,
                            verb_features, stem, entry["lemma"],
                        )
                        dedupe_key = (root_key(match.root), entry["lemma"])
                        if dedupe_key not in found or found[dedupe_key][0] < score:
                            found[dedupe_key] = (score, result)

    return found


def _english_search(raw_query, lexicon):
    """query is English -> find Arabic entries whose gloss(es) match it."""
    query_lower = raw_query.strip().lower()
    query_words = set(_EN_WORD_RE.findall(query_lower))
    if not query_words:
        return {}

    found = {}  # (root_key, lemma) -> (score, result)
    for w in query_words:
        for rk, entry, gloss in lexicon.lookup_english_word(w):
            gloss_lower = gloss.lower().strip()
            gloss_words = set(_EN_WORD_RE.findall(gloss_lower))
            overlap = len(query_words & gloss_words)
            score = overlap / max(len(gloss_words), 1)
            if query_lower == gloss_lower:
                score += 10
            elif query_lower in gloss_lower:
                score += 2

            if rk is not None:
                letters = lexicon.by_root[rk]["letters"]
                weakness = lexicon.by_root[rk]["weakness"]
            else:
                letters, weakness = (), None
            breakdown = {
                "proclitic": "", "enclitic": "", "verb_features": {},
                "affix_len": 0, "surface_stem": raw_query, "match_type": "english_gloss",
            }
            result = _make_result(entry, letters, weakness, breakdown, "english_gloss", extra_note=f'matched gloss: "{gloss}"')
            dedupe_key = (rk, entry["lemma"])
            if dedupe_key not in found or found[dedupe_key][0] < score:
                found[dedupe_key] = (score, result)

    return found


def analyze(raw_query):
    lexicon = get_lexicon()

    if _looks_english(raw_query):
        found = _english_search(raw_query, lexicon)
        ranked = sorted(found.values(), key=lambda pair: -pair[0])
        results = [r for _, r in ranked[:MAX_RESULTS]]
        return _finalize(raw_query, results, lexicon)

    word = clean_query(raw_query)
    if not word:
        return []

    # Only built when the user actually typed tashkeel — align_clusters lets
    # _search_once compare that against candidates' full diacritization
    # (see _diacritic_bonus); for ordinary undiacritized input this stays
    # None and every lookup below behaves exactly as before.
    clusters = align_clusters(raw_query.strip()) if has_diacritics(raw_query) else None

    found = _search_once(word, lexicon, clusters)

    if not found:
        # Fallback: fuzzy-fold pass for common typos (alef/ya/ta-marbuta variants).
        folded = fold(raw_query)
        if folded != word:
            found = _search_once(folded, lexicon, clusters)

    if not found and re.search(r"\s", raw_query.strip()):
        # A phrase never exists as a single lexicon entry (no lemma contains a
        # space) — analyze each space-separated word on its own rather than
        # reporting the whole phrase as one big "not found", e.g. "يا ويحي"
        # fails as a unit even though يا and ويحي each resolve individually.
        tokens = [t for t in raw_query.strip().split() if t]
        if len(tokens) > 1:
            per_word = [analyze(t) for t in tokens]
            return {
                "query": raw_query,
                "found": any(w.get("found") for w in per_word),
                "multi_word": True,
                "words": [
                    {"word": t, "found": w.get("found", False), "results": w.get("results", []), "message": w.get("message")}
                    for t, w in zip(tokens, per_word)
                ],
            }

    ranked = sorted(found.values(), key=lambda pair: -pair[0])
    results = [r for _, r in ranked[:MAX_RESULTS]]
    return _finalize(raw_query, results, lexicon)


def _finalize(raw_query, results, lexicon):
    for r in results:
        group = lexicon.by_root.get(root_key(r["root_letters"]))
        if group:
            r["root_family"] = [
                {"lemma": e["lemma"], "pos": e.get("pos"), "glosses": e.get("glosses", [])}
                for e in group["entries"] if e["lemma"] != r["lemma"]
            ]
        else:
            r["root_family"] = []

    if not results:
        return {"query": raw_query, "found": False, "results": [], "message": "No entry or recognizable root found for this word yet."}

    return {"query": raw_query, "found": True, "results": results}
