import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.morphology.conjugate import generate_paradigm
from app.morphology.normalize import strip_diacritics


def check(label, got, expected):
    got_bare = strip_diacritics(got)
    expected_bare = strip_diacritics(expected)
    status = "OK" if got_bare == expected_bare else "MISMATCH"
    marker = "" if got == expected else "  (diacritics differ)" if status == "OK" else ""
    print(f"[{status}] {label}: got={got!r} expected={expected!r}{marker}")
    return status == "OK"


results = []

# Form I sound: كتب (u-class: يكتب)
p = generate_paradigm(("ك", "ت", "ب"), 1, "sound", mudari3_vowel="u")
results.append(check("katab 3ms madi", p["madi"]["active"]["3ms"], "كَتَبَ"))
results.append(check("katab 1s madi", p["madi"]["active"]["1s"], "كَتَبْتُ"))
results.append(check("katab 3ms mudari active", p["mudari3"]["active"]["3ms"], "يَكْتُبُ"))
results.append(check("katab 3ms mudari passive", p["mudari3"]["passive"]["3ms"], "يُكْتَبُ"))
results.append(check("katab 3ms madi passive", p["madi"]["passive"]["3ms"], "كُتِبَ"))
results.append(check("katab amr 2ms", p["amr"]["2ms"], "اُكْتُبْ"))

# Form IV: اخرج (akhraja) from خرج
p4 = generate_paradigm(("خ", "ر", "ج"), 4, "sound")
results.append(check("akhraja 3ms madi", p4["madi"]["active"]["3ms"], "أَخْرَجَ"))
results.append(check("yukhriju 3ms mudari active", p4["mudari3"]["active"]["3ms"], "يُخْرِجُ"))
results.append(check("akhraja amr 2ms", p4["amr"]["2ms"], "أَخْرِجْ"))

# Form VIII: اجتمع from جمع
p8 = generate_paradigm(("ج", "م", "ع"), 8, "sound")
results.append(check("ijtama'a 3ms madi", p8["madi"]["active"]["3ms"], "اِجْتَمَعَ"))
results.append(check("yajtami'u 3ms mudari", p8["mudari3"]["active"]["3ms"], "يَجْتَمِعُ"))
results.append(check("ijtami' amr 2ms", p8["amr"]["2ms"], "اِجْتَمِعْ"))

# Form X: استخرج from خرج
p10 = generate_paradigm(("خ", "ر", "ج"), 10, "sound")
results.append(check("istakhraja 3ms madi", p10["madi"]["active"]["3ms"], "اِسْتَخْرَجَ"))
results.append(check("yastakhriju 3ms mudari", p10["mudari3"]["active"]["3ms"], "يَسْتَخْرِجُ"))
results.append(check("istakhrij amr 2ms", p10["amr"]["2ms"], "اِسْتَخْرِجْ"))

# Hollow: قال (qala) و-medial, u-class
ph = generate_paradigm(("ق", "و", "ل"), 1, "hollow", mudari3_medial="و", madi_contraction_vowel="u")
results.append(check("qala 3ms madi", ph["madi"]["active"]["3ms"], "قَالَ"))
results.append(check("qultu 1s madi", ph["madi"]["active"]["1s"], "قُلْتُ"))
results.append(check("qulna 3fp madi", ph["madi"]["active"]["3fp"], "قُلْنَ"))
results.append(check("yaqulu 3ms mudari", ph["mudari3"]["active"]["3ms"], "يَقُولُ"))
results.append(check("yaqulna 3fp mudari", ph["mudari3"]["active"]["3fp"], "يَقُلْنَ"))
results.append(check("qul amr 2ms", ph["amr"]["2ms"], "قُلْ"))
results.append(check("quli amr 2fs", ph["amr"]["2fs"], "قُولِي"))

# Hollow: نام (nama) medial='ا', i-contraction
pn = generate_paradigm(("ن", "و", "م"), 1, "hollow", mudari3_medial="ا", madi_contraction_vowel="i")
results.append(check("nama 3ms madi", pn["madi"]["active"]["3ms"], "نَامَ"))
results.append(check("nimtu 1s madi", pn["madi"]["active"]["1s"], "نِمْتُ"))
results.append(check("yanamu 3ms mudari", pn["mudari3"]["active"]["3ms"], "يَنَامُ"))

# Defective: دعا (da'a) و-final, u-class
pd = generate_paradigm(("د", "ع", "و"), 1, "defective", mudari3_vowel="u")
results.append(check("da'a 3ms madi", pd["madi"]["active"]["3ms"], "دَعَا"))
results.append(check("da'at 3fs madi", pd["madi"]["active"]["3fs"], "دَعَتْ"))
results.append(check("da'awtu 1s madi", pd["madi"]["active"]["1s"], "دَعَوْتُ"))
results.append(check("yad'u 3ms mudari", pd["mudari3"]["active"]["3ms"], "يَدْعُو"))
results.append(check("yad'una 3mp mudari", pd["mudari3"]["active"]["3mp"], "يَدْعُونَ"))
results.append(check("tad'ina 2fs mudari", pd["mudari3"]["active"]["2fs"], "تَدْعِينَ"))
results.append(check("yad'ina 3fp mudari (fem pl)", pd["mudari3"]["active"]["3fp"], "يَدْعُوْنَ"))
results.append(check("ud'u amr 2ms", pd["amr"]["2ms"], "اُدْعُ"))

# Defective: رمى (rama) ي-final, i-class
pr = generate_paradigm(("ر", "م", "ي"), 1, "defective", mudari3_vowel="i")
results.append(check("rama 3ms madi", pr["madi"]["active"]["3ms"], "رَمَى"))
results.append(check("ramat 3fs madi", pr["madi"]["active"]["3fs"], "رَمَتْ"))
results.append(check("yarmi 3ms mudari", pr["mudari3"]["active"]["3ms"], "يَرْمِي"))
results.append(check("yarmuna 3mp mudari (neutralized)", pr["mudari3"]["active"]["3mp"], "يَرْمُونَ"))
results.append(check("irmi amr 2ms", pr["amr"]["2ms"], "اِرْمِ"))

# Doubled: رد (radda)
prd = generate_paradigm(("ر", "د", "د"), 1, "doubled")
results.append(check("radda 3ms madi", prd["madi"]["active"]["3ms"], "رَدَّ"))
results.append(check("radadtu 1s madi", prd["madi"]["active"]["1s"], "رَدَدْتُ"))
results.append(check("raddu 3mp madi", prd["madi"]["active"]["3mp"], "رَدُّوا"))
results.append(check("yaruddu 3ms mudari", prd["mudari3"]["active"]["3ms"], "يَرُدُّ"))
results.append(check("yardudna 3fp mudari (fem pl split)", prd["mudari3"]["active"]["3fp"], "يَرْدُدْنَ"))
results.append(check("rudda amr 2ms", prd["amr"]["2ms"], "رُدَّ"))

print()
passed = sum(results)
print(f"{passed}/{len(results)} passed")
