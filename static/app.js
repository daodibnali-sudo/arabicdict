const input = document.getElementById("q");
const goBtn = document.getElementById("go");
const resultsEl = document.getElementById("results");
const themeToggle = document.getElementById("theme-toggle");

function currentTheme() {
  const explicit = document.documentElement.getAttribute("data-theme");
  if (explicit === "dark" || explicit === "light") return explicit;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function updateThemeToggleLabel(theme) {
  themeToggle.textContent = theme === "dark" ? "Light mode" : "Dark mode";
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem("theme", theme); } catch (e) {}
  updateThemeToggleLabel(theme);
}

themeToggle.addEventListener("click", () => {
  applyTheme(currentTheme() === "dark" ? "light" : "dark");
});
updateThemeToggleLabel(currentTheme());

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

// Any Arabic word shown in a result — root-family members, synonyms/antonyms,
// plural, conjugation-table cells — is itself a valid search: wrap it so a
// click re-runs the search on that exact form (e.g. from لَانَ's conjugation
// table, clicking يَلِينُ searches that inflected form directly).
function wordLink(word) {
  if (!word) return "";
  return `<span class="word-link" data-word="${esc(word)}">${esc(word)}</span>`;
}

async function runSearch() {
  const q = input.value.trim();
  if (!q) { resultsEl.innerHTML = ""; return; }
  resultsEl.innerHTML = "<p class='no-results'>Searching…</p>";
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    render(data);
  } catch (e) {
    resultsEl.innerHTML = "<p class='no-results'>Something went wrong.</p>";
  }
}

function render(data) {
  if (data.multi_word) {
    resultsEl.innerHTML = data.words.map(w => `
      <div class="phrase-word">
        <div class="phrase-word-heading">${wordLink(w.word)}</div>
        ${w.found
          ? w.results.map(cardHtml).join("")
          : `<p class="no-results">${esc(w.message || "No results.")}</p>`}
      </div>`).join("");
    return;
  }
  if (!data.found) {
    resultsEl.innerHTML = `<p class="no-results">${esc(data.message || "No results.")}</p>`;
    return;
  }
  resultsEl.innerHTML = data.results.map(cardHtml).join("");
}

function breakdownLine(r) {
  const b = r.breakdown;
  const parts = [];
  if (b.proclitic) parts.push(`prefix: <span class="ar">${esc(b.proclitic)}</span>`);
  if (b.enclitic) parts.push(`suffix: <span class="ar">${esc(b.enclitic)}</span>`);
  if (b.verb_features && b.verb_features.tense) {
    parts.push(`tense: ${esc(b.verb_features.tense)}`);
  }
  parts.push(`matched via: ${esc(r.match_type)}`);
  if (!parts.length) return "";
  return `<div class="breakdown">${parts.join(" · ")}</div>`;
}

function rootFamilyHtml(r) {
  if (!r.root_family || !r.root_family.length) return "";
  const items = r.root_family.map(e =>
    `<li><span class="ar">${wordLink(e.lemma)}</span> <span class="en">— ${esc((e.glosses || []).join("; "))}</span></li>`
  ).join("");
  return `<details class="root-family"><summary>Other words from this root (${r.root_family.length})</summary><ul>${items}</ul></details>`;
}

function conjRow(persons, paradigm, code) {
  const madiA = paradigm.madi.active[code] || "";
  const madiP = (paradigm.madi.passive || {})[code] || "";
  const mudA = paradigm.mudari3.active[code] || "";
  const mudP = (paradigm.mudari3.passive || {})[code] || "";
  const amr = (paradigm.amr || {})[code] || "";
  const hasPassive = Object.keys(paradigm.madi.passive || {}).length || Object.keys(paradigm.mudari3.passive || {}).length;
  let row = `<tr><td class="ar">${esc(persons.find(p => p.code === code).label_ar)}</td>`;
  row += `<td class="ar">${madiA ? wordLink(madiA) : '<span class="empty">—</span>'}</td>`;
  row += `<td class="ar">${mudA ? wordLink(mudA) : '<span class="empty">—</span>'}</td>`;
  if (hasPassive) {
    row += `<td class="ar">${madiP ? wordLink(madiP) : '<span class="empty">—</span>'}</td>`;
    row += `<td class="ar">${mudP ? wordLink(mudP) : '<span class="empty">—</span>'}</td>`;
  }
  row += `<td class="ar">${amr ? wordLink(amr) : '<span class="empty">—</span>'}</td>`;
  row += `</tr>`;
  return row;
}

function highlightMatch(ar, matched) {
  if (!matched) return esc(ar);
  const idx = ar.indexOf(matched);
  if (idx === -1) return esc(ar);
  const before = ar.slice(0, idx);
  const hit = ar.slice(idx, idx + matched.length);
  const after = ar.slice(idx + matched.length);
  return `${esc(before)}<mark>${esc(hit)}</mark>${esc(after)}`;
}

const ARABIC_INDIC_DIGITS = ["٠", "١", "٢", "٣", "٤", "٥", "٦", "٧", "٨", "٩"];
function toArabicIndicDigits(n) {
  return String(n).split("").map(d => ARABIC_INDIC_DIGITS[+d] ?? d).join("");
}

function exampleSourceLine(ex) {
  if (ex.source === "quran" && ex.surah_number) {
    return `<span class="ar">${esc(ex.surah_name_ar)} (${esc(ex.surah_name_en)}) — آية ${toArabicIndicDigits(ex.ayah_number)}</span>`;
  }
  return esc(ex.source);
}

function exampleArabicHtml(ex) {
  const body = highlightMatch(ex.ar, ex.matched);
  if (ex.source === "quran") {
    const marker = ` ۝${toArabicIndicDigits(ex.ayah_number || "")}`;
    return `<span class="quran-text">${body}${esc(marker)}</span>`;
  }
  return body;
}

function examplesHtml(r) {
  if (!r.examples || !r.examples.length) return "";
  const items = r.examples.map(ex =>
    `<li><div class="ar">${exampleArabicHtml(ex)}</div><div class="en">${esc(ex.en)}</div><div class="ex-src">${exampleSourceLine(ex)}</div></li>`
  ).join("");
  return `<details class="examples"><summary>Examples (${r.examples.length})</summary><ul>${items}</ul></details>`;
}

function conjugationHtml(r) {
  const c = r.conjugation;
  if (!c) return "";
  const hasPassive = Object.keys(c.paradigm.madi.passive || {}).length || Object.keys(c.paradigm.mudari3.passive || {}).length;
  let header = `<tr><th></th><th>ماضي</th><th>مضارع</th>`;
  if (hasPassive) header += `<th>ماضي (مجهول)</th><th>مضارع (مجهول)</th>`;
  header += `<th>أمر</th></tr>`;
  const rows = c.persons.map(p => conjRow(c.persons, c.paradigm, p.code)).join("");
  const noteHtml = c.paradigm.note ? `<div class="note">${esc(c.paradigm.note)}</div>` : "";
  return `<details class="conj"><summary>Conjugation — Form ${c.form}, ${esc(c.weakness)}</summary>
    ${noteHtml}
    <table>${header}${rows}</table>
  </details>`;
}

function cardHtml(r) {
  const synAnt = [];
  if (r.synonyms && r.synonyms.length) synAnt.push(`<span class="ar">مرادف: ${r.synonyms.map(wordLink).join("، ")}</span>`);
  if (r.antonyms && r.antonyms.length) synAnt.push(`<span class="ar">ضد: ${r.antonyms.map(wordLink).join("، ")}</span>`);

  const notesHtml = (r.notes || []).map(n => `<div class="note">${esc(n)}</div>`).join("");

  return `<div class="card">
    <span class="lemma">${esc(r.lemma)}</span><span class="pos">${esc(r.pos || "")}</span>
    ${r.source === "wiktionary" ? '<span class="src">Wiktionary</span>' : ""}
    ${r.source === "freedict" ? '<span class="src">FreeDict</span>' : ""}
    ${r.root ? `<div class="root">جذر: ${esc(r.root)}</div>` : ""}
    <div class="glosses">${esc((r.glosses || []).join("; ")) || "<em>no gloss in seed dictionary yet</em>"}</div>
    ${r.plural ? `<div class="meta-line ar">جمع: ${wordLink(r.plural)}</div>` : ""}
    ${synAnt.length ? `<div class="meta-line">${synAnt.join(" &nbsp; ")}</div>` : ""}
    ${notesHtml}
    ${breakdownLine(r)}
    ${examplesHtml(r)}
    ${rootFamilyHtml(r)}
    ${conjugationHtml(r)}
  </div>`;
}

goBtn.addEventListener("click", runSearch);
input.addEventListener("keydown", e => { if (e.key === "Enter") runSearch(); });

resultsEl.addEventListener("click", e => {
  const link = e.target.closest(".word-link");
  if (!link) return;
  input.value = link.dataset.word;
  runSearch();
  input.scrollIntoView({ behavior: "smooth", block: "start" });
});
