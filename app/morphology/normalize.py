"""Text normalization for Arabic input.

Two normalization levels are exposed:
  - strip_diacritics: removes harakat/tanween/shadda/sukun/tatweel. This is the
    form the analyzer works on internally, since almost all real-world search
    input is undiacritized.
  - fold: an additional, lossier fold (unifies alef/ya/ta-marbuta variants)
    used only as a fallback search key when an exact match fails, since users
    routinely type "ا" for "أ", "ه" for "ة", etc.
"""
import re
import unicodedata

_DIACRITICS = re.compile(
    "[" + "".join(
        chr(c) for c in [
            0x064B, 0x064C, 0x064D, 0x064E, 0x064F, 0x0650, 0x0651, 0x0652,
            0x0653, 0x0654, 0x0655, 0x0656, 0x0657, 0x0658, 0x0659, 0x065A,
            0x065B, 0x065C, 0x065D, 0x065E, 0x065F,
        ]
    ) + "]"
)
_TATWEEL = "ـ"
_DAGGER_ALEF = "ٰ"  # Quranic/Uthmani spelling elides ا, marking it with this diacritic instead —
# e.g. كِتَٰب for كتاب. It stands for an actual long vowel, so it must fold to
# "ا" (matching modern spelling), NOT disappear like a real diacritic — stripping
# it to nothing would collapse the noun كتاب down to the unrelated verb root كتب.

_ALEF_VARIANTS = str.maketrans({
    "أ": "ا",  # أ -> ا
    "إ": "ا",  # إ -> ا
    "آ": "ا",  # آ -> ا
    "ٱ": "ا",  # ٱ -> ا
})
_YA_VARIANTS = str.maketrans({"ى": "ي"})  # ى -> ي
_TA_VARIANTS = str.maketrans({"ة": "ه"})  # ة -> ه


def strip_diacritics(text: str) -> str:
    text = text.replace(_TATWEEL, "")
    text = text.replace(_DAGGER_ALEF, "ا")
    text = _DIACRITICS.sub("", text)
    return unicodedata.normalize("NFC", text)


def fold(text: str) -> str:
    """Lossy fold for fuzzy fallback matching only — never used for root storage."""
    text = strip_diacritics(text)
    text = text.translate(_ALEF_VARIANTS)
    text = text.translate(_YA_VARIANTS)
    text = text.translate(_TA_VARIANTS)
    return text


def clean_query(text: str) -> str:
    return strip_diacritics(text.strip())


def has_diacritics(text: str) -> bool:
    return bool(_DIACRITICS.search(text)) or _DAGGER_ALEF in text


def align_clusters(text: str):
    """Split text into one (bare_letter, diacritized_form) pair per base
    letter, diacritics folded onto the letter they follow. Since every
    clitic/affix-stripping function in this codebase slices the *bare*
    string by character count, slicing this cluster list with the exact
    same indices recovers the original diacritics for that same substring —
    letting the analyzer compare what the user actually typed (tashkeel and
    all) against a dictionary entry's full diacritized lemma, not just the
    bare skeleton both reduce to.
    """
    text = unicodedata.normalize("NFC", text.replace(_TATWEEL, ""))
    clusters = []
    for ch in text:
        if ch == _DAGGER_ALEF:
            clusters.append(("ا", "ا"))
        elif _DIACRITICS.match(ch):
            if clusters:
                letter, seg = clusters[-1]
                clusters[-1] = (letter, seg + ch)
            # a stray leading diacritic with no preceding letter is dropped
        else:
            clusters.append((ch, ch))
    return clusters


def clusters_bare(clusters, start=0, end=None) -> str:
    return "".join(c[0] for c in clusters[start:end])


def clusters_diacritized(clusters, start=0, end=None) -> str:
    return "".join(c[1] for c in clusters[start:end])


def normalize_spelling_variants(text: str) -> str:
    """Same alef/ya/ta-marbuta tolerance as fold(), but keeps diacritics —
    for comparing a user's fully-diacritized input against a dictionary
    lemma's diacritization without also erasing the tashkeel that's the
    whole point of the comparison.
    """
    text = text.translate(_ALEF_VARIANTS)
    text = text.translate(_YA_VARIANTS)
    text = text.translate(_TA_VARIANTS)
    return text
