const $ = (id) => document.getElementById(id);
let sheetLoaded = false;
window._fulls = {};
window._frames = {};
let chosenTarget = "";
let lastScreen = "";

function show(view) {
  for (const id of ["idle", "findings", "textures", "error"]) $(id).hidden = id !== view;
  for (const b of $("tabs").querySelectorAll("button[data-view]"))
    b.classList.toggle("on", b.dataset.view === view);
  if (view === "textures" && !sheetLoaded) loadSheet();
}

function renderFindings(d) {
  const item = (f) => `<div class="finding ${f.severity}">${esc(f.message)}
    <div class="where">${esc(f.stage)}${f.path ? " · " + esc(f.path) : ""}</div></div>`;
  const loud = d.findings.filter((f) => f.severity !== "info");
  const notes = d.findings.filter((f) => f.severity === "info");
  $("findings").innerHTML =
    (loud.length ? loud.map(item).join("") : `<p class="muted">Nothing to flag.</p>`) +
    (notes.length ? `<details><summary>Show ${notes.length} notes</summary>
       ${notes.map(item).join("")}</details>` : "");
}

async function loadSheet() {
  sheetLoaded = true;
  const sheet = await window.pywebview.api.sheet();
  const flagged = new Set(window._flagged || []);
  const parts = sheet.sections.map((s) => `<h2>${esc(s.label)} · ${s.tiles.length}</h2>
    <div class="grid">${s.tiles.map((t) => tile(t, s.label, flagged)).join("")}</div>`);
  if (sheet.excluded.length)
    parts.push(`<h2>Not shown</h2><p class="muted">` +
      sheet.excluded.map((e) => `${e.count} ${esc(e.label.toLowerCase())}`).join(" · ") +
      `</p>`);
  $("textures").innerHTML = parts.join("");
  // Armor tiles carry their own big render; everything else asks Python for
  // the original texture on demand. Keyed here rather than stamped into a
  // data- attribute so a 40 KB data URI never lands in the DOM.
  for (const s of sheet.sections)
    for (const t of s.tiles) if (t.full) window._fulls[t.path] = t.full;
  for (const el of $("textures").querySelectorAll(".tile"))
    el.onclick = () => openFull(el);
  for (const el of $("textures").querySelectorAll(".tile[data-anim]")) animate(el);
}

function tile(t, label, flagged) {
  const cls = ["tile", label === "Armor" ? "armor" : "",
               label === "Animated" ? "animated" : "",
               flagged.has(norm(t.path)) ? "flagged" : ""].join(" ");
  // The frames live in a map, NOT in a data- attribute: 20 animated tiles at
  // 24 base64 frames each put megabytes of text into the DOM, and WebView2
  // stops responding under it.
  if (t.frames) window._frames[t.path] = t.frames;
  const frames = t.frames ? ` data-anim="1" data-ft="${t.frametime}"` : "";
  const src = t.frames ? t.frames[0] : t.thumb;
  return `<div class="${cls}" data-path="${esc(t.path)}"${frames}>
    <img src="${src}" alt=""><span class="cap">${esc(t.name)}</span>
    <span class="cap">${t.w}×${t.h}</span></div>`;
}

function animate(el) {
  const frames = window._frames[el.dataset.path];
  if (!frames) return;
  const img = el.querySelector("img");
  let i = 0;
  setInterval(() => { i = (i + 1) % frames.length; img.src = frames[i]; },
              Number(el.dataset.ft));
}

let lightboxTimer = null;

async function openFull(el) {
  const path = el.dataset.path;
  const img = $("lightbox-img");
  clearInterval(lightboxTimer);
  lightboxTimer = null;

  // A tile that turns should keep turning when opened -- the whole reason for
  // the model view is seeing the sides a still frame hides.
  const frames = window._frames[path];
  if (frames) {
    let i = 0;
    img.src = frames[0];
    lightboxTimer = setInterval(() => {
      i = (i + 1) % frames.length;
      img.src = frames[i];
    }, Number(el.dataset.ft));
  } else {
    const uri = window._fulls[path] || await window.pywebview.api.texture(path);
    if (!uri) return;
    img.src = uri;
  }
  $("lightbox").hidden = false;
}

// Finding paths come in four shapes across the pipeline: "assets/...",
// "/...", "textures/..." and "optifine/...". Strip both leading separators and
// the assets/minecraft/ prefix so a finding and a tile land on the same key.
const norm = (p) => String(p ?? "")
  .replace(/^\/+/, "").replace(/^assets\/minecraft\//, "");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let pollFails = 0;

// A second pack may be dropped once the first has finished, so everything the
// page is holding about the previous one has to go with it. Without this the
// Textures tab keeps serving the pack before last from sheetLoaded, and the
// full-size images and animation frames are keyed by path, so they collide.
function forgetPreviousRun() {
  sheetLoaded = false;
  window._fulls = {};
  window._frames = {};
  window._flagged = [];
  $("textures").innerHTML = `<p class="muted">Building the sheet…</p>`;
  $("findings").innerHTML = "";
}


// The window wears the converted pack: its stone and ore underfoot, its grass
// block along the top. The ground is a whole field of blocks rather than one
// tile, so Python measures it and sends the size along.
function dress(d) {
  const css = document.body.style;
  if (d.background) {
    css.setProperty("--pack-bg", `url("${d.background}")`);
    if (d.backgroundSize) css.setProperty("--pack-bg-size", d.backgroundSize);
  }
  if (d.grass) css.setProperty("--pack-grass", `url("${d.grass}")`);
}

async function tick() {
  try {
    const d = await window.pywebview.api.poll();
    pollFails = 0;
    $("headline").textContent = d.headline;
    $("details").textContent = d.details.join("\n");
    $("bar").hidden = d.screen !== "progress";
    if (d.total) { $("bar").max = d.total; $("bar").value = d.done; }
    dress(d);          // BEFORE the early returns below, or the drop screen --
                       // which is the whole reason the last pack is cached --
                       // would never wear anything but the shipped stand-in.
    if (d.screen !== lastScreen) {
      if (d.screen === "progress") forgetPreviousRun();
      lastScreen = d.screen;
    }

    if (d.screen === "idle") { $("tabs").hidden = true; show("idle"); return setTimeout(tick, 250); }
    if (d.screen === "progress") { show("idle"); $("dropzone").hidden = true;
                                   return setTimeout(tick, 120); }
    if (d.screen === "error") { $("trace").textContent = d.error_details; show("error"); return; }

    window._flagged = d.findings.filter((f) => f.path).map((f) => norm(f.path));
    $("tabs").hidden = false;
    renderFindings(d);
    show("findings");
  } catch (err) {
    // A windowed exe has no console. A dead poll loop would freeze the page on
    // "Starting..." forever with nothing to show, so retry a few times and then
    // say what happened rather than failing silently.
    if (++pollFails < 4) return setTimeout(tick, 250);
    $("headline").textContent = "Something went wrong";
    $("details").textContent = "The page stopped receiving updates.";
    $("tabs").hidden = true;
    $("trace").textContent = String((err && err.stack) || err);
    show("error");
  }
}

$("tabs").onclick = (e) => { if (e.target.dataset.view) show(e.target.dataset.view); };
$("open-folder").onclick = () => window.pywebview.api.open_folder();
$("lightbox").onclick = () => {
  clearInterval(lightboxTimer);   // stop the turn when it is closed
  lightboxTimer = null;
  $("lightbox").hidden = true;
};
$("copy").onclick = async () => {
  try {
    await navigator.clipboard.writeText($("trace").textContent);
    $("copy").textContent = "Copied";
  } catch {
    // The Clipboard API is absent or blocked in some embedded webviews, and this
    // button is how a user reports a crash. Select the text so it can still be
    // copied by hand rather than leaving a button that does nothing.
    const range = document.createRange();
    range.selectNodeContents($("trace"));
    const sel = getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    $("copy").textContent = "Press Ctrl+C to copy";
  }
};
async function submit(path) {
  $("drop-error").textContent = "";
  const problem = await window.pywebview.api.start(path, chosenTarget);
  if (problem) $("drop-error").textContent = problem;
}

// The whole window is the drop target, not a small rectangle to aim at.
document.addEventListener("dragover", (e) => {
  e.preventDefault();
  document.body.classList.add("dragging");
});
document.addEventListener("dragleave", (e) => {
  if (e.relatedTarget === null) document.body.classList.remove("dragging");
});
document.addEventListener("drop", (e) => {
  e.preventDefault();
  document.body.classList.remove("dragging");
  const file = e.dataTransfer.files[0];
  // pywebview stamps the real filesystem path on the File object; a browser
  // never exposes one, so this is the only way a dropped pack is usable.
  const path = file && (file.pywebviewFullPath || file.path);
  if (path) submit(path);
  else $("drop-error").textContent = "Could not read that file's location.";
});

$("choose").onclick = async () => {
  const path = await window.pywebview.api.pick();
  if (path) submit(path);
};

async function loadTargets() {
  const { targets, current } = await window.pywebview.api.targets();
  chosenTarget = current;
  $("targets").innerHTML = "<span class=\"label\">Convert to</span>" +
    targets.map((t) => `<button data-target="${esc(t)}"` +
      `${t === current ? ' class="on"' : ""}>${esc(t)}</button>`).join("");
  $("targets").onclick = (e) => {
    const t = e.target.dataset.target;
    if (!t) return;
    chosenTarget = t;
    for (const b of $("targets").querySelectorAll("button"))
      b.classList.toggle("on", b.dataset.target === t);
  };
}

window.addEventListener("pywebviewready", () => { loadTargets(); tick(); });
