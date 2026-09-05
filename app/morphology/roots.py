"""Root representation and weak-root classification.

A root is a tuple of 3 letters, e.g. ("ك", "ت", "ب"). For weak roots the
*true* underlying radical is stored even when it never surfaces plainly in
some conjugated forms — e.g. the root of قال ("to say") is stored as
("ق", "و", "ل"), not the surface ("ق", "ا", "ل").
"""

WEAK_LETTERS = {"و", "ي"}
HAMZA_VARIANTS = {"ء", "أ", "إ", "ؤ", "ئ", "آ"}

WEAKNESS_SOUND = "sound"
WEAKNESS_ASSIMILATED = "assimilated"   # مثال — weak 1st radical (و/ي)
WEAKNESS_HOLLOW = "hollow"             # أجوف — weak 2nd radical
WEAKNESS_DEFECTIVE = "defective"       # ناقص — weak 3rd radical
WEAKNESS_DOUBLED = "doubled"           # مضعف — 2nd radical == 3rd radical
WEAKNESS_HAMZATED = "hamzated"         # مهموز — a radical is hamza


def canonical_hamza(letter: str) -> str:
    return "ء" if letter in HAMZA_VARIANTS else letter


def root_key(letters) -> str:
    """Canonical lookup key for a root tuple/list — hamza-seat-insensitive."""
    return " ".join(canonical_hamza(c) for c in letters)


def classify_weakness(root) -> str:
    r1, r2, r3 = root
    if r2 == r3 and r2 not in WEAK_LETTERS:
        return WEAKNESS_DOUBLED
    if r1 in WEAK_LETTERS:
        return WEAKNESS_ASSIMILATED
    if r2 in WEAK_LETTERS:
        return WEAKNESS_HOLLOW
    if r3 in WEAK_LETTERS:
        return WEAKNESS_DEFECTIVE
    if any(canonical_hamza(r) == "ء" for r in (r1, r2, r3)):
        return WEAKNESS_HAMZATED
    return WEAKNESS_SOUND


ARABIC_LETTER_RE_RANGE = "ء-ي"
