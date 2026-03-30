/* SNID-SAGE WISEREP Results Viewer
 *
 * Loads:
 * - data/wiserep_results.json : array of row objects
 * - data/meta.json           : column labels + flag rank mapping (optional)
 */

const QUALITY_OPTIONS = ["Very Low", "Low", "Medium", "High"];
const CONFIDENCE_OPTIONS = ["Very Low", "Low", "Medium", "High", "No Comp"];

function qs(id) {
  return document.getElementById(id);
}

function normalizeStr(v) {
  if (v === null || v === undefined) return "";
  const s = String(v).trim();
  if (!s || ["nan", "none", "null"].includes(s.toLowerCase())) return "";
  return s;
}

function toLower(v) {
  return normalizeStr(v).toLowerCase();
}

function tryNumber(v) {
  if (v === null || v === undefined) return null;
  if (typeof v === "number" && Number.isFinite(v)) return v;
  const s = normalizeStr(v);
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function csvEscape(value) {
  const s = value === null || value === undefined ? "" : String(value);
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function downloadText(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function uniqueSorted(values) {
  const set = new Set();
  for (const v of values) {
    const s = normalizeStr(v);
    if (s) set.add(s);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
}

// ---- App state ---------------------------------------------------------------

let allRows = [];
let filteredRows = [];
let columns = []; // [{key,label,is_flag}]
let flagRank = {}; // { "very low": 1, ... }

let sortKey = null;
let sortDir = "asc"; // "asc" | "desc"
let highlightEnabled = false;

let pageSize = 100;
let page = 1;

// ---- DOM --------------------------------------------------------------------

const elType = qs("filterType");
const elSubtype = qs("filterSubtype");
const elName = qs("filterName");
const elQuality = qs("filterQuality");
const elTypeConf = qs("filterTypeConf");
const elSubtypeConf = qs("filterSubtypeConf");

const btnApply = qs("btnApply");
const btnClear = qs("btnClear");
const btnHighlight = qs("btnHighlight");
const btnDownload = qs("btnDownload");
const btnReload = qs("btnReload");

const elSummary = qs("summaryText");
const elHead = qs("tableHead");
const elBody = qs("tableBody");

const btnPrev = qs("btnPrev");
const btnNext = qs("btnNext");
const elPageInfo = qs("pageInfo");
const elPageSize = qs("pageSize");

// ---- Filters ----------------------------------------------------------------

function buildCheckboxGroup(container, options, idPrefix) {
  container.innerHTML = "";
  for (const opt of options) {
    const id = `${idPrefix}_${opt.replace(/\s+/g, "_")}`;
    const label = document.createElement("label");
    label.className = "check";

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = id;
    cb.value = opt;

    const span = document.createElement("span");
    span.textContent = opt;

    label.appendChild(cb);
    label.appendChild(span);
    container.appendChild(label);
  }
}

function getCheckedValues(container) {
  return Array.from(container.querySelectorAll('input[type="checkbox"]'))
    .filter((cb) => cb.checked)
    .map((cb) => cb.value);
}

function setAllCheckboxes(container, checked) {
  for (const cb of container.querySelectorAll('input[type="checkbox"]')) {
    cb.checked = checked;
  }
}

function populateTypeSubtype() {
  const types = uniqueSorted(allRows.map((r) => r.type));
  elType.innerHTML = "";
  elType.appendChild(new Option("", ""));
  for (const t of types) elType.appendChild(new Option(t, t));

  populateSubtype();
}

function populateSubtype() {
  const selectedType = normalizeStr(elType.value);
  const subset =
    selectedType && selectedType.length > 0
      ? allRows.filter((r) => normalizeStr(r.type) === selectedType)
      : allRows;
  const subtypes = uniqueSorted(subset.map((r) => r.subtype));

  const previous = normalizeStr(elSubtype.value);
  elSubtype.innerHTML = "";
  elSubtype.appendChild(new Option("", ""));
  for (const st of subtypes) elSubtype.appendChild(new Option(st, st));
  if (previous && subtypes.includes(previous)) elSubtype.value = previous;
}

function clearFilters() {
  elType.value = "";
  elSubtype.value = "";
  elName.value = "";
  setAllCheckboxes(elQuality, false);
  setAllCheckboxes(elTypeConf, false);
  setAllCheckboxes(elSubtypeConf, false);
}

// ---- Sorting ----------------------------------------------------------------

function valueForSort(row, key) {
  const v = row[key];
  if (v === null || v === undefined) return { type: "empty", v: "" };

  // Flag ranking for specific columns
  if (
    key === "match_quality" ||
    key === "type_confidence" ||
    key === "subtype_confidence"
  ) {
    const s = toLower(v);
    const rank =
      s && Object.prototype.hasOwnProperty.call(flagRank, s)
        ? flagRank[s]
        : null;
    if (rank !== null) return { type: "number", v: rank };
    return { type: "string", v: s };
  }

  const n = tryNumber(v);
  if (n !== null) return { type: "number", v: n };
  return { type: "string", v: toLower(v) };
}

function compareRows(a, b) {
  if (!sortKey) return (a.__index ?? 0) - (b.__index ?? 0);

  const av = valueForSort(a, sortKey);
  const bv = valueForSort(b, sortKey);

  let cmp = 0;
  if (av.type === "number" && bv.type === "number") cmp = av.v - bv.v;
  else cmp = String(av.v).localeCompare(String(bv.v));

  // Secondary keys: type, subtype, official_name, then stable __index
  if (cmp === 0) cmp = toLower(a.type).localeCompare(toLower(b.type));
  if (cmp === 0) cmp = toLower(a.subtype).localeCompare(toLower(b.subtype));
  if (cmp === 0)
    cmp = toLower(a.official_name).localeCompare(toLower(b.official_name));
  if (cmp === 0) cmp = (a.__index ?? 0) - (b.__index ?? 0);

  return sortDir === "asc" ? cmp : -cmp;
}

// ---- Table rendering ---------------------------------------------------------

function setHeaderSortIndicators() {
  for (const th of elHead.querySelectorAll("th")) {
    th.removeAttribute("data-sort");
    if (sortKey && th.dataset.key === sortKey) th.dataset.sort = sortDir;
  }
}

function renderHeader() {
  const tr = document.createElement("tr");
  for (const col of columns) {
    const th = document.createElement("th");
    th.textContent = col.label || col.key;
    th.dataset.key = col.key;
    th.dataset.col = col.key;
    th.addEventListener("click", () => {
      const key = col.key;
      if (sortKey === key) sortDir = sortDir === "asc" ? "desc" : "asc";
      else {
        sortKey = key;
        sortDir = "asc";
      }
      applyAndRender(false);
    });
    tr.appendChild(th);
  }
  elHead.innerHTML = "";
  elHead.appendChild(tr);
  setHeaderSortIndicators();
}

function visiblePageRows() {
  const total = filteredRows.length;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (page > pages) page = pages;
  if (page < 1) page = 1;
  const start = (page - 1) * pageSize;
  const end = Math.min(total, start + pageSize);
  return { total, pages, start, end, rows: filteredRows.slice(start, end) };
}

function renderBody() {
  const { total, pages, start, end, rows } = visiblePageRows();

  elBody.innerHTML = "";
  for (const row of rows) {
    const tr = document.createElement("tr");
    if (highlightEnabled) {
      if (row.match_kind === "self_template") tr.classList.add("row--known");
      else if (row.match_kind === "new_object") tr.classList.add("row--new");
    }

    for (const col of columns) {
      const td = document.createElement("td");
      td.dataset.col = col.key;
      const v = row[col.key];
      td.textContent = v === null || v === undefined ? "" : String(v);

      // Helpful tooltips for clipped columns
      if (col.key === "internal_name" || col.key === "spectra_file_name") {
        const full = v === null || v === undefined ? "" : String(v);
        if (full) td.title = full;
      }
      tr.appendChild(td);
    }
    elBody.appendChild(tr);
  }

  elSummary.textContent = `Filtered results: ${total} rows`;
  elPageInfo.textContent = `Rows ${total === 0 ? 0 : start + 1}-${end} of ${total}  |  Page ${page}/${pages}`;
  btnPrev.disabled = page <= 1;
  btnNext.disabled = page >= pages;
}

// ---- Apply filters -----------------------------------------------------------

function applyFilters() {
  const typeFilter = normalizeStr(elType.value);
  const subtypeFilter = normalizeStr(elSubtype.value);
  const nameContains = normalizeStr(elName.value).toLowerCase();

  const quality = new Set(getCheckedValues(elQuality));
  const typeConf = new Set(getCheckedValues(elTypeConf));
  const subtypeConf = new Set(getCheckedValues(elSubtypeConf));

  const out = [];
  for (const row of allRows) {
    if (typeFilter && normalizeStr(row.type) !== typeFilter) continue;
    if (subtypeFilter && normalizeStr(row.subtype) !== subtypeFilter) continue;

    if (quality.size > 0 && !quality.has(normalizeStr(row.match_quality))) continue;
    if (
      typeConf.size > 0 &&
      !typeConf.has(normalizeStr(row.type_confidence))
    )
      continue;
    if (
      subtypeConf.size > 0 &&
      !subtypeConf.has(normalizeStr(row.subtype_confidence))
    )
      continue;

    if (nameContains) {
      // Search across multiple identity fields (IAU name, internal names, filenames)
      const haystack = [
        row.official_name,
        row.internal_name,
        row.file,
        row.spectra_file_name,
      ]
        .map((v) => normalizeStr(v).toLowerCase())
        .filter(Boolean)
        .join(" ");
      if (!haystack.includes(nameContains)) continue;
    }

    out.push(row);
  }
  return out;
}

function applyAndRender(resetPage = true) {
  filteredRows = applyFilters();
  filteredRows.sort(compareRows);
  setHeaderSortIndicators();
  if (resetPage) page = 1;

  const hasRows = filteredRows.length > 0;
  btnDownload.disabled = !hasRows;
  btnHighlight.disabled = !hasRows;

  renderBody();
}

// ---- Download ---------------------------------------------------------------

function downloadFilteredCsv() {
  if (!filteredRows || filteredRows.length === 0) return;
  const headers = columns.map((c) => c.key);
  const lines = [];
  lines.push(headers.map(csvEscape).join(","));
  for (const row of filteredRows) {
    const vals = headers.map((k) => csvEscape(row[k]));
    lines.push(vals.join(","));
  }
  downloadText("filtered_wiserep_results.csv", lines.join("\n"), "text/csv");
}

// ---- Data loading ------------------------------------------------------------

async function loadJson(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch ${path}: ${res.status}`);
  return await res.json();
}

function inferColumnsFromRows(rows) {
  if (!rows || rows.length === 0) return [];
  // Hide internal fields that are present for functionality (e.g. highlighting)
  // but should not be shown as table columns.
  const hiddenKeys = new Set(["__index", "match_kind", "zfixed"]);
  const keys = Object.keys(rows[0]).filter((k) => !hiddenKeys.has(k));
  const labelMap = {
    official_name: "IAU name",
    internal_name: "Internal name/s",
    tns_type: "TNS Type",
    type: "SAGE type",
    subtype: "SAGE subtype",
    z_err: "z error",
    match_kind: "Match kind",
  };
  return keys.map((k) => ({
    key: k,
    label: labelMap[k] || k.replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase()),
  }));
}

async function bootstrap() {
  elSummary.textContent = "Loading data...";

  buildCheckboxGroup(elQuality, QUALITY_OPTIONS, "q");
  buildCheckboxGroup(elTypeConf, CONFIDENCE_OPTIONS, "tc");
  buildCheckboxGroup(elSubtypeConf, CONFIDENCE_OPTIONS, "sc");

  // Load meta (optional)
  let meta = null;
  try {
    meta = await loadJson("data/meta.json");
  } catch (e) {
    meta = null;
  }

  // Load data
  allRows = await loadJson("data/wiserep_results.json");

  // Apply meta
  flagRank = (meta && meta.flag_sort_rank) || {
    "no comp": 0,
    "very low": 1,
    low: 2,
    medium: 3,
    high: 4,
  };

  columns = (meta && meta.columns) || inferColumnsFromRows(allRows);

  // Ensure we don’t show internal index
  columns = columns.filter((c) => c.key !== "__index");

  populateTypeSubtype();
  renderHeader();

  // Default sort like the GUI feels: by type then by name (stable)
  sortKey = "type";
  sortDir = "asc";

  applyAndRender(true);
}

// ---- Events -----------------------------------------------------------------

elType.addEventListener("change", () => {
  populateSubtype();
});

btnApply.addEventListener("click", () => {
  applyAndRender(true);
});

btnClear.addEventListener("click", () => {
  clearFilters();
  populateSubtype();
  applyAndRender(true);
});

btnHighlight.addEventListener("click", () => {
  highlightEnabled = !highlightEnabled;
  btnHighlight.textContent = highlightEnabled ? "Unhighlight matches" : "Highlight matches";
  renderBody();
});

btnDownload.addEventListener("click", () => {
  downloadFilteredCsv();
});

btnReload.addEventListener("click", async () => {
  highlightEnabled = false;
  btnHighlight.textContent = "Highlight matches";
  await bootstrap();
});

btnPrev.addEventListener("click", () => {
  page -= 1;
  renderBody();
});

btnNext.addEventListener("click", () => {
  page += 1;
  renderBody();
});

elPageSize.addEventListener("change", () => {
  pageSize = Number(elPageSize.value) || 100;
  page = 1;
  renderBody();
});

// Start
bootstrap().catch((e) => {
  console.error(e);
  const msg = e && e.message ? e.message : String(e);
  elSummary.textContent =
    "Failed to load data: " +
    msg +
    ". Run the exporter to generate docs/table/data/wiserep_results.json";
});

