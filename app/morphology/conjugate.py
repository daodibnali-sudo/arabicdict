"""Full verb paradigm generator.

Given a root, a form number (1-10, i.e. وزن), and a weakness class, this
generates the complete conjugation: ماضي (past) and مضارع (present,
indicative/مرفوع) each in معلوم (active) and مجهول (passive), plus أمر
(imperative, active only, 2nd person).

Coverage / honest limitations:
  - Sound, doubled, assimilated and hamzated roots: fully generated for all
    10 forms.
  - Hollow and defective roots: fully generated for Form I only (by far the
    most common case), and only for the more common "fa'ala-type" pattern
    (دعا/يدعو, رمى/يرمي, قال/يقول) rather than the rarer "fa'ila-type"
    (نسي/ينسى, رضي/يرضى). Forms II-X for hollow/defective roots fall back
    to treating the weak letter as if it were a plain consonant (the
    "sound-pattern approximation") — flagged via a "note" key rather than
    silently presented as exact.
  - The Form I mudari3 vowel class (the yaktu-b / yaj-lis / yadh-hab split)
    and, for hollow/defective roots, which long-vowel letter surfaces in the
    mudari3 stem, are lexically idiosyncratic in real Arabic — not derivable
    from the root alone. They must be supplied (normally from the lexicon
    entry); a default is used otherwise, and is a guess, not a fact.
"""

FATHA, DAMMA, KASRA, SUKUN, SHADDA = "َ", "ُ", "ِ", "ْ", "ّ"
ALEF = "ا"

PERSON_ORDER = ["3ms", "3md", "3mp", "3fs", "3fd", "3fp",
                "2ms", "2d", "2mp", "2fs", "2fp", "1s", "1p"]

PERSON_LABELS_AR = {
    "3ms": "هو", "3md": "هما (مذكر)", "3mp": "هم", "3fs": "هي", "3fd": "هما (مؤنث)", "3fp": "هنّ",
    "2ms": "أنتَ", "2d": "أنتما", "2mp": "أنتم", "2fs": "أنتِ", "2fp": "أنتنّ",
    "1s": "أنا", "1p": "نحن",
}
PERSON_LABELS_EN = {
    "3ms": "he", "3md": "they two (m)", "3mp": "they (m)", "3fs": "she", "3fd": "they two (f)", "3fp": "they (f)",
    "2ms": "you (m.sg)", "2d": "you two", "2mp": "you (m.pl)", "2fs": "you (f.sg)", "2fp": "you (f.pl)",
    "1s": "I", "1p": "we",
}

# ---- madi (past) person endings, applied after r3 ------------------------
_MADI_ENDINGS = {
    "3ms": lambda r3: r3 + FATHA,
    "3md": lambda r3: r3 + FATHA + ALEF,
    "3mp": lambda r3: r3 + DAMMA + "و" + ALEF,
    "3fs": lambda r3: r3 + FATHA + "ت" + SUKUN,
    "3fd": lambda r3: r3 + FATHA + "ت" + FATHA + ALEF,
    "3fp": lambda r3: r3 + SUKUN + "ن" + FATHA,
    "2ms": lambda r3: r3 + SUKUN + "ت" + FATHA,
    "2d": lambda r3: r3 + SUKUN + "ت" + DAMMA + "م" + FATHA + ALEF,
    "2mp": lambda r3: r3 + SUKUN + "ت" + DAMMA + "م" + SUKUN,
    "2fp": lambda r3: r3 + SUKUN + "ت" + DAMMA + "ن" + SHADDA + FATHA,
    "2fs": lambda r3: r3 + SUKUN + "ت" + KASRA,
    "1s": lambda r3: r3 + SUKUN + "ت" + DAMMA,
    "1p": lambda r3: r3 + SUKUN + "ن" + FATHA + ALEF,
}
# Persons whose suffix begins with a quiescent (sukun) consonant attached
# directly to r3 — the set that triggers hollow-root contraction and
# defective-root radical "resurfacing".
_CONSONANT_SUFFIX_PERSONS = {"3fp", "2ms", "2d", "2mp", "2fp", "2fs", "1s", "1p"}

# ---- mudari3 (present) prefix + ending categories -------------------------
_MUDARI_PERSON_INFO = {
    "3ms": ("ي", "bare"), "3md": ("ي", "dual"), "3mp": ("ي", "plural_m"),
    "3fs": ("ت", "bare"), "3fd": ("ت", "dual"), "3fp": ("ي", "plural_f"),
    "2ms": ("ت", "bare"), "2d": ("ت", "dual"), "2mp": ("ت", "plural_m"),
    "2fs": ("ت", "2fs"), "2fp": ("ت", "plural_f"),
    "1s": ("أ", "bare"), "1p": ("ن", "bare"),
}
_MUDARI_ENDINGS = {
    "bare": lambda r3: r3 + DAMMA,
    "dual": lambda r3: r3 + FATHA + ALEF + "ن" + KASRA,
    "plural_m": lambda r3: r3 + DAMMA + "و" + "ن" + FATHA,
    "plural_f": lambda r3: r3 + SUKUN + "ن" + FATHA,
    "2fs": lambda r3: r3 + KASRA + "ي" + "ن" + FATHA,
}
_AMR_ENDINGS = {
    "bare": lambda r3: r3 + SUKUN,
    "dual": lambda r3: r3 + FATHA + ALEF,
    "plural_m": lambda r3: r3 + DAMMA + "و" + ALEF,
    "2fs": lambda r3: r3 + KASRA + "ي",
    "plural_f": lambda r3: r3 + SUKUN + "ن" + FATHA,
}

# Forms whose active mudari3 prefix takes DAMMA (II, III, IV); all others take FATHA.
_DAMMA_PREFIX_FORMS = {2, 3, 4}


def _madi_base_active(form, r1, r2):
    return {
        1: lambda: r1 + FATHA + r2 + FATHA,
        2: lambda: r1 + FATHA + r2 + SHADDA + FATHA,
        3: lambda: r1 + FATHA + ALEF + r2 + FATHA,
        4: lambda: "أ" + FATHA + r1 + SUKUN + r2 + FATHA,
        5: lambda: "ت" + FATHA + r1 + FATHA + r2 + SHADDA + FATHA,
        6: lambda: "ت" + FATHA + r1 + FATHA + ALEF + r2 + FATHA,
        7: lambda: ALEF + KASRA + "ن" + SUKUN + r1 + FATHA + r2 + FATHA,
        8: lambda: ALEF + KASRA + r1 + SUKUN + "ت" + FATHA + r2 + FATHA,
        9: lambda: ALEF + KASRA + r1 + SUKUN + r2 + FATHA,
        10: lambda: ALEF + KASRA + "س" + SUKUN + "ت" + FATHA + r1 + SUKUN + r2 + FATHA,
    }[form]()


def _madi_base_passive(form, r1, r2):
    fn = {
        1: lambda: r1 + DAMMA + r2 + KASRA,
        2: lambda: r1 + DAMMA + r2 + SHADDA + KASRA,
        3: lambda: r1 + DAMMA + "و" + r2 + KASRA,
        4: lambda: "أ" + DAMMA + r1 + SUKUN + r2 + KASRA,
        5: lambda: "ت" + DAMMA + r1 + DAMMA + r2 + SHADDA + KASRA,
        6: lambda: "ت" + DAMMA + r1 + DAMMA + "و" + r2 + KASRA,
        7: lambda: ALEF + DAMMA + "ن" + SUKUN + r1 + DAMMA + r2 + KASRA,
        8: lambda: ALEF + DAMMA + r1 + SUKUN + "ت" + DAMMA + r2 + KASRA,
        9: None,
        10: lambda: ALEF + DAMMA + "س" + SUKUN + "ت" + DAMMA + r1 + SUKUN + r2 + KASRA,
    }[form]
    return fn() if fn else None


def _mudari_internal_active(form, r1, r2, class_vowel):
    return {
        1: lambda: r1 + SUKUN + r2 + class_vowel,
        2: lambda: r1 + FATHA + r2 + SHADDA + KASRA,
        3: lambda: r1 + FATHA + ALEF + r2 + KASRA,
        4: lambda: r1 + SUKUN + r2 + KASRA,
        5: lambda: r1 + FATHA + r2 + SHADDA + FATHA,
        6: lambda: r1 + FATHA + ALEF + r2 + FATHA,
        7: lambda: "ن" + SUKUN + r1 + FATHA + r2 + KASRA,
        8: lambda: r1 + SUKUN + "ت" + FATHA + r2 + KASRA,
        9: lambda: r1 + SUKUN + r2 + FATHA,
        10: lambda: "س" + SUKUN + "ت" + FATHA + r1 + SUKUN + r2 + KASRA,
    }[form]()


def _mudari_internal_passive(form, r1, r2):
    fn = {
        1: lambda: r1 + SUKUN + r2 + FATHA,
        2: lambda: r1 + FATHA + r2 + SHADDA + FATHA,
        3: lambda: r1 + FATHA + ALEF + r2 + FATHA,
        4: lambda: r1 + SUKUN + r2 + FATHA,
        5: lambda: r1 + FATHA + r2 + SHADDA + FATHA,
        6: lambda: r1 + FATHA + ALEF + r2 + FATHA,
        7: lambda: "ن" + SUKUN + r1 + FATHA + r2 + FATHA,
        8: lambda: r1 + SUKUN + "ت" + FATHA + r2 + FATHA,
        9: None,
        10: lambda: "س" + SUKUN + "ت" + FATHA + r1 + SUKUN + r2 + FATHA,
    }[form]
    return fn() if fn else None


# amr helper (hamza) needed when the mudari3 internal pattern starts on a sukun.
_AMR_HELPER = {
    1: "wasl_class", 2: None, 3: None, 4: "qat_fatha", 5: None, 6: None,
    7: "wasl_kasra", 8: "wasl_kasra", 9: "wasl_kasra", 10: "wasl_kasra",
}


def _sound_paradigm(r1, r2, r3, form, mudari3_vowel):
    class_vowel = {"u": DAMMA, "i": KASRA, "a": FATHA}.get(mudari3_vowel, DAMMA)
    result = {"madi": {"active": {}, "passive": {}}, "mudari3": {"active": {}, "passive": {}}, "amr": {}}

    active_base = _madi_base_active(form, r1, r2)
    for p in PERSON_ORDER:
        result["madi"]["active"][p] = active_base + _MADI_ENDINGS[p](r3)

    passive_base = _madi_base_passive(form, r1, r2)
    if passive_base is not None:
        for p in PERSON_ORDER:
            result["madi"]["passive"][p] = passive_base + _MADI_ENDINGS[p](r3)

    prefix_vowel_active = DAMMA if form in _DAMMA_PREFIX_FORMS else FATHA
    internal_active = _mudari_internal_active(form, r1, r2, class_vowel)
    for p in PERSON_ORDER:
        letter, cat = _MUDARI_PERSON_INFO[p]
        result["mudari3"]["active"][p] = letter + prefix_vowel_active + internal_active + _MUDARI_ENDINGS[cat](r3)

    internal_passive = _mudari_internal_passive(form, r1, r2)
    if internal_passive is not None:
        for p in PERSON_ORDER:
            letter, cat = _MUDARI_PERSON_INFO[p]
            result["mudari3"]["passive"][p] = letter + DAMMA + internal_passive + _MUDARI_ENDINGS[cat](r3)

    helper = _AMR_HELPER[form]
    for p in ["2ms", "2d", "2mp", "2fs", "2fp"]:
        _, cat = _MUDARI_PERSON_INFO[p]
        body = internal_active + _AMR_ENDINGS[cat](r3)
        if helper == "wasl_class":
            wasl_vowel = DAMMA if mudari3_vowel == "u" else KASRA
            result["amr"][p] = ALEF + wasl_vowel + body
        elif helper == "wasl_kasra":
            result["amr"][p] = ALEF + KASRA + body
        elif helper == "qat_fatha":
            result["amr"][p] = "أ" + FATHA + body
        else:
            result["amr"][p] = body

    if form == 9:
        # Form IX doubles r3 (اِفْعَلَّ) — patch the base 3ms citation forms;
        # the generic engine above isn't set up to double a letter mid-template.
        result["madi"]["active"]["3ms"] = ALEF + KASRA + r1 + SUKUN + r2 + FATHA + r3 + SHADDA + FATHA
        result["mudari3"]["active"]["3ms"] = "ي" + FATHA + r1 + SUKUN + r2 + FATHA + r3 + SHADDA + DAMMA

    return result


def _hollow_form1(r1, r3, mudari3_medial, madi_contraction_vowel):
    """Form-I hollow root (أجوف), e.g. قال (ق-و-ل, medial='و') or نام (ن-و-م, medial='ا')."""
    class_vowel_before_long = {"و": DAMMA, "ي": KASRA, "ا": FATHA}[mudari3_medial]
    short = DAMMA if madi_contraction_vowel == "u" else KASRA

    long_stem = r1 + class_vowel_before_long + mudari3_medial   # e.g. قُو
    contracted_stem = r1 + short                                 # e.g. قُ (radical elided)
    uncontracted_madi = r1 + FATHA + ALEF                        # e.g. قَا (madi keeps plain alef regardless of class)

    madi_active = {}
    for p in PERSON_ORDER:
        base = contracted_stem if p in _CONSONANT_SUFFIX_PERSONS else uncontracted_madi
        madi_active[p] = base + _MADI_ENDINGS[p](r3)

    mudari3_active = {}
    for p in PERSON_ORDER:
        letter, cat = _MUDARI_PERSON_INFO[p]
        stem = contracted_stem if cat == "plural_f" else long_stem
        mudari3_active[p] = letter + FATHA + stem + _MUDARI_ENDINGS[cat](r3)

    amr = {}
    for p in ["2ms", "2d", "2mp", "2fs", "2fp"]:
        _, cat = _MUDARI_PERSON_INFO[p]
        stem = contracted_stem if cat in ("bare", "plural_f") else long_stem
        amr[p] = stem + _AMR_ENDINGS[cat](r3)

    return {
        "madi": {"active": madi_active, "passive": {}},
        "mudari3": {"active": mudari3_active, "passive": {}},
        "amr": amr,
        "note": "hollow root, Form I — passive omitted (rare/marked differently for hollow verbs)",
    }


def _defective_form1(r1, r2, weak_letter, mudari3_vowel):
    """Form-I defective root (ناقص), e.g. دعا (د-ع-و) or رمى (ر-م-ي)."""
    class_vowel = {"u": DAMMA, "i": KASRA, "a": FATHA}.get(mudari3_vowel, KASRA)
    bare_letter = {"u": "و", "i": "ي"}.get(mudari3_vowel, "ي")
    citation_alef = ALEF if weak_letter == "و" else "ى"

    madi_active = {
        "3ms": r1 + FATHA + r2 + FATHA + citation_alef,
        "3md": r1 + FATHA + r2 + FATHA + weak_letter + FATHA + ALEF,
        "3mp": r1 + FATHA + r2 + FATHA + "و" + SUKUN + ALEF,
        "3fs": r1 + FATHA + r2 + FATHA + "ت" + SUKUN,
        "3fd": r1 + FATHA + r2 + FATHA + "ت" + FATHA + ALEF,
        "3fp": r1 + FATHA + r2 + FATHA + weak_letter + SUKUN + "ن" + FATHA,
        "2ms": r1 + FATHA + r2 + FATHA + weak_letter + SUKUN + "ت" + FATHA,
        "2d": r1 + FATHA + r2 + FATHA + weak_letter + SUKUN + "ت" + DAMMA + "م" + FATHA + ALEF,
        "2mp": r1 + FATHA + r2 + FATHA + weak_letter + SUKUN + "ت" + DAMMA + "م" + SUKUN,
        "2fp": r1 + FATHA + r2 + FATHA + weak_letter + SUKUN + "ت" + DAMMA + "ن" + SHADDA + FATHA,
        "2fs": r1 + FATHA + r2 + FATHA + weak_letter + SUKUN + "ت" + KASRA,
        "1s": r1 + FATHA + r2 + FATHA + weak_letter + SUKUN + "ت" + DAMMA,
        "1p": r1 + FATHA + r2 + FATHA + weak_letter + SUKUN + "ن" + FATHA + ALEF,
    }

    mudari3_active = {}
    for p in PERSON_ORDER:
        letter, cat = _MUDARI_PERSON_INFO[p]
        if cat == "bare":
            mudari3_active[p] = letter + FATHA + r1 + SUKUN + r2 + class_vowel + bare_letter
        elif cat == "dual":
            mudari3_active[p] = letter + FATHA + r1 + SUKUN + r2 + class_vowel + weak_letter + FATHA + ALEF + "ن" + KASRA
        elif cat == "plural_m":
            # Neutralized — masc. plural always shows و regardless of the true final radical.
            mudari3_active[p] = letter + FATHA + r1 + SUKUN + r2 + DAMMA + "و" + "ن" + FATHA
        elif cat == "2fs":
            # Neutralized — 2fs always shows ي regardless of the true final radical.
            mudari3_active[p] = "ت" + FATHA + r1 + SUKUN + r2 + KASRA + "ي" + "ن" + FATHA
        elif cat == "plural_f":
            mudari3_active[p] = letter + FATHA + r1 + SUKUN + r2 + class_vowel + weak_letter + SUKUN + "ن" + FATHA

    amr = {
        "2ms": r1 + SUKUN + r2 + class_vowel,
        "2d": r1 + SUKUN + r2 + class_vowel + weak_letter + FATHA + ALEF,
        "2mp": r1 + SUKUN + r2 + DAMMA + "و" + ALEF,
        "2fs": r1 + SUKUN + r2 + KASRA + "ي",
        "2fp": r1 + SUKUN + r2 + class_vowel + weak_letter + SUKUN + "ن" + FATHA,
    }
    wasl_vowel = DAMMA if mudari3_vowel == "u" else KASRA
    amr = {k: ALEF + wasl_vowel + v for k, v in amr.items()}

    return {
        "madi": {"active": madi_active, "passive": {}},
        "mudari3": {"active": mudari3_active, "passive": {}},
        "amr": amr,
        "note": "defective root, Form I ('fa'ala' pattern only, e.g. دعا/رمى) — passive omitted",
    }


def _doubled_form1(r1, r2):
    """Form-I doubled/geminate root (مضعف), e.g. رد (ر-د-د)."""
    geminate_citation = r1 + FATHA + r2 + SHADDA + FATHA          # رَدَّ
    geminate_no_end_vowel = r1 + FATHA + r2 + SHADDA               # رَدّ + ending

    madi_active = {}
    for p in PERSON_ORDER:
        if p in _CONSONANT_SUFFIX_PERSONS:
            # Gemination splits apart with a fatha: رَدَدْتُ.
            madi_active[p] = r1 + FATHA + r2 + FATHA + _MADI_ENDINGS[p](r2)
        elif p == "3ms":
            madi_active[p] = geminate_citation
        else:
            madi_active[p] = geminate_no_end_vowel + _MADI_ENDINGS[p](r2)[len(r2):]

    mudari3_active = {}
    for p in PERSON_ORDER:
        letter, cat = _MUDARI_PERSON_INFO[p]
        if cat == "plural_f":
            # يَرْدُدْنَ — gemination splits before the fem.-plural ن, like madi.
            # (unsliced: the ending's own leading r2 supplies the second literal radical)
            mudari3_active[p] = letter + FATHA + r1 + SUKUN + r2 + DAMMA + _MUDARI_ENDINGS[cat](r2)
        else:
            # يَرُدُّ — merged gemination shifts the class vowel onto r1, not between r1/r2.
            mudari3_active[p] = letter + FATHA + r1 + DAMMA + r2 + SHADDA + _MUDARI_ENDINGS[cat](r2)[len(r2):]

    amr = {
        "2ms": r1 + DAMMA + r2 + SHADDA + FATHA,
        "2d": r1 + DAMMA + r2 + SHADDA + FATHA + ALEF,
        "2mp": r1 + DAMMA + r2 + SHADDA + DAMMA + "و" + ALEF,
        "2fs": r1 + DAMMA + r2 + SHADDA + KASRA + "ي",
        "2fp": ALEF + DAMMA + r1 + SUKUN + r2 + DAMMA + SUKUN + "ن" + FATHA,
    }

    return {
        "madi": {"active": madi_active, "passive": {}},
        "mudari3": {"active": mudari3_active, "passive": {}},
        "amr": amr,
        "note": "doubled root, Form I — passive omitted",
    }


def generate_paradigm(root, form, weakness, mudari3_vowel="u", mudari3_medial=None, madi_contraction_vowel=None):
    """Generate the full conjugation table for (root, form, weakness).

    root: (r1, r2, r3) tuple of true radicals (weak letters spelled out, e.g. ("ق","و","ل")).
    form: 1-10.
    weakness: one of sound/assimilated/hollow/defective/doubled/hamzated.
    mudari3_vowel: "u"/"i"/"a" — Form I mudari3 stem-vowel class (lexical; default "u").
    mudari3_medial / madi_contraction_vowel: hollow-root-only lexical hints.
    """
    r1, r2, r3 = root
    if weakness == "hollow" and form == 1:
        medial = mudari3_medial or (r2 if r2 in ("و", "ي") else "و")
        contraction = madi_contraction_vowel or ("u" if medial == "و" else "i")
        result = _hollow_form1(r1, r3, medial, contraction)
    elif weakness == "defective" and form == 1:
        weak_letter = r3 if r3 in ("و", "ي") else "ي"
        result = _defective_form1(r1, r2, weak_letter, mudari3_vowel)
    elif weakness == "doubled" and form == 1:
        result = _doubled_form1(r1, r2)
    else:
        result = _sound_paradigm(r1, r2, r3, form, mudari3_vowel)
        if weakness in ("hollow", "defective", "doubled") and form != 1:
            result["note"] = (
                f"{weakness} root, Form {form}: generated with the sound-root pattern as an "
                "approximation — Forms II-X of weak roots beyond Form I are not fully modeled yet."
            )

    return result
