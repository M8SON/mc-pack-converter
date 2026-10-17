"""Assemble the browser converter as static files: build/web/ by default.

    python tools/build_web.py [--out build/web]

The page runs this package, unmodified, on Pyodide (CPython compiled to
WebAssembly). The runtime is SELF-HOSTED next to the page rather than loaded
from a CDN: the page then makes no third-party request at all, so "your pack
never leaves your machine" is checkable in the network tab, it keeps working
where a CDN is blocked, and the runtime cannot change under it. Nothing
binary is committed -- this script fetches the pinned release and checks
every file against a published SHA-256 before using it.

Output:
    index.html, app.js, worker.js, style.css   from web/
    pyodide/                                   the runtime + the Pillow wheel
    py/<this package>.whl, py/manifest.json    the converter itself
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PYODIDE_VERSION = "314.0.7"
# The digest GitHub publishes for the release asset.
CORE_SHA256 = "2abdcc2e35208af406e07724cffa85bc582ced97e9028383ecf5462541393f95"
CORE_URL = (f"https://github.com/pyodide/pyodide/releases/download/"
            f"{PYODIDE_VERSION}/pyodide-core-{PYODIDE_VERSION}.tar.bz2")
# Wheels outside the core tarball; each is checked against the sha256 in the
# (already verified) pyodide-lock.json.
FULL_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
PACKAGES = ["pillow"]
# What the page loads from the core tarball. The .d.ts files, package.json
# and the Node CLI entry points are not needed in a browser.
RUNTIME = ["pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm",
           "python_stdlib.zip", "pyodide-lock.json"]


def fetch(url: str, sha256: str, cache: Path) -> Path:
    dest = cache / url.rsplit("/", 1)[-1]
    if not dest.exists() or hashlib.sha256(dest.read_bytes()).hexdigest() != sha256:
        print(f"fetching {url}")
        with urllib.request.urlopen(url) as r:
            dest.write_bytes(r.read())
    got = hashlib.sha256(dest.read_bytes()).hexdigest()
    if got != sha256:
        sys.exit(f"sha256 mismatch for {url}: expected {sha256}, got {got}")
    return dest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="build_web")
    ap.add_argument("--out", type=Path, default=REPO / "build" / "web")
    args = ap.parse_args(argv)
    out: Path = args.out
    cache = REPO / "build" / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    if out.exists():
        shutil.rmtree(out)
    (out / "pyodide").mkdir(parents=True)
    (out / "py").mkdir()

    core = fetch(CORE_URL, CORE_SHA256, cache)
    with tarfile.open(core) as tar:
        for name in RUNTIME:
            member = tar.getmember(f"pyodide/{name}")
            (out / "pyodide" / name).write_bytes(tar.extractfile(member).read())

    lock = json.loads((out / "pyodide" / "pyodide-lock.json").read_text())
    for name in PACKAGES:
        entry = lock["packages"][name]
        if entry["depends"]:
            sys.exit(f"{name} now depends on {entry['depends']}; add them to PACKAGES")
        wheel = fetch(FULL_URL + entry["file_name"], entry["sha256"], cache)
        shutil.copy(wheel, out / "pyodide" / entry["file_name"])

    subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--quiet",
                    "-w", str(out / "py"), str(REPO)], check=True)
    wheels = list((out / "py").glob("mc_pack_converter-*.whl"))
    if len(wheels) != 1:
        sys.exit(f"expected one converter wheel, found {wheels}")
    (out / "py" / "manifest.json").write_text(json.dumps({"wheel": wheels[0].name}))

    for f in (REPO / "web").iterdir():
        shutil.copy(f, out / f.name)

    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"wrote {out} ({total / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
