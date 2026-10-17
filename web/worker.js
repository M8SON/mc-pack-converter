// Runs the converter -- the same Python package the desktop build installs --
// on Pyodide, off the page's thread so the page can repaint between stages.
import { loadPyodide } from "./pyodide/pyodide.mjs";

// The desktop CLI's job seam, unchanged: validate_source, then run_job with
// on_stage and write_reports=False, exactly as gui.py calls it.
const GLUE = `
import json
from pathlib import Path
from mc_pack_converter.data import INPUT_FORMAT, load_table
from mc_pack_converter.job import (DEFAULT_TARGET, out_path_beside_source,
                                   run_job, validate_source)
from mc_pack_converter.pipeline import FatalConversionError
from mc_pack_converter.stages import STAGES

def info():
    targets = [k for k in load_table("pack_format") if k != INPUT_FORMAT]
    targets.sort(key=lambda k: tuple(int(p) for p in k.split(".")), reverse=True)
    return json.dumps({"targets": targets, "default": DEFAULT_TARGET,
                       "stages": [name for name, _ in STAGES]})

def convert(source, target, on_stage):
    source = Path(source)
    problem = validate_source(source)
    if problem:
        return json.dumps({"problem": problem})
    out = out_path_beside_source(source, target)
    try:
        result = run_job(source, out, target, on_stage=on_stage,
                         write_reports=False)
    except FatalConversionError as exc:
        return json.dumps({"problem": str(exc)})
    return json.dumps({
        "out": str(out),
        "counts": {s.value: n for s, n in result.counts.items()},
        "findings": [{"stage": f.stage, "severity": f.severity.value,
                      "message": f.message, "path": f.path}
                     for f in result.ctx.findings],
        "reports": result.report_texts,
    })
`;

let py;

async function boot() {
  py = await loadPyodide({ indexURL: new URL("./pyodide/", import.meta.url).href });
  const manifest = await (await fetch(new URL("./py/manifest.json", import.meta.url))).json();
  // Pillow resolves through pyodide-lock.json beside the runtime. The
  // converter's own wheel is loaded by URL, so its Requires-Dist is not
  // resolved -- numpy is only needed by the desktop HTML report, not here.
  await py.loadPackage("pillow");
  await py.loadPackage(new URL(`./py/${manifest.wheel}`, import.meta.url).href);
  py.runPython(GLUE);
  return JSON.parse(py.globals.get("info")());
}

async function convert({ name, bytes, target }) {
  const dir = "/work/in";
  py.FS.mkdirTree(dir);
  // The file's own name, so the output is named like the desktop's:
  // <pack>-<target>.zip. A "/" cannot occur in a File's name.
  const source = `${dir}/${name}`;
  py.FS.writeFile(source, new Uint8Array(bytes));
  const onStage = (stage, i, total) => postMessage({ type: "stage", stage, i, total });
  try {
    const res = JSON.parse(py.globals.get("convert")(source, target, onStage));
    if (res.problem)
      return postMessage({ type: "problem", message: res.problem.replace(source, name) });
    const out = py.FS.readFile(res.out);
    py.FS.unlink(res.out);
    postMessage({ type: "done", ...res, name: res.out.split("/").pop(), zip: out.buffer },
                [out.buffer]);
  } finally {
    py.FS.unlink(source);
  }
}

onmessage = async ({ data }) => {
  try {
    if (data.type === "boot") postMessage({ type: "ready", ...(await boot()) });
    else if (data.type === "convert") await convert(data);
  } catch (e) {
    postMessage({ type: "crash", message: String(e && e.message || e) });
  }
};
