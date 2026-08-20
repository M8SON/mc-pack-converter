const $ = (id) => document.getElementById(id);
window._fulls = {};
window._frames = {};

// The model is embedded in the page, so there is nothing to wait for and
// nothing to poll. The previous version had to guard against the bridge's
// api object existing before its methods did; a constant has no such state.
const M = window.MODEL;

function show(view) {
  for (const id of ["findings", "textures"]) $(id).hidden = id !== view;
  for (const b of $("tabs").querySelectorAll("button[data-view]"))
    b.classList.toggle("on", b.dataset.view === view);
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

function renderSheet(sheet) {
  const flagged = new Set(window._flagged || []);
  const parts = sheet.sections.map((s) => `<h2>${esc(s.label)} · ${s.tiles.length}</h2>
    <div class="grid">${s.tiles.map((t) => tile(t, s.label, flagged)).join("")}</div>`);
  if (sheet.excluded.length)
    parts.push(`<h2>Not shown</h2><p class="muted">` +
      sheet.excluded.map((e) => `${e.count} ${esc(e.label.toLowerCase())}`).join(" · ") +
      `</p>`);
  $("textures").innerHTML = parts.join("");
  // `full` is up to 512px of base64 (sheet.py's FULL cap). Measured: stamping
  // that into a data- attribute is what stopped WebView2 responding, so it
  // stays in a side map keyed by path, same as the animation frames below.
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

function openFull(el) {
  const path = el.dataset.path;
  const img = $("lightbox-img");
  clearInterval(lightboxTimer);
  lightboxTimer = null;

  // A tile that turns should keep turning when opened -- the whole reason for
  // the model view is seeing the sides a still frame hides. An animated
  // tile's `full` (Armor excepted, which overwrites it) is a sliver of the
  // raw unsliced strip, so frames must win whenever they exist.
  const frames = window._frames[path];
  if (frames) {
    let i = 0;
    img.src = frames[0];
    lightboxTimer = setInterval(() => {
      i = (i + 1) % frames.length;
      img.src = frames[i];
    }, Number(el.dataset.ft));
  } else {
    // `full` is null whenever the thumbnail already is the original, which is
    // 893 of 1019 tiles on the reference pack -- thumb_data_uri never upscales.
    const uri = window._fulls[path];
    img.src = uri || el.querySelector("img").src;
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

function render() {
  $("headline").textContent = M.headline;
  $("out-name").textContent = M.out_path;
  // The old window's summary line ("0 errors, 5 warnings, 466 notes"),
  // reproduced from M.counts in the same words cli.py's summary_lines uses
  // (cli.py:45) so both front ends read the same.
  $("details").textContent =
    `${M.counts.error} errors, ${M.counts.warning} warnings, ${M.counts.info} notes`;
  const up = $("update");
  up.textContent = M.update || "";
  up.hidden = !M.update;

  window._flagged = M.findings.filter((f) => f.path).map((f) => norm(f.path));
  renderFindings(M);
  renderSheet(M.sheet);
  show("findings");
}

$("tabs").onclick = (e) => { if (e.target.dataset.view) show(e.target.dataset.view); };
$("lightbox").onclick = () => {
  clearInterval(lightboxTimer);   // stop the turn when it is closed
  lightboxTimer = null;
  $("lightbox").hidden = true;
};

document.addEventListener("DOMContentLoaded", render);
