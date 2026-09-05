"""Wazn (pattern/template) matching: consonant-skeleton -> candidate root(s).

Arabic derivational morphology is root-and-pattern: a 3-letter root is poured
into a fixed template (وزن) that adds fixed "augment" letters at fixed
positions (the classical mnemonic for augment letters is "سألتمونيها").
Given a stem with clitics and subject affixes already removed, we match its
*shape* (length + which fixed letters sit where) against the known templates
for the ten verb forms plus the common derived-noun patterns, and read the
root off the remaining "slot" letters.

Several templates are genuinely indistinguishable without diacritics (Form I
vs Form II both look like a bare 3-letter skeleton; Form III verb and the
Form-I active participle share the same X-ا-X-X shape). In those cases we
emit every reading as a separate candidate — the caller (analyzer + lexicon
lookup) is responsible for ranking/filtering using what's actually attested.
"""
from collections import namedtuple

from .roots import WEAK_LETTERS

Match = namedtuple("Match", ["root", "tag", "form", "note"])

ALEF = "ا"
HAMZA_FORMS = {"أ", "إ", "آ", "ء"}


def _is_letters(*chars):
    return all(c and c not in ("", None) for c in chars)


def match_stem(stem):
    """Return a list of Match candidates for a clitic/affix-stripped stem."""
    n = len(stem)
    out = []

    if n == 3:
        r1, r2, r3 = stem[0], stem[1], stem[2]
        if r2 == ALEF:
            # Hollow root: the ا stands for an elided و or ي — try both.
            out.append(Match((r1, "و", r3), "verb_hollow_madi", 1, "hollow root (madi contraction)"))
            out.append(Match((r1, "ي", r3), "verb_hollow_madi", 1, "hollow root (madi contraction)"))
        else:
            out.append(Match((r1, r2, r3), "verb_form_1", 1, None))
            out.append(Match((r1, r2, r3), "verb_form_2_ambiguous", 2, "Form I/II look identical without shadda"))
            out.append(Match((r1, r2, r3), "noun_bare_triliteral", None, "could be a primitive noun, not a derived form"))

    if n == 2:
        # Doubled root contracted in undiacritized madi 3ms, e.g. رد -> ردد.
        r1, r2 = stem[0], stem[1]
        out.append(Match((r1, r2, r2), "verb_doubled_madi", 1, "doubled root (gemination contracted)"))

    if n == 4:
        if stem[1] == ALEF:
            # X ا X X : Form III verb or Form-I active participle (فاعل)
            root = (stem[0], stem[2], stem[3])
            out.append(Match(root, "verb_form_3", 3, None))
            out.append(Match(root, "noun_active_participle", None, None))
        elif stem[0] in HAMZA_FORMS:
            out.append(Match((stem[1], stem[2], stem[3]), "verb_form_4", 4, None))
        elif stem[0] == "ت":
            out.append(Match((stem[1], stem[2], stem[3]), "verb_form_5", 5, None))
        elif stem[0] == "م":
            root = (stem[1], stem[2], stem[3])
            out.append(Match(root, "noun_meem_prefix", None, "place/instrument noun or Form II-X active participle"))
        elif stem[0] == ALEF and stem[1] == "ت":
            # Assimilated Form VIII (و/ي 1st radical merges into the ت infix), e.g. اتصل from وصل.
            out.append(Match(("و", stem[2], stem[3]), "verb_form_8_assimilated", 8, "assimilated 1st radical guessed as و"))
            out.append(Match(("ي", stem[2], stem[3]), "verb_form_8_assimilated", 8, "assimilated 1st radical guessed as ي"))
        elif stem[2] == "و":
            # Broken plural فُعُول of a CvCC noun (جَهْد -> جُهُود), or the same
            # shape used as an intensive adjective (صَبُور) — same root either way.
            out.append(Match((stem[0], stem[1], stem[3]), "noun_broken_plural_fuul", None, "broken plural / intensive adjective (فعول)"))
        elif stem[1] == "ت":
            # Form VIII mudari3/amr: the citation ا-فتعل loses its hamzat-wasl once a
            # subject prefix (or nothing, for amr) takes that slot — يفتعل -> فتعل.
            if stem[2] == ALEF:
                # Hollow root: the ا stands for an elided و or ي, e.g. يحتاج -> حتاج (حوج).
                out.append(Match((stem[0], "و", stem[3]), "verb_form_8_mudari3", 8, "hollow root"))
                out.append(Match((stem[0], "ي", stem[3]), "verb_form_8_mudari3", 8, "hollow root"))
            else:
                out.append(Match((stem[0], stem[2], stem[3]), "verb_form_8_mudari3", 8, None))
        elif stem[0] == "ن":
            # Form VII mudari3/amr: same hamzat-wasl loss as Form VIII above — ينفعل -> نفعل.
            if stem[2] == ALEF:
                out.append(Match((stem[1], "و", stem[3]), "verb_form_7_mudari3", 7, "hollow root"))
                out.append(Match((stem[1], "ي", stem[3]), "verb_form_7_mudari3", 7, "hollow root"))
            else:
                out.append(Match((stem[1], stem[2], stem[3]), "verb_form_7_mudari3", 7, None))

    if n == 5:
        if stem[0] == "ت" and stem[2] == ALEF:
            out.append(Match((stem[1], stem[3], stem[4]), "verb_form_6", 6, None))
        elif stem[0] == ALEF and stem[1] == "ن":
            out.append(Match((stem[2], stem[3], stem[4]), "verb_form_7", 7, None))
        elif stem[0] == ALEF and stem[2] == "ت":
            out.append(Match((stem[1], stem[3], stem[4]), "verb_form_8", 8, None))
        elif stem[0] == ALEF and stem[3] == stem[4]:
            out.append(Match((stem[1], stem[2], stem[3]), "verb_form_9", 9, "rare form (colors/defects)"))
        elif stem[0] == "م" and stem[3] == "و":
            out.append(Match((stem[1], stem[2], stem[4]), "noun_passive_participle", None, None))
        elif stem[0] == "م" and stem[2] == ALEF:
            # Broken plural مَفَاعِل of a meem-prefix noun (مَنْصِب -> مَنَاصِب,
            # مَكْتَب -> مَكَاتِب).
            out.append(Match((stem[1], stem[3], stem[4]), "noun_broken_plural_mafail", None, "broken plural (مفاعل)"))
        elif stem[1] == "و" and stem[2] == ALEF:
            # Broken plural فَوَاعِل of a فاعل-shaped noun (شَاغِل -> شَوَاغِل,
            # عَامِل -> عَوَامِل). A defective final radical often surfaces as ي
            # regardless of the root's true weak letter (دَاعِي -> دَوَاعِي, root د-ع-و).
            out.append(Match((stem[0], stem[3], stem[4]), "noun_broken_plural_fawaail", None, "broken plural (فواعل)"))
            if stem[4] == "ي":
                out.append(Match((stem[0], stem[3], "و"), "noun_broken_plural_fawaail", None, "broken plural (فواعل), defective root"))
        elif stem[2] == ALEF and stem[3] in ("ء", "ئ"):
            # Broken plural فَعَائِل of a فَعَالة-shaped feminine noun
            # (خَسَارَة -> خَسَائِر, رِسَالَة -> رَسَائِل).
            out.append(Match((stem[0], stem[1], stem[4]), "noun_broken_plural_faail", None, "broken plural (فعائل)"))
        elif stem[0:2] == "ست":
            # Form X mudari3/amr: يستفعل -> ستفعل (same mechanism, one more augment letter).
            out.append(Match((stem[2], stem[3], stem[4]), "verb_form_10_mudari3", 10, None))
        elif stem[3] == "ي":
            # Form II verbal noun (masdar): تفعيل, e.g. تطوير "development" from طوّر.
            out.append(Match((stem[1], stem[2], stem[4]), "noun_masdar_form2", None, "Form II verbal noun (تفعيل)"))
        elif stem[0] in HAMZA_FORMS and stem[3] == ALEF:
            # Form IV verbal noun (masdar): إفعال, e.g. إدماج "integration" from أدمج.
            out.append(Match((stem[1], stem[2], stem[4]), "noun_masdar_form4", None, "Form IV verbal noun (إفعال)"))

    if n == 6:
        if stem[0:3] == "است":
            out.append(Match((stem[3], stem[4], stem[5]), "verb_form_10", 10, None))
        elif stem[0:3] == "مست":
            root_first, root_last = stem[3], stem[5]
            if stem[4] == ALEF:
                # Hollow root: the ا stands for an elided و or ي — try both.
                out.append(Match((root_first, "و", root_last), "noun_participle_form10", None, "Form X participle, hollow root (مستفعَل)"))
                out.append(Match((root_first, "ي", root_last), "noun_participle_form10", None, "Form X participle, hollow root (مستفعَل)"))
            else:
                out.append(Match((root_first, stem[4], root_last), "noun_participle_form10", None, "Form X participle (مستفعِل/مستفعَل)"))
        elif stem[0] == ALEF and stem[4] == ALEF:
            # Forms VII/VIII verbal nouns share the ا-X-X-X-ا-X skeleton; emit
            # both readings (Form VIII's ت-infix at position 2, Form VII's
            # fixed ن at position 1) and let lexicon lookup pick the real one.
            if stem[2] == "ت":
                out.append(Match((stem[1], stem[3], stem[5]), "noun_masdar_form8", None, "Form VIII verbal noun (افتعال)"))
            if stem[1] == "ن":
                out.append(Match((stem[2], stem[3], stem[5]), "noun_masdar_form7", None, "Form VII verbal noun (انفعال)"))

    if n == 7 and stem[0:3] == "است" and stem[5] == ALEF:
        # Form X verbal noun (masdar): استفعال, e.g. استخدام "use" from استخدم.
        out.append(Match((stem[3], stem[4], stem[6]), "noun_masdar_form10", None, "Form X verbal noun (استفعال)"))

    # Defective-root guess: final stem letter is ا/ى standing in for elided و/ي.
    if n >= 3 and stem[-1] in (ALEF, "ى"):
        base = stem[:-1]
        if len(base) == 2:
            out.append(Match((base[0], base[1], "و"), "verb_defective_madi", 1, "defective root guess"))
            out.append(Match((base[0], base[1], "ي"), "verb_defective_madi", 1, "defective root guess"))

    return out
