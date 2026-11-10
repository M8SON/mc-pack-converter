// The page: pick one or more packs, hand each one's bytes to the worker in
// turn, show stages as they run, then offer the converted zip as a download
// and show the report. Nothing is sent anywhere. One pack keeps the original
// result, including its automatic download. Several packs are listed: a
// failure stays on its row, and each finished pack has its own download and
// report. Browsers block a burst of downloads, so a batch never clicks them.
const $ = (id) => document.getElementById(id);
const worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
let busy = true;
let urls = [];
let target = null;
// The worker converts one pack at a time and reuses one folder in its
// memory filesystem, so the next file is sent only after this one finishes.
let batch = [];
let current = -1;
let selected = -1;

function setReady(on, text) {
  busy = !on;
  $("choose").disabled = !on;
  for (const b of $("targets").querySelectorAll("button")) b.disabled = !on;
  $("drop-text").textContent = text;
}

function showProblem(text) {
  $("problem").textContent = text;
  $("problem").hidden = !text;
}

function releaseUrls() {
  // The iframe keeps the blob document alive until it navigates away.
  $("report-frame").src = "about:blank";
  urls.forEach(URL.revokeObjectURL);
  urls = [];
}

function renderTargets(targets, current) {
  target = current;
  $("targets").append(...targets.map((t) => {
    const b = document.createElement("button");
    b.textContent = t;
    b.setAttribute("aria-pressed", String(t === current));
    b.onclick = () => {
      target = t;
      for (const o of $("targets").querySelectorAll("button"))
        o.setAttribute("aria-pressed", String(o === b));
    };
    return b;
  }));
}

function renderStages(names) {
  $("stages").replaceChildren(...names.map((n) => {
    const li = document.createElement("li");
    li.textContent = n;
    li.dataset.stage = n;
    return li;
  }));
}

function statusText(item) {
  if (item.status === "waiting") return "Waiting";
  if (item.status === "running") return "Converting";
  if (item.status === "failed") return "Failed";
  return item.counts && item.counts.error ? "Done, with errors" : "Done";
}

function renderQueue() {
  const list = $("packs");
  if (batch.length < 2) {
    list.replaceChildren();
    return;
  }
  list.replaceChildren(...batch.map((item, i) => {
    const li = document.createElement("li");
    if (i === selected) li.classList.add("selected");
    if (item.status === "running") li.setAttribute("aria-current", "step");
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = item.file.name;
    const status = document.createElement("span");
    status.className = `status ${item.status}`;
    status.textContent = statusText(item);
    li.append(name, status);
    if (item.status === "done") {
      const counts = document.createElement("span");
      counts.className = "counts muted";
      const c = item.counts;
      counts.textContent = `${c.error} errors, ${c.warning} warnings, ${c.info} notes`;
      const a = document.createElement("a");
      a.className = "button primary";
      a.href = item.zipUrl;
      a.download = item.outName;
      a.textContent = "Download";
      a.setAttribute("aria-label", `Download ${item.outName}`);
      const report = document.createElement("button");
      report.type = "button";
      report.textContent = "Report";
      report.setAttribute("aria-pressed", String(i === selected));
      report.onclick = () => selectReport(i, true);
      li.append(counts, a, report);
    }
    if (item.error) {
      const err = document.createElement("p");
      err.className = "error";
      err.textContent = item.error;
      li.append(err);
    }
    return li;
  }));
}

function selectReport(i, scroll) {
  const item = batch[i];
  if (!item || !item.reportUrl) return;
  selected = i;
  $("report-frame").src = item.reportUrl;
  $("report-for").textContent = item.file.name;
  $("report-open").href = item.reportUrl;
  const save = $("report-save-multi");
  save.href = item.reportUrl;
  save.download = item.outName.replace(/\.zip$/i, "") + "-report.html";
  $("report-tools").hidden = false;
  $("report-view").hidden = false;
  renderQueue();
  if (scroll) $("report-view").scrollIntoView({ behavior: "smooth" });
}

function remember(i, r) {
  const item = batch[i];
  item.status = "done";
  item.outName = r.name;
  item.counts = r.counts;
  const zip = URL.createObjectURL(new Blob([r.zip], { type: "application/zip" }));
  const report = URL.createObjectURL(new Blob([r.html], { type: "text/html" }));
  item.zipUrl = zip;
  item.reportUrl = report;
  urls.push(zip, report);
}

function finishBatch() {
  current = -1;
  const ok = batch.filter((p) => p.status === "done").length;
  if (batch[batch.length - 1].status !== "done")
    $("progress").hidden = true;
  else if (ok !== batch.length)
    $("progress-title").textContent = `Finished ${ok} of ${batch.length}`;
  // One report document at a time. The others stay blob URLs until chosen,
  // or until the next batch revokes them.
  if (selected < 0) {
    const first = batch.findIndex((p) => p.reportUrl);
    if (first >= 0) selectReport(first, false);
  }
  setReady(true, "Drop packs to convert them");
}

// One pack: the centred problem line, as before. Several: the row keeps the
// error and the next pack starts.
function failCurrent(message, readyText) {
  if (batch.length <= 1) {
    $("progress").hidden = true;
    showProblem(message);
    setReady(true, readyText);
    return;
  }
  const item = batch[current];
  item.status = "failed";
  item.error = message;
  renderQueue();
  convertAt(current + 1);
}

function convertAt(i) {
  if (i >= batch.length) {
    finishBatch();
    return;
  }
  current = i;
  const item = batch[i];
  item.status = "running";
  renderQueue();
  for (const li of $("stages").children) li.className = "";
  $("progress-title").textContent = `Converting ${item.file.name}`;
  $("progress").hidden = false;
  setReady(false, batch.length > 1 ? `Converting ${i + 1} of ${batch.length}…` : "Converting…");
  item.file.arrayBuffer().then((bytes) => {
    if (batch[i] !== item || item.status !== "running") return;
    worker.postMessage({ type: "convert", name: item.file.name, bytes, target },
                       [bytes]);
  }).catch((err) => {
    if (batch[i] !== item || item.status !== "running") return;
    failCurrent(err && err.message ? err.message : "Could not read the file",
                "Drop a 1.8.9 resource pack here");
  });
}

function start(input) {
  const list = [...(input instanceof File ? [input] : input || [])];
  if (busy || list.length === 0) return;
  releaseUrls();
  showProblem("");
  $("result").hidden = true;
  $("report-view").hidden = true;
  $("report-tools").hidden = true;
  selected = -1;
  batch = list.map((file) => ({
    file, status: "waiting", error: "", zipUrl: "", reportUrl: "",
    outName: "", counts: null,
  }));
  $("queue").hidden = list.length < 2;
  renderQueue();
  if (list.length > 1) $("queue").scrollIntoView({ behavior: "smooth" });
  convertAt(0);
}

function showResult(r) {
  const c = r.counts;
  $("result-title").textContent = c.error ? "Converted, with errors" : "Converted";
  $("counts").textContent = `${c.error} errors, ${c.warning} warnings, ${c.info} notes`;
  urls.forEach(URL.revokeObjectURL);
  const zip = URL.createObjectURL(new Blob([r.zip], { type: "application/zip" }));
  const report = URL.createObjectURL(new Blob([r.html], { type: "text/html" }));
  urls = [zip, report];
  const a = $("download");
  a.href = zip;
  a.download = r.name;
  a.textContent = `Download ${r.name}`;
  $("report-tab").href = report;
  $("report-save").href = report;
  $("report-save").download = r.name.replace(/\.zip$/i, "") + "-report.html";
  $("report-frame").src = report;
  $("result").hidden = false;
  $("report-view").hidden = false;
  $("result").scrollIntoView({ behavior: "smooth" });
  a.click();
}

worker.onmessage = ({ data }) => {
  switch (data.type) {
    case "ready":
      renderTargets(data.targets, data.default);
      renderStages(data.stages);
      setReady(true, "Drop a 1.8.9 resource pack here");
      break;
    case "stage":
      [...$("stages").children].forEach((li, k) => {
        li.className = k + 1 < data.i ? "done" : k + 1 === data.i ? "running" : "";
      });
      $("progress-title").textContent = `Stage ${data.i} of ${data.total}: ${data.stage}`;
      break;
    case "report":
      for (const li of $("stages").children) li.className = "done";
      $("progress-title").textContent = "Building the texture report…";
      break;
    case "done":
      for (const li of $("stages").children) li.className = "done";
      $("progress-title").textContent = "All stages finished";
      if (batch.length <= 1) {
        showResult(data);
        setReady(true, "Drop another pack to convert it");
        break;
      }
      remember(current, data);
      renderQueue();
      convertAt(current + 1);
      break;
    case "problem":
      failCurrent(data.message, "Drop a 1.8.9 resource pack here");
      break;
    case "crash":
      if (batch.length > 1 && current >= 0 && batch[current].status === "running")
        failCurrent(`The converter stopped unexpectedly: ${data.message}`,
                    "Drop a pack to try again");
      else {
        showProblem(`The converter stopped unexpectedly: ${data.message}`);
        setReady(true, "Drop a pack to try again");
      }
      break;
  }
};
worker.onerror = (e) => {
  showProblem(`The converter could not start: ${e.message || "unknown error"}`);
  setReady(false, "Unavailable");
};

$("choose").onclick = () => $("file").click();
$("file").addEventListener("change", (e) => { start(e.target.files); e.target.value = ""; });
// The whole window is the drop target, as in the old desktop window. Without
// preventDefault on dragover the browser would open the zip itself instead.
let depth = 0;
addEventListener("dragenter", () => { depth++; document.body.classList.add("dragging"); });
addEventListener("dragleave", () => { if (--depth <= 0) { depth = 0; document.body.classList.remove("dragging"); } });
addEventListener("dragover", (e) => e.preventDefault());
addEventListener("drop", (e) => {
  e.preventDefault();
  depth = 0;
  document.body.classList.remove("dragging");
  start(e.dataTransfer.files);
});

worker.postMessage({ type: "boot" });
