// The page: pick a pack, hand its bytes to the worker, show stages as they
// run, then offer the converted zip as a download and show the report.
// Nothing is sent anywhere.
const $ = (id) => document.getElementById(id);
const worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
let busy = true;
let urls = [];

function setReady(on, text) {
  busy = !on;
  $("file").disabled = !on;
  $("target").disabled = !on;
  $("drop").setAttribute("aria-disabled", String(!on));
  $("drop-text").textContent = text;
}

function showProblem(text) {
  $("problem").textContent = text;
  $("problem").hidden = !text;
}

function renderStages(names) {
  $("stages").replaceChildren(...names.map((n) => {
    const li = document.createElement("li");
    li.textContent = n;
    li.dataset.stage = n;
    return li;
  }));
}

function start(file) {
  if (busy || !file) return;
  showProblem("");
  $("result").hidden = true;
  $("report-view").hidden = true;
  for (const li of $("stages").children) li.className = "";
  $("progress-title").textContent = `Converting ${file.name}`;
  $("progress").hidden = false;
  setReady(false, "Converting…");
  file.arrayBuffer().then((bytes) => {
    worker.postMessage({ type: "convert", name: file.name, bytes, target: $("target").value },
                       [bytes]);
  });
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
      $("target").replaceChildren(...data.targets.map((t) => new Option(t, t, false, t === data.default)));
      renderStages(data.stages);
      setReady(true, "Drop a 1.8.9 pack .zip here, or click to choose one");
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
      showResult(data);
      setReady(true, "Drop another pack to convert it");
      break;
    case "problem":
      $("progress").hidden = true;
      showProblem(data.message);
      setReady(true, "Drop a 1.8.9 pack .zip here, or click to choose one");
      break;
    case "crash":
      showProblem(`The converter stopped unexpectedly: ${data.message}`);
      setReady(true, "Drop a pack to try again");
      break;
  }
};
worker.onerror = (e) => {
  showProblem(`The converter could not start: ${e.message || "unknown error"}`);
  setReady(false, "Unavailable");
};

$("file").addEventListener("change", (e) => { start(e.target.files[0]); e.target.value = ""; });
const drop = $("drop");
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => {
  e.preventDefault();
  drop.classList.remove("over");
  start(e.dataTransfer.files[0]);
});

worker.postMessage({ type: "boot" });
