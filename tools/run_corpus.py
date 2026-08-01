#!/usr/bin/env python3
"""Convert a directory of packs and record every decision the converter made.

Why this exists: the proving-ground pack cannot show a bug it does not have.
Running 173 real packs found, in one pass, 14 packs the converter refused
outright, connected textures silently broken in 38% of packs, and a validate
stage that crashed and skipped itself without saying so. None of it was
reachable from one pack.

Usage:
    python tools/run_corpus.py <pack-dir> [-o results.jsonl] [--target 26.1.2]
    python tools/run_corpus.py <pack-dir> --compare old.jsonl

One JSON line per pack: pack_format, timing, output size, every non-INFO
finding, and the stage summary lines. Output archives are written to a temp
path and deleted after their size is recorded — 170 packs would otherwise be
about 10GB.

Resumable: a pack already present in the results file is skipped, so an
interrupted run continues where it stopped. To redo a subset, delete those
lines and re-run.

--compare diffs two result files by warning class, which is how you tell an
improvement from a regression. A change that fixes one class and silently
opens another looks identical to a clean fix in the totals alone.
"""
from __future__ import annotations
import argparse
import collections
import json
import re
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mc_pack_converter.cli import convert           # noqa: E402
from mc_pack_converter.mcmeta import sanitize       # noqa: E402
from mc_pack_converter.pipeline import Severity     # noqa: E402


def pack_format(zpath: Path) -> int | None:
    """pack_format from a pack zip, or None if it cannot be read."""
    try:
        with zipfile.ZipFile(zpath) as zf:
            cand = [n for n in zf.namelist()
                    if n.endswith("pack.mcmeta") and n.count("/") <= 1]
            if not cand:
                return None
            txt = zf.read(cand[0]).decode("utf-8-sig", "replace")
            for attempt in (txt, sanitize(txt)):
                try:
                    p = json.loads(attempt).get("pack", {})
                    return p.get("pack_format") or p.get("min_format")
                except Exception:
                    continue
            m = re.search(r'"pack_format"\s*:\s*(\d+)', txt)
            return int(m.group(1)) if m else None
    except Exception:
        return None


def run(pack_dir: Path, out_path: Path, target: str) -> None:
    packs = sorted(pack_dir.glob("*.zip"))
    done = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            try:
                done.add(json.loads(line)["pack"])
            except Exception:
                pass
    print(f"{len(packs)} packs, {len(done)} already recorded", flush=True)

    with tempfile.TemporaryDirectory(prefix="corpus_") as tmp:
        tmp_zip = Path(tmp) / "out.zip"
        with out_path.open("a") as fh:
            for i, p in enumerate(packs, 1):
                if p.name in done:
                    continue
                fmt = pack_format(p)
                rec: dict = {"pack": p.name, "pack_format": fmt}
                if fmt != 1:
                    rec["skipped"] = f"pack_format {fmt}, not 1"
                    fh.write(json.dumps(rec) + "\n"); fh.flush()
                    print(f"[{i}/{len(packs)}] {'skip':>9s}  {p.name[:52]}", flush=True)
                    continue
                t0 = time.time()
                try:
                    for stale in tmp_zip.parent.glob("out*"):
                        stale.unlink()
                    ctx = convert(p, tmp_zip, target, False)
                    rec["seconds"] = round(time.time() - t0, 1)
                    rec["out_bytes"] = tmp_zip.stat().st_size if tmp_zip.exists() else 0
                    rec["sprites"] = len(ctx.sliced)
                    rec["findings"] = [
                        {"stage": f.stage, "sev": f.severity.value,
                         "msg": f.message, "path": f.path}
                        for f in ctx.findings if f.severity is not Severity.INFO]
                    rec["summaries"] = [f.message for f in ctx.findings
                                        if f.severity is Severity.INFO and f.path is None]
                except Exception as exc:
                    rec["crash"] = f"{type(exc).__name__}: {exc}"
                    rec["traceback"] = traceback.format_exc()[-1500:]
                    rec["seconds"] = round(time.time() - t0, 1)
                fh.write(json.dumps(rec) + "\n"); fh.flush()
                status = "CRASH" if "crash" in rec else f"{len(rec.get('findings', []))} warn"
                print(f"[{i}/{len(packs)}] {status:>9s}  {rec.get('seconds','-')}s  "
                      f"{p.name[:52]}", flush=True)
    print("done", flush=True)


def _classes(rows) -> collections.Counter:
    """Warning counts by (stage, shape), with numbers and quotes generalised."""
    c: collections.Counter = collections.Counter()
    for r in rows:
        for f in r.get("findings", []):
            msg = re.sub(r"\d+", "N", f["msg"])
            msg = re.sub(r"'[^']*'", "'X'", msg)[:70]
            c[(f["stage"], msg)] += 1
    return c


def summarize(rows, label: str) -> collections.Counter:
    conv = [r for r in rows if "crash" not in r and "skipped" not in r]
    crashed = [r for r in rows if "crash" in r]
    stage_crashes = sum(1 for r in conv for f in r.get("findings", [])
                        if "stage crashed" in f["msg"])
    c = _classes(rows)
    print(f"{label}: converted {len(conv)}  crashed {len(crashed)}  "
          f"stage-crashes {stage_crashes}  warnings {sum(c.values())}")
    for r in crashed:
        print(f"    CRASH {r['pack'][:44]}: {r['crash'][:70]}")
    return c


def compare(old_path: Path, new_path: Path) -> int:
    old = [json.loads(l) for l in old_path.read_text().splitlines()]
    new = [json.loads(l) for l in new_path.read_text().splitlines()]
    a = summarize(old, "before")
    b = summarize(new, "after ")
    print("\nwarning classes that changed:")
    changed = False
    for k in sorted(set(a) | set(b), key=lambda k: -abs(b.get(k, 0) - a.get(k, 0))):
        if a.get(k, 0) != b.get(k, 0):
            changed = True
            print(f"   {a.get(k,0):5d} -> {b.get(k,0):5d}   [{k[0]}] {k[1]}")
    if not changed:
        print("   none")
    regressions = [k for k in set(a) | set(b) if b.get(k, 0) > a.get(k, 0)]
    if regressions:
        print(f"\n{len(regressions)} class(es) got WORSE — check these are intended.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="run_corpus")
    ap.add_argument("pack_dir", type=Path, nargs="?")
    ap.add_argument("-o", "--out", type=Path, default=Path("corpus_results.jsonl"))
    ap.add_argument("--target", default="26.1.2")
    ap.add_argument("--compare", type=Path,
                    help="diff an earlier results file against --out and exit")
    args = ap.parse_args(argv)
    if args.compare:
        return compare(args.compare, args.out)
    if not args.pack_dir:
        ap.error("pack_dir is required unless --compare is given")
    run(args.pack_dir, args.out, args.target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
