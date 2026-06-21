const $ = (s) => document.querySelector(s);
const outputSel = $("#output_format");
const inputHidden = $("#input_format");
const fileInput = $("#file");
const inPill = $("#in-pill");
const optionsBox = $("#options");
const filterInput = $("#filter");
const statusEl = $("#status");
const submitBtn = $("#submit");
const setCount = $("#set-count");
const codeEl = $("#code");
const codeLang = $("#code-lang");
const copyBtn = $("#copy");
const LANG_LABEL = {
  curl: "cURL",
  python: "Python · requests",
  js: "JavaScript · fetch",
};

// Format lists are injected by the server into a JSON data island, so there is
// no need to fetch("/formats") on load.
const BOOTSTRAP = JSON.parse(
  document.getElementById("bootstrap-data").textContent,
);
let inputFormats = BOOTSTRAP.input_formats;
let activeLang = "curl";
let snippets = { curl: "", python: "", js: "" };

const ORIGIN = window.location.origin;

function setStatus(msg, kind, busy) {
  statusEl.className = kind || "";
  statusEl.textContent = "";
  if (busy) {
    const sp = document.createElement("span");
    sp.className = "spinner";
    statusEl.append(sp, " " + msg);
  } else {
    statusEl.textContent = msg;
  }
}

function fillSelect(sel, items, placeholder) {
  sel.innerHTML = "";
  if (placeholder) {
    const o = document.createElement("option");
    o.value = "";
    o.textContent = placeholder;
    sel.appendChild(o);
  }
  for (const item of items) {
    const o = document.createElement("option");
    o.value = item;
    o.textContent = item.toUpperCase();
    sel.appendChild(o);
  }
}

function detectInput() {
  const name = fileInput.files?.[0]?.name || "";
  const ext = name.split(".").pop()?.toLowerCase();
  const ok = ext && inputFormats.includes(ext);
  inputHidden.value = ok ? ext : "";
  if (!name) {
    inPill.className = "pill hidden";
  } else if (ok) {
    inPill.textContent = ext;
    inPill.className = "pill";
  } else {
    inPill.textContent = "unsupported";
    inPill.className = "pill empty";
  }
  renderOptions();
}

function fieldFor(opt) {
  const wrap = document.createElement("div");
  wrap.className = "field";
  wrap.dataset.search = (opt.name + " " + (opt.help || "")).toLowerCase();

  const label = document.createElement("label");
  label.textContent = opt.name;
  label.htmlFor = "opt-" + opt.name;
  wrap.appendChild(label);

  let control;
  const defText =
    opt.default === null || opt.default === "" ? null : String(opt.default);

  if (opt.type === "bool") {
    control = document.createElement("select");
    for (const [v, t] of [
      ["", "— default"],
      ["true", "true"],
      ["false", "false"],
    ]) {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = t;
      control.appendChild(o);
    }
  } else if (opt.type === "file") {
    control = document.createElement("input");
    control.type = "file";
  } else if (opt.type === "choice" && opt.choices) {
    control = document.createElement("select");
    const e = document.createElement("option");
    e.value = "";
    e.textContent = "— default";
    control.appendChild(e);
    for (const c of opt.choices) {
      const o = document.createElement("option");
      o.value = c;
      o.textContent = c;
      control.appendChild(o);
    }
  } else {
    control = document.createElement("input");
    control.type =
      opt.type === "int" || opt.type === "float" ? "number" : "text";
    if (opt.type === "float") control.step = "any";
    if (defText !== null) control.placeholder = "default: " + defText;
  }

  control.id = "opt-" + opt.name;
  control.name = opt.name;
  control.dataset.optName = opt.name;
  wrap.appendChild(control);

  if (opt.help) {
    const help = document.createElement("div");
    help.className = "help";
    help.innerHTML = renderHelp(opt.help);
    wrap.appendChild(help);
  }
  return wrap;
}

/**
 * Render Calibre's lightly-marked-up help (bullet lists, paragraphs, URLs,
 * **bold**, `code`) to HTML. Text is escaped first, so it stays injection-safe.
 */
function renderHelp(text) {
  const esc = (s) => {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  };
  const inline = (s) => {
    return esc(s)
      .replace(
        /(https?:\/\/[^\s<]+)/g,
        '<a href="$1" target="_blank" rel="noopener">$1</a>',
      )
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  };

  const lines = text.split("\n");
  const isItem = (l) => l.match(/^\s*[*-]\s+(.*)$/);
  let out = "";
  let para = [];
  const flush = () => {
    if (para.length) {
      out += `<p>${para.map(inline).join(" ")}</p>`;
      para = [];
    }
  };

  for (let i = 0; i < lines.length; ) {
    if (isItem(lines[i])) {
      flush();
      const items = [];
      let m;
      while (i < lines.length && (m = isItem(lines[i]))) {
        items.push(`<li>${inline(m[1])}</li>`);
        i++;
      }
      out += `<ul>${items.join("")}</ul>`;
    } else if (lines[i].trim() === "") {
      flush();
      i++;
    } else {
      para.push(lines[i].trim());
      i++;
    }
  }
  flush();
  return out;
}

async function renderOptions() {
  const inFmt = inputHidden.value;
  const outFmt = outputSel.value;
  if (!inFmt || !outFmt) {
    optionsBox.innerHTML =
      '<p class="empty">Choose a file and output format to see the available options.</p>';
    updateCode();
    return;
  }
  optionsBox.innerHTML =
    '<p class="empty"><span class="spinner"></span> Loading options...</p>';
  let groups;
  try {
    const res = await fetch(`/formats/${inFmt}/${outFmt}/options`);
    if (!res.ok)
      throw new Error((await res.json()).detail || "Failed to load options");
    groups = await res.json();
  } catch (e) {
    optionsBox.innerHTML = `<p class="empty">${e.message}</p>`;
    updateCode();
    return;
  }

  optionsBox.innerHTML = "";
  for (const group of groups) {
    const details = document.createElement("details");
    details.className = "group";

    const summary = document.createElement("summary");
    const dot = '<span class="set-dot" title="has set options"></span>';
    summary.innerHTML = `${group.group}${dot}<span class="count">${group.options.length}</span>`;
    details.appendChild(summary);

    const body = document.createElement("div");
    body.className = "group-body";
    const grid = document.createElement("div");
    grid.className = "grid";
    for (const opt of group.options) grid.appendChild(fieldFor(opt));
    body.appendChild(grid);
    details.appendChild(body);
    optionsBox.appendChild(details);
  }
  applyFilter();
  updateCode();
}

function applyFilter() {
  const query = filterInput.value.trim().toLowerCase();
  for (const group of optionsBox.querySelectorAll("details.group")) {
    let visible = 0;
    for (const field of group.querySelectorAll(".field")) {
      const match = !query || field.dataset.search.includes(query);
      field.classList.toggle("hidden", !match);
      if (match) visible++;
    }
    group.classList.toggle("hidden", visible === 0);
    if (query && visible > 0) group.open = true;
  }
}

function setAllOpen(open) {
  for (const g of optionsBox.querySelectorAll("details.group:not(.hidden)"))
    g.open = open;
}

// --- selection state ---------------------------------------------------
// An option is "set" when it has a value, or — for file inputs — a chosen file.
// Returns {name, value, file}: `file` is the File object for upload fields, else null.
function isSet(c) {
  return c.type === "file"
    ? !!c.files?.length
    : c.value !== "" && c.value != null;
}

function selectedOptions() {
  const out = [];
  for (const c of optionsBox.querySelectorAll("[data-opt-name]")) {
    if (!isSet(c)) continue;
    if (c.type === "file") {
      const f = c.files[0];
      out.push({ name: c.dataset.optName, value: f.name, file: f });
    } else {
      out.push({ name: c.dataset.optName, value: c.value, file: null });
    }
  }
  return out;
}

function refreshSetIndicators() {
  let total = 0;
  for (const group of optionsBox.querySelectorAll("details.group")) {
    let n = 0;
    for (const c of group.querySelectorAll("[data-opt-name]")) {
      if (isSet(c)) n++;
    }
    group.classList.toggle("has-set", n > 0);
    total += n;
  }
  setCount.textContent = total === 1 ? "1 set" : `${total} set`;
}

// --- code generation ---------------------------------------------------
function fileName() {
  return fileInput.files?.[0]?.name || `book.${inputHidden.value || "epub"}`;
}
function outName() {
  const out = outputSel.value || "out";
  const base = fileName().replace(/\.[^.]+$/, "");
  return `${base}.${out}`;
}
const q = (v) => JSON.stringify(String(v)); // safe double-quoted literal

function genCurl(opts, out) {
  const lines = [`curl -X POST ${q(ORIGIN + "/convert")} \\`];
  lines.push(`  -F ${q("file=@" + fileName())} \\`);
  lines.push(`  -F ${q("output_format=" + out)} \\`);
  // File-path options use curl's "@" syntax to attach the file.
  for (const o of opts)
    lines.push(
      `  -F ${q(o.name + "=" + (o.file ? "@" + o.value : o.value))} \\`,
    );
  lines.push(`  -o ${q(outName())}`);
  return lines.join("\n");
}

function genPython(opts, out) {
  const files = [`        "file": open(${q(fileName())}, "rb"),`];
  const data = [`            "output_format": ${q(out)},`];
  for (const o of opts) {
    if (o.file) files.push(`        ${q(o.name)}: open(${q(o.value)}, "rb"),`);
    else data.push(`            ${q(o.name)}: ${q(o.value)},`);
  }
  return [
    "import requests",
    "",
    `url = ${q(ORIGIN + "/convert")}`,
    "",
    "resp = requests.post(",
    "    url,",
    "    files={",
    ...files,
    "    },",
    "    data={",
    ...data,
    "    },",
    ")",
    "",
    "resp.raise_for_status()",
    `with open(${q(outName())}, "wb") as out:`,
    "    out.write(resp.content)",
  ].join("\n");
}

function genJs(opts, out) {
  const appends = [
    'form.append("file", fileInput.files[0]);',
    `form.append("output_format", ${q(out)});`,
  ];
  for (const o of opts) {
    // A file-path option needs a File object; reference it by a placeholder var.
    if (o.file)
      appends.push(
        `form.append(${q(o.name)}, ${o.name}File); // your ${o.value}`,
      );
    else appends.push(`form.append(${q(o.name)}, ${q(o.value)});`);
  }
  return [
    "const form = new FormData();",
    ...appends,
    "",
    `const resp = await fetch(${q(ORIGIN + "/convert")}, {`,
    '  method: "POST",',
    "  body: form,",
    "});",
    "if (!resp.ok) throw new Error(await resp.text());",
    "",
    "const blob = await resp.blob();",
    'const a = document.createElement("a");',
    "a.href = URL.createObjectURL(blob);",
    `a.download = ${q(outName())};`,
    "a.click();",
  ].join("\n");
}

// line-based highlighter (safe: textContent per token)
function highlight(code, lang) {
  codeEl.innerHTML = "";
  for (const raw of code.split("\n")) {
    const line = document.createElement("span");
    line.className = "ln";
    const trimmed = raw.trimStart();
    const isComment =
      (lang === "python" && trimmed.startsWith("#")) ||
      (lang !== "python" && trimmed.startsWith("//"));
    if (isComment) {
      line.classList.add("com");
      line.textContent = raw || "​";
      codeEl.appendChild(line);
      continue;
    }
    // split on double-quoted strings, color them
    const parts = raw.split(/("(?:[^"\\]|\\.)*")/g);
    for (const part of parts) {
      const span = document.createElement("span");
      if (part.startsWith('"') && part.endsWith('"')) span.className = "str";
      span.textContent = part;
      line.appendChild(span);
    }
    if (!raw) line.textContent = "​";
    codeEl.appendChild(line);
  }
}

function updateCode() {
  refreshSetIndicators();
  const out = outputSel.value;
  if (!out) {
    snippets = { curl: "", python: "", js: "" };
    codeEl.innerHTML =
      '<span class="ln com"># select an output format to build the request</span>';
    return;
  }
  const opts = selectedOptions();
  snippets = {
    curl: genCurl(opts, out),
    python: genPython(opts, out),
    js: genJs(opts, out),
  };
  highlight(snippets[activeLang], activeLang);
}

function setLang(lang) {
  activeLang = lang;
  codeLang.textContent = LANG_LABEL[lang];
  for (const t of document.querySelectorAll(".tab"))
    t.classList.toggle("active", t.dataset.lang === lang);
  if (snippets[lang]) highlight(snippets[lang], lang);
  else updateCode();
}

// --- submit ------------------------------------------------------------
async function onSubmit(e) {
  e.preventDefault();
  if (!fileInput.files?.length) return setStatus("Select a file first.", "err");
  if (!inputHidden.value)
    return setStatus("Unsupported input file extension.", "err");
  if (!outputSel.value) return setStatus("Select an output format.", "err");

  const fd = new FormData();
  fd.append("file", fileInput.files[0]);
  fd.append("output_format", outputSel.value);
  for (const o of selectedOptions()) fd.append(o.name, o.file || o.value);

  submitBtn.disabled = true;
  setStatus("Converting...", "", true);
  try {
    const res = await fetch("/convert", { method: "POST", body: fd });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = (await res.json()).detail || detail;
      } catch {}
      throw new Error(detail);
    }
    const blob = await res.blob();
    const dispo = res.headers.get("Content-Disposition") || "";
    const m = dispo.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
    const name = m ? decodeURIComponent(m[1]) : outName();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
    setStatus("Downloaded " + name, "ok");
  } catch (err) {
    setStatus("Error: " + err.message, "err");
  } finally {
    submitBtn.disabled = false;
  }
}

async function copyCode() {
  const text = snippets[activeLang];
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    copyBtn.textContent = "Copied!";
    copyBtn.classList.add("copied");
    setTimeout(() => {
      copyBtn.textContent = "Copy";
      copyBtn.classList.remove("copied");
    }, 1400);
  } catch {
    setStatus("Copy failed — select and copy manually.", "err");
  }
}

fileInput.addEventListener("change", detectInput);
outputSel.addEventListener("change", renderOptions);
filterInput.addEventListener("input", applyFilter);
optionsBox.addEventListener("input", updateCode);
optionsBox.addEventListener("change", updateCode);
$("#expand-all").addEventListener("click", () => setAllOpen(true));
$("#collapse-all").addEventListener("click", () => setAllOpen(false));
$("#tabs").addEventListener("click", (e) => {
  if (e.target.dataset.lang) setLang(e.target.dataset.lang);
});
copyBtn.addEventListener("click", copyCode);
$("#form").addEventListener("submit", onSubmit);

// Populate the output-format dropdown from the injected data and render initial code.
fillSelect(outputSel, BOOTSTRAP.output_formats, "Select...");
updateCode();
