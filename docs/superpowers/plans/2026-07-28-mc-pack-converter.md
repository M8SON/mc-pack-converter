# Minecraft Texture Pack Converter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python CLI that converts a Minecraft Java 1.8.9-era resource pack into a working 26.2 pack, correctly handling fire, GUI sprites, reorganized entity textures (chest), and OptiFine custom sky, emitting a conversion report and a null-texture safety report.

**Architecture:** An ordered pipeline of isolated stages runs over a working copy of the pack. Each stage is a pure function `(ctx: ConversionContext) -> None` that mutates the working tree and appends `Finding`s. Large lookup tables live as JSON data files loaded at runtime, separate from code.

**Tech Stack:** Python 3.11+ (stdlib), Pillow (image work), pytest (tests).

## Global Constraints

- Target Minecraft version: **26.2** (Java Edition). Exact `pack_format` value is resolved from `data/pack_format.json` (Task 12) — never hardcode it in stage code.
- **Fix and format — never create art.** Stages only rename, move, cut/paste existing pixels, slice sheets, or validate. No stage generates new texture content.
- Un-themed modern assets falling back to vanilla is acceptable and is NOT a failure. Only genuine purple/black-causing conditions are flagged.
- **Fail-soft per file:** an unexpected/bad file appends a `warning` Finding and is skipped; it never aborts the run. Hard-fail only on: input is not a valid pack, or output path is unwritable.
- Data tables are loaded from `mc_pack_converter/data/*.json`; code must not embed table contents inline.
- TDD: every code change is preceded by a failing test. Commit after each task.
- Python style: type hints on public functions, `pathlib.Path` for all paths, no `os.path` string munging.

---

## File Structure

```
mc_pack_converter/
  __init__.py
  cli.py                 # arg parsing + orchestration
  pipeline.py            # ConversionContext, Finding, Severity, run_pipeline
  report.py              # render conversion + null-texture reports from findings
  imaging.py             # Pillow helpers: dims, validate, crop_paste, slice_sheet
  data/
    flattening.json      # old->new file renames
    region_remap.json    # per-texture source-rect -> dest-rect
    ctm_blocks.json      # legacy CTM key -> modern matchBlocks
    gui_sprites.json     # sheet -> [{name,x,y,w,h,ninepatch?}]
    sound_map.json       # old sound path -> new sound path
    pack_format.json     # version string -> pack_format int
  stages/
    __init__.py          # STAGES: ordered list of (name, callable)
    ingest.py
    clean.py
    restructure.py
    flatten_rename.py
    atlas_remap.py
    optifine.py
    gui_sprites.py
    sounds.py
    pack_meta.py
    validate.py
    package.py
tests/
  conftest.py            # fixtures: tmp mini-pack builder
  fixtures/              # synthetic mini packs; M8SON pack symlink for golden test
  test_*.py              # one per module/stage
pyproject.toml
```

---

## Task 1: Project scaffold, ConversionContext, pipeline runner

**Files:**
- Create: `pyproject.toml`, `mc_pack_converter/__init__.py`, `mc_pack_converter/pipeline.py`
- Test: `tests/test_pipeline.py`, `tests/conftest.py`

**Interfaces:**
- Produces:
  - `class Severity(enum.Enum): INFO, WARNING, ERROR`
  - `@dataclass Finding: stage: str; severity: Severity; message: str; path: str | None = None`
  - `@dataclass ConversionContext: root: Path; findings: list[Finding]; target: str = "26.2"` with method `add(self, stage, severity, message, path=None) -> None`
  - `def run_pipeline(ctx: ConversionContext, stages: list[tuple[str, Callable[[ConversionContext], None]]]) -> None` — runs stages in order; an exception in a stage is caught, recorded as an ERROR finding, and (unless it is a `FatalConversionError`) the pipeline continues.
  - `class FatalConversionError(Exception)` — raised by stages for hard-fail conditions; re-raised by `run_pipeline`.

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "mc-pack-converter"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["Pillow>=10.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
mc-pack-converter = "mc_pack_converter.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write conftest.py mini-pack builder fixture**

```python
# tests/conftest.py
from pathlib import Path
import pytest

@pytest.fixture
def mini_pack(tmp_path: Path):
    """Build a minimal 1.8.9-style pack tree; return its root Path."""
    def _build(files: dict[str, bytes] | None = None) -> Path:
        root = tmp_path / "pack"
        (root / "assets/minecraft/textures/blocks").mkdir(parents=True)
        (root / "pack.mcmeta").write_text(
            '{"pack":{"pack_format":1,"description":"test"}}'
        )
        for rel, data in (files or {}).items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return root
    return _build
```

- [ ] **Step 3: Write failing test for context + pipeline**

```python
# tests/test_pipeline.py
from mc_pack_converter.pipeline import (
    ConversionContext, Finding, Severity, run_pipeline, FatalConversionError,
)

def test_run_pipeline_runs_stages_in_order(tmp_path):
    ctx = ConversionContext(root=tmp_path, findings=[])
    order = []
    stages = [("a", lambda c: order.append("a")),
              ("b", lambda c: order.append("b"))]
    run_pipeline(ctx, stages)
    assert order == ["a", "b"]

def test_stage_exception_recorded_and_continues(tmp_path):
    ctx = ConversionContext(root=tmp_path, findings=[])
    def boom(c): raise ValueError("nope")
    ran_after = []
    run_pipeline(ctx, [("boom", boom), ("after", lambda c: ran_after.append(1))])
    assert ran_after == [1]
    assert any(f.severity is Severity.ERROR and f.stage == "boom" for f in ctx.findings)

def test_fatal_error_aborts(tmp_path):
    ctx = ConversionContext(root=tmp_path, findings=[])
    def fatal(c): raise FatalConversionError("bad pack")
    import pytest
    with pytest.raises(FatalConversionError):
        run_pipeline(ctx, [("fatal", fatal)])
```

- [ ] **Step 4: Run tests, verify they fail**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL (ImportError: cannot import ConversionContext).

- [ ] **Step 5: Implement pipeline.py**

```python
# mc_pack_converter/pipeline.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class FatalConversionError(Exception):
    """Hard-fail: invalid pack or unwritable output."""

@dataclass
class Finding:
    stage: str
    severity: Severity
    message: str
    path: str | None = None

@dataclass
class ConversionContext:
    root: Path
    findings: list[Finding] = field(default_factory=list)
    target: str = "26.2"

    def add(self, stage: str, severity: Severity, message: str,
            path: str | None = None) -> None:
        self.findings.append(Finding(stage, severity, message, path))

def run_pipeline(
    ctx: ConversionContext,
    stages: list[tuple[str, Callable[[ConversionContext], None]]],
) -> None:
    for name, fn in stages:
        try:
            fn(ctx)
        except FatalConversionError:
            raise
        except Exception as exc:  # fail-soft
            ctx.add(name, Severity.ERROR, f"stage crashed: {exc!r}")
```

- [ ] **Step 6: Run tests, verify pass**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml mc_pack_converter/ tests/
git commit -m "feat: pipeline runner, ConversionContext, Finding model"
```

---

## Task 2: Report rendering

**Files:**
- Create: `mc_pack_converter/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `Finding`, `Severity` from `pipeline`.
- Produces:
  - `def render_conversion_report(findings: list[Finding]) -> str` — Markdown grouped by stage.
  - `def render_null_texture_report(findings: list[Finding]) -> str` — lists only WARNING/ERROR findings whose stage is `"validate"`; header line `"0 null-texture risks"` when none.

- [ ] **Step 1: Write failing test**

```python
# tests/test_report.py
from mc_pack_converter.pipeline import Finding, Severity
from mc_pack_converter.report import render_conversion_report, render_null_texture_report

def test_conversion_report_groups_by_stage():
    fs = [Finding("clean", Severity.INFO, "removed 5 junk files"),
          Finding("validate", Severity.WARNING, "bad mcmeta", "block/fire_0.png")]
    out = render_conversion_report(fs)
    assert "## clean" in out and "removed 5 junk files" in out
    assert "block/fire_0.png" in out

def test_null_texture_report_zero_when_clean():
    assert "0 null-texture risks" in render_null_texture_report([])

def test_null_texture_report_lists_validate_issues():
    fs = [Finding("validate", Severity.ERROR, "corrupt png", "item/apple.png"),
          Finding("clean", Severity.INFO, "ignore me")]
    out = render_null_texture_report(fs)
    assert "corrupt png" in out and "item/apple.png" in out
    assert "ignore me" not in out
```

- [ ] **Step 2: Run test, verify fail**

Run: `pytest tests/test_report.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement report.py**

```python
# mc_pack_converter/report.py
from __future__ import annotations
from collections import defaultdict
from .pipeline import Finding, Severity

def render_conversion_report(findings: list[Finding]) -> str:
    by_stage: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_stage[f.stage].append(f)
    lines = ["# Conversion Report", ""]
    for stage, items in by_stage.items():
        lines.append(f"## {stage}")
        for f in items:
            loc = f" (`{f.path}`)" if f.path else ""
            lines.append(f"- **{f.severity.value}**: {f.message}{loc}")
        lines.append("")
    return "\n".join(lines)

def render_null_texture_report(findings: list[Finding]) -> str:
    risks = [f for f in findings
             if f.stage == "validate" and f.severity in (Severity.WARNING, Severity.ERROR)]
    lines = ["# Null-Texture Safety Report", ""]
    if not risks:
        lines.append("0 null-texture risks")
        return "\n".join(lines)
    for f in risks:
        loc = f" (`{f.path}`)" if f.path else ""
        lines.append(f"- **{f.severity.value}**: {f.message}{loc}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_report.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add mc_pack_converter/report.py tests/test_report.py
git commit -m "feat: conversion + null-texture report rendering"
```

---

## Task 3: Imaging helpers

**Files:**
- Create: `mc_pack_converter/imaging.py`
- Test: `tests/test_imaging.py`

**Interfaces:**
- Produces:
  - `def png_size(path: Path) -> tuple[int, int]`
  - `def is_valid_png(path: Path) -> bool` — False on zero-byte or unreadable.
  - `def crop_paste(src: Path, dst: Path, regions: list[dict], out_size: tuple[int,int]) -> None` — each region `{"src":[x,y,w,h], "dst":[x,y,w,h]}`; resizes each cropped region to dst w/h (nearest) and pastes onto a new transparent image of `out_size`, writes to `dst`.
  - `def slice_sheet(sheet: Path, out_dir: Path, specs: list[dict]) -> list[Path]` — each spec `{"name","x","y","w","h"}`; crops and writes `out_dir/name.png`; returns written paths.

- [ ] **Step 1: Write failing test**

```python
# tests/test_imaging.py
from pathlib import Path
from PIL import Image
from mc_pack_converter.imaging import png_size, is_valid_png, crop_paste, slice_sheet

def _make(path: Path, size, color=(255,0,0,255)):
    Image.new("RGBA", size, color).save(path)

def test_png_size(tmp_path):
    p = tmp_path/"a.png"; _make(p,(16,32))
    assert png_size(p) == (16,32)

def test_is_valid_png_false_on_empty(tmp_path):
    p = tmp_path/"z.png"; p.write_bytes(b"")
    assert is_valid_png(p) is False

def test_slice_sheet_writes_named_crops(tmp_path):
    sheet = tmp_path/"widgets.png"; _make(sheet,(256,256))
    out = tmp_path/"sprites"; out.mkdir()
    written = slice_sheet(sheet, out, [{"name":"hotbar","x":0,"y":0,"w":182,"h":22}])
    assert (out/"hotbar.png").exists()
    assert png_size(out/"hotbar.png") == (182,22)

def test_crop_paste_produces_out_size(tmp_path):
    src = tmp_path/"chest.png"; _make(src,(64,64))
    dst = tmp_path/"out.png"
    crop_paste(src, dst, [{"src":[0,0,14,14],"dst":[0,0,14,14]}], out_size=(64,64))
    assert png_size(dst) == (64,64)
```

- [ ] **Step 2: Run test, verify fail**

Run: `pytest tests/test_imaging.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement imaging.py**

```python
# mc_pack_converter/imaging.py
from __future__ import annotations
from pathlib import Path
from PIL import Image

def png_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as im:
        return im.size

def is_valid_png(path: Path) -> bool:
    try:
        if path.stat().st_size == 0:
            return False
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        return False

def crop_paste(src: Path, dst: Path, regions: list[dict],
               out_size: tuple[int, int]) -> None:
    with Image.open(src) as im:
        im = im.convert("RGBA")
        canvas = Image.new("RGBA", out_size, (0, 0, 0, 0))
        for r in regions:
            sx, sy, sw, sh = r["src"]
            dx, dy, dw, dh = r["dst"]
            piece = im.crop((sx, sy, sx + sw, sy + sh))
            if (sw, sh) != (dw, dh):
                piece = piece.resize((dw, dh), Image.NEAREST)
            canvas.paste(piece, (dx, dy))
        dst.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(dst)

def slice_sheet(sheet: Path, out_dir: Path, specs: list[dict]) -> list[Path]:
    written: list[Path] = []
    with Image.open(sheet) as im:
        im = im.convert("RGBA")
        for s in specs:
            x, y, w, h = s["x"], s["y"], s["w"], s["h"]
            crop = im.crop((x, y, x + w, y + h))
            out = out_dir / f"{s['name']}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            crop.save(out)
            written.append(out)
    return written
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_imaging.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add mc_pack_converter/imaging.py tests/test_imaging.py
git commit -m "feat: Pillow imaging helpers (size, validate, crop_paste, slice_sheet)"
```

---

## Task 4: Ingest stage

**Files:**
- Create: `mc_pack_converter/stages/__init__.py`, `mc_pack_converter/stages/ingest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `ConversionContext`, `FatalConversionError`, `Severity`.
- Produces:
  - `def prepare_working_copy(source: Path, workdir: Path) -> Path` — if `source` is a `.zip`, extract into `workdir`; else copytree; return the pack root (the dir containing `pack.mcmeta`, searching one level down if needed).
  - `def ingest(ctx: ConversionContext) -> None` — asserts `ctx.root/pack.mcmeta` exists with `pack_format == 1` (else `FatalConversionError`); adds INFO finding with detected format. If `pack_format` already >= modern floor (from pack_format.json, Task 12; until then treat >1 as already-converted), add WARNING "looks already converted".
- `STAGES` list in `stages/__init__.py` starts empty and gains entries as stages land (final wiring in Task 15).

- [ ] **Step 1: Write failing test**

```python
# tests/test_ingest.py
import json, pytest
from pathlib import Path
from mc_pack_converter.pipeline import ConversionContext, Severity, FatalConversionError
from mc_pack_converter.stages.ingest import ingest, prepare_working_copy

def test_ingest_accepts_format_1(mini_pack):
    root = mini_pack()
    ctx = ConversionContext(root=root)
    ingest(ctx)
    assert any(f.severity is Severity.INFO for f in ctx.findings)

def test_ingest_rejects_non_pack(tmp_path):
    ctx = ConversionContext(root=tmp_path)
    with pytest.raises(FatalConversionError):
        ingest(ctx)

def test_prepare_working_copy_from_folder(mini_pack, tmp_path):
    root = mini_pack()
    work = tmp_path/"work"
    out = prepare_working_copy(root, work)
    assert (out/"pack.mcmeta").exists()
```

- [ ] **Step 2: Run test, verify fail**

Run: `pytest tests/test_ingest.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement stages/__init__.py and ingest.py**

```python
# mc_pack_converter/stages/__init__.py
STAGES = []  # populated in Task 15 (cli wiring)
```

```python
# mc_pack_converter/stages/ingest.py
from __future__ import annotations
import json, shutil, zipfile
from pathlib import Path
from ..pipeline import ConversionContext, Severity, FatalConversionError

def _find_pack_root(base: Path) -> Path:
    if (base / "pack.mcmeta").exists():
        return base
    for child in base.iterdir():
        if child.is_dir() and (child / "pack.mcmeta").exists():
            return child
    return base

def prepare_working_copy(source: Path, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    if source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as zf:
            zf.extractall(workdir)
        return _find_pack_root(workdir)
    dest = workdir / source.name
    shutil.copytree(source, dest)
    return _find_pack_root(dest)

def ingest(ctx: ConversionContext) -> None:
    meta = ctx.root / "pack.mcmeta"
    if not meta.exists():
        raise FatalConversionError(f"no pack.mcmeta at {ctx.root}")
    try:
        fmt = json.loads(meta.read_text())["pack"]["pack_format"]
    except Exception as exc:
        raise FatalConversionError(f"unreadable pack.mcmeta: {exc}")
    ctx.add("ingest", Severity.INFO, f"detected pack_format={fmt}")
    if fmt != 1:
        ctx.add("ingest", Severity.WARNING,
                f"pack_format is {fmt}, expected 1; may already be converted")
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_ingest.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add mc_pack_converter/stages/ tests/test_ingest.py
git commit -m "feat: ingest stage + working-copy prep"
```

---

## Task 5: Clean stage

**Files:**
- Create: `mc_pack_converter/stages/clean.py`
- Test: `tests/test_clean.py`

**Interfaces:**
- Produces: `def clean(ctx: ConversionContext) -> None` — deletes junk matching: any name ending `:Zone.Identifier`, `Thumbs.db`, `.DS_Store`, `desktop.ini`, and any file ending `.png~`. Adds one INFO finding with the total count removed.

- [ ] **Step 1: Write failing test**

```python
# tests/test_clean.py
from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages.clean import clean

def test_clean_removes_junk(mini_pack):
    root = mini_pack({
        "assets/minecraft/textures/blocks/stone.png:Zone.Identifier": b"x",
        "assets/minecraft/textures/blocks/Thumbs.db": b"x",
        "assets/minecraft/textures/gui/widgets.png~": b"x",
        "assets/minecraft/textures/blocks/stone.png": b"realpng",
    })
    ctx = ConversionContext(root=root)
    clean(ctx)
    tex = root/"assets/minecraft/textures"
    assert not (tex/"blocks/stone.png:Zone.Identifier").exists()
    assert not (tex/"blocks/Thumbs.db").exists()
    assert not (tex/"gui/widgets.png~").exists()
    assert (tex/"blocks/stone.png").exists()
    assert any("3" in f.message for f in ctx.findings if f.severity is Severity.INFO)
```

- [ ] **Step 2: Run test, verify fail**

Run: `pytest tests/test_clean.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement clean.py**

```python
# mc_pack_converter/stages/clean.py
from __future__ import annotations
from pathlib import Path
from ..pipeline import ConversionContext, Severity

_EXACT = {"Thumbs.db", ".DS_Store", "desktop.ini"}

def _is_junk(name: str) -> bool:
    return (name.endswith(":Zone.Identifier")
            or name.endswith(".png~")
            or name in _EXACT)

def clean(ctx: ConversionContext) -> None:
    removed = 0
    for p in list(ctx.root.rglob("*")):
        if p.is_file() and _is_junk(p.name):
            p.unlink()
            removed += 1
    ctx.add("clean", Severity.INFO, f"removed {removed} junk files")
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_clean.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mc_pack_converter/stages/clean.py tests/test_clean.py
git commit -m "feat: clean stage strips OS/editor junk files"
```

---

## Task 6: Restructure stage (folder renames)

**Files:**
- Create: `mc_pack_converter/stages/restructure.py`
- Test: `tests/test_restructure.py`

**Interfaces:**
- Produces: `def restructure(ctx: ConversionContext) -> None` — under `assets/minecraft/`: rename `textures/blocks`→`textures/block`, `textures/items`→`textures/item`, `mcpatcher`→`optifine`. Each rename that occurs adds an INFO finding. Missing source dir is a silent no-op (fail-soft).

- [ ] **Step 1: Write failing test**

```python
# tests/test_restructure.py
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.restructure import restructure

def test_restructure_renames_dirs(mini_pack):
    root = mini_pack({
        "assets/minecraft/textures/items/apple.png": b"x",
        "assets/minecraft/mcpatcher/sky/world0/sky1.properties": b"x",
    })
    ctx = ConversionContext(root=root)
    restructure(ctx)
    mc = root/"assets/minecraft"
    assert (mc/"textures/block").is_dir()
    assert (mc/"textures/item/apple.png").exists()
    assert (mc/"optifine/sky/world0/sky1.properties").exists()
    assert not (mc/"mcpatcher").exists()
```

- [ ] **Step 2: Run test, verify fail**

Run: `pytest tests/test_restructure.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement restructure.py**

```python
# mc_pack_converter/stages/restructure.py
from __future__ import annotations
from ..pipeline import ConversionContext, Severity

_RENAMES = [
    ("textures/blocks", "textures/block"),
    ("textures/items", "textures/item"),
    ("mcpatcher", "optifine"),
]

def restructure(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    for old_rel, new_rel in _RENAMES:
        old, new = mc / old_rel, mc / new_rel
        if old.is_dir() and not new.exists():
            old.rename(new)
            ctx.add("restructure", Severity.INFO, f"{old_rel} -> {new_rel}")
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_restructure.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mc_pack_converter/stages/restructure.py tests/test_restructure.py
git commit -m "feat: restructure stage renames blocks/items/mcpatcher dirs"
```

---

## Task 7: Flatten-rename stage + flattening.json

**Files:**
- Create: `mc_pack_converter/data/flattening.json`, `mc_pack_converter/stages/flatten_rename.py`
- Test: `tests/test_flatten_rename.py`

**Interfaces:**
- Produces:
  - `def load_table(name: str) -> dict` — loads `mc_pack_converter/data/<name>.json` (shared helper; place in `mc_pack_converter/data/__init__.py`).
  - `def flatten_rename(ctx: ConversionContext) -> None` — for each `{old_rel: new_rel}` in `flattening.json`, if `assets/minecraft/<old_rel>` exists, move it (and a sibling `<old>.mcmeta` if present) to `<new_rel>`. Records INFO per move; if both old and new exist, WARNING and skip.

**Data-table task — build `flattening.json` against a reference, do NOT invent entries:**
`flattening.json` maps 1.8.9 asset-relative paths to 26.2 paths. Seed it with the entries this repo is certain of, then expand from the reference source below during this task. Schema: flat JSON object, keys/values are POSIX paths relative to `assets/minecraft/`.

Confident seed entries (verified against the M8SON pack + well-known Flattening):
```json
{
  "textures/block/fire_layer_0.png": "textures/block/fire_0.png",
  "textures/block/fire_layer_1.png": "textures/block/fire_1.png"
}
```
Reference to expand from during implementation: the Minecraft Wiki "Java Edition 1.13/Flattening" texture-rename tables and the official texture template pages. Every added entry must be a real 1.8.9→modern rename. Note ordering: this stage runs AFTER restructure, so keys already use `block/` and `item/` (singular).

- [ ] **Step 1: Write failing test**

```python
# tests/test_flatten_rename.py
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.flatten_rename import flatten_rename

def test_fire_is_renamed(mini_pack):
    root = mini_pack({
        "assets/minecraft/textures/block/fire_layer_0.png": b"x",
        "assets/minecraft/textures/block/fire_layer_0.png.mcmeta": b"{}",
    })
    ctx = ConversionContext(root=root)
    flatten_rename(ctx)
    b = root/"assets/minecraft/textures/block"
    assert (b/"fire_0.png").exists()
    assert (b/"fire_0.png.mcmeta").exists()
    assert not (b/"fire_layer_0.png").exists()
```

- [ ] **Step 2: Run test, verify fail**

Run: `pytest tests/test_flatten_rename.py -v`
Expected: FAIL (ImportError / file missing).

- [ ] **Step 3: Create data loader + flattening.json + stage**

```python
# mc_pack_converter/data/__init__.py
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

@lru_cache
def load_table(name: str) -> dict:
    p = Path(__file__).parent / f"{name}.json"
    return json.loads(p.read_text())
```

```json
// mc_pack_converter/data/flattening.json
{
  "textures/block/fire_layer_0.png": "textures/block/fire_0.png",
  "textures/block/fire_layer_1.png": "textures/block/fire_1.png"
}
```

```python
# mc_pack_converter/stages/flatten_rename.py
from __future__ import annotations
from ..pipeline import ConversionContext, Severity
from ..data import load_table

def _move(src, dst, ctx):
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    # move sibling .mcmeta if present
    m = src.with_name(src.name + ".mcmeta")
    if m.exists():
        m.rename(dst.with_name(dst.name + ".mcmeta"))
    ctx.add("flatten_rename", Severity.INFO, f"{src.name} -> {dst.name}")

def flatten_rename(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    for old_rel, new_rel in load_table("flattening").items():
        old, new = mc / old_rel, mc / new_rel
        if not old.exists():
            continue
        if new.exists():
            ctx.add("flatten_rename", Severity.WARNING,
                    f"target exists, skipping {old_rel}", str(old_rel))
            continue
        _move(old, new, ctx)
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_flatten_rename.py -v`
Expected: PASS.

- [ ] **Step 5: Expand flattening.json from the reference**

Add verified 1.8.9→26.2 renames from the Minecraft Wiki Flattening tables. After each batch, run `python -c "from mc_pack_converter.data import load_table; load_table.cache_clear(); print(len(load_table('flattening')))"` and re-run the test to confirm no regressions. Do not add speculative entries.

- [ ] **Step 6: Commit**

```bash
git add mc_pack_converter/data/ mc_pack_converter/stages/flatten_rename.py tests/test_flatten_rename.py
git commit -m "feat: flatten-rename stage + flattening data table (fire seed)"
```

---

## Task 8: Atlas-remap stage + region_remap.json

**Files:**
- Create: `mc_pack_converter/data/region_remap.json`, `mc_pack_converter/stages/atlas_remap.py`
- Test: `tests/test_atlas_remap.py`

**Interfaces:**
- Produces: `def atlas_remap(ctx: ConversionContext) -> None` — for each entry in `region_remap.json` (`{asset_rel: {"out_size":[w,h], "regions":[{"src":[..],"dst":[..]}]}}`), if the asset exists, call `imaging.crop_paste` in place (write to a temp then replace). INFO per remap; skip + INFO if asset absent.

**Data-table task — `region_remap.json`:** maps entity/model textures whose internal layout changed (chest is the known case). Coordinates come from comparing the 1.8.9 vs 26.2 texture *templates* (Minecraft Wiki "Model"/entity template pages). Seed with the chest single-chest entry once its exact rects are confirmed against the wiki; until confirmed, ship the file with an empty object `{}` and the stage is a no-op (the golden test in Task 15 will surface the chest and drive filling this in with a visual spot-check). Do not guess coordinates.

Seed content:
```json
{}
```

- [ ] **Step 1: Write failing test (synthetic remap, not real chest coords)**

```python
# tests/test_atlas_remap.py
from PIL import Image
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.atlas_remap import atlas_remap
from mc_pack_converter.imaging import png_size
import mc_pack_converter.stages.atlas_remap as mod

def test_atlas_remap_applies_table(mini_pack, monkeypatch):
    root = mini_pack({"assets/minecraft/textures/entity/chest/normal.png": b""})
    Image.new("RGBA",(64,64),(0,255,0,255)).save(
        root/"assets/minecraft/textures/entity/chest/normal.png")
    fake = {"textures/entity/chest/normal.png":
            {"out_size":[64,64],"regions":[{"src":[0,0,32,32],"dst":[0,0,32,32]}]}}
    monkeypatch.setattr(mod, "load_table", lambda name: fake)
    ctx = ConversionContext(root=root)
    atlas_remap(ctx)
    assert png_size(root/"assets/minecraft/textures/entity/chest/normal.png") == (64,64)
```

- [ ] **Step 2: Run test, verify fail**

Run: `pytest tests/test_atlas_remap.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement region_remap.json + atlas_remap.py**

```python
# mc_pack_converter/stages/atlas_remap.py
from __future__ import annotations
from ..pipeline import ConversionContext, Severity
from ..data import load_table
from ..imaging import crop_paste

def atlas_remap(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    for rel, spec in load_table("region_remap").items():
        asset = mc / rel
        if not asset.exists():
            continue
        tmp = asset.with_suffix(".remap.png")
        crop_paste(asset, tmp, spec["regions"], tuple(spec["out_size"]))
        tmp.replace(asset)
        ctx.add("atlas_remap", Severity.INFO, f"remapped {rel}", rel)
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_atlas_remap.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mc_pack_converter/data/region_remap.json mc_pack_converter/stages/atlas_remap.py tests/test_atlas_remap.py
git commit -m "feat: atlas-remap stage for reorganized entity textures"
```

---

## Task 9: OptiFine translate stage (sky refs, ctm, passthrough) + ctm_blocks.json

**Files:**
- Create: `mc_pack_converter/data/ctm_blocks.json`, `mc_pack_converter/stages/optifine.py`
- Test: `tests/test_optifine.py`

**Interfaces:**
- Produces:
  - `def optifine_translate(ctx: ConversionContext) -> None` — runs three sub-steps under `assets/minecraft/optifine/`:
    1. **sky**: for each `sky/world0/*.properties`, parse `key=value` lines; for `source=` values, resolve the referenced file relative to the properties file; if missing, add WARNING (dangling source ref). Rewrite nothing structurally (format unchanged); this sub-step only validates + reports.
    2. **ctm**: for each `ctm/**/*.properties` with `method=ctm`/`method=overlay` etc. that lacks a `matchBlocks=`/`matchTiles=` line, look up the containing folder name in `ctm_blocks.json` and append the resolved `matchBlocks=` line. INFO per file updated; WARNING if folder not in table.
  - Helper: `def parse_properties(text: str) -> dict[str,str]`.

**Data-table task — `ctm_blocks.json`:** maps legacy CTM folder names (e.g. `glass`, `glass_stained/glass_black`) to modern block IDs for `matchBlocks=` (e.g. `minecraft:glass`, `minecraft:black_stained_glass`). Build from the M8SON `ctm/` folder listing (19 configs) cross-referenced with modern block IDs. Seed with the confident glass mappings; expand for the stained-glass colors.

Seed content:
```json
{
  "glass": "minecraft:glass",
  "glass_pane": "minecraft:glass_pane"
}
```

- [ ] **Step 1: Write failing test**

```python
# tests/test_optifine.py
from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages.optifine import optifine_translate, parse_properties

def test_parse_properties():
    assert parse_properties("a=1\n# c\nb=2\n") == {"a":"1","b":"2"}

def test_sky_dangling_source_warns(mini_pack):
    root = mini_pack({
        "assets/minecraft/optifine/sky/world0/sky4.properties":
            b"source=./starfield01.png\nblend=add\n",
    })
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    assert any(f.severity is Severity.WARNING and "starfield01" in f.message
               for f in ctx.findings)

def test_ctm_matchblocks_appended(mini_pack):
    root = mini_pack({
        "assets/minecraft/optifine/ctm/glass/glass.properties":
            b"method=ctm\ntiles=0-46\n",
    })
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    txt = (root/"assets/minecraft/optifine/ctm/glass/glass.properties").read_text()
    assert "matchBlocks=minecraft:glass" in txt
```

- [ ] **Step 2: Run test, verify fail**

Run: `pytest tests/test_optifine.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement ctm_blocks.json + optifine.py**

```python
# mc_pack_converter/stages/optifine.py
from __future__ import annotations
from pathlib import Path
from ..pipeline import ConversionContext, Severity
from ..data import load_table

def parse_properties(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out

def _check_sky(ctx: ConversionContext, sky_dir: Path) -> None:
    for prop in sky_dir.rglob("*.properties"):
        props = parse_properties(prop.read_text())
        src = props.get("source")
        if not src:
            continue
        target = (prop.parent / src).resolve()
        if not target.exists():
            ctx.add("optifine", Severity.WARNING,
                    f"sky source missing: {src}", str(prop))

def _fix_ctm(ctx: ConversionContext, ctm_dir: Path) -> None:
    table = load_table("ctm_blocks")
    for prop in ctm_dir.rglob("*.properties"):
        text = prop.read_text()
        props = parse_properties(text)
        if "matchBlocks" in props or "matchTiles" in props:
            continue
        folder = prop.parent.relative_to(ctm_dir).as_posix()
        block = table.get(folder) or table.get(prop.parent.name)
        if not block:
            ctx.add("optifine", Severity.WARNING,
                    f"no matchBlocks mapping for ctm folder '{folder}'", str(prop))
            continue
        prop.write_text(text.rstrip() + f"\nmatchBlocks={block}\n")
        ctx.add("optifine", Severity.INFO, f"ctm matchBlocks={block}", str(prop))

def optifine_translate(ctx: ConversionContext) -> None:
    of = ctx.root / "assets" / "minecraft" / "optifine"
    if not of.is_dir():
        return
    sky = of / "sky"
    if sky.is_dir():
        _check_sky(ctx, sky)
    ctm = of / "ctm"
    if ctm.is_dir():
        _fix_ctm(ctx, ctm)
```

```json
// mc_pack_converter/data/ctm_blocks.json
{
  "glass": "minecraft:glass",
  "glass_pane": "minecraft:glass_pane"
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_optifine.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Expand ctm_blocks.json** for the 17 stained-glass color folders (`glass_stained/glass_black` → `minecraft:black_stained_glass`, etc.), verifying each modern block ID. Re-run tests.

- [ ] **Step 6: Commit**

```bash
git add mc_pack_converter/data/ctm_blocks.json mc_pack_converter/stages/optifine.py tests/test_optifine.py
git commit -m "feat: optifine stage (sky ref validation, ctm matchBlocks)"
```

---

## Task 10: GUI sprite-slice stage + gui_sprites.json

**Files:**
- Create: `mc_pack_converter/data/gui_sprites.json`, `mc_pack_converter/stages/gui_sprites.py`
- Test: `tests/test_gui_sprites.py`

**Interfaces:**
- Produces: `def gui_sprites(ctx: ConversionContext) -> None` — for each sheet entry in `gui_sprites.json` (`{sheet_rel: {"dir": out_dir_rel, "sprites":[{name,x,y,w,h}], "ninepatch": {name:[l,t,r,b]}}}`), if the sheet exists, call `imaging.slice_sheet`, then for any sprite listed under `ninepatch`, write a `<name>.png.mcmeta` with the 9-slice border. INFO per sheet sliced.

**Data-table task — `gui_sprites.json`:** the modern 26.2 `gui/sprites/` layout and the source coordinates within 1.8.9 `widgets.png`/`icons.png`. Build from the 26.2 vanilla assets (the real sprite names + sizes) and the known 1.8.9 sheet coordinates. Seed with the hotbar sprite (widely documented: `widgets.png` hotbar is 182x22 at 0,0). Expand to the full HUD sprite set during this task, verifying names against 26.2 vanilla `assets/minecraft/textures/gui/sprites/`.

Seed content:
```json
{
  "textures/gui/widgets.png": {
    "dir": "textures/gui/sprites/hud",
    "sprites": [{"name": "hotbar", "x": 0, "y": 0, "w": 182, "h": 22}],
    "ninepatch": {}
  }
}
```

- [ ] **Step 1: Write failing test**

```python
# tests/test_gui_sprites.py
from PIL import Image
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.gui_sprites import gui_sprites

def test_widgets_sliced_to_sprites(mini_pack):
    root = mini_pack()
    sheet = root/"assets/minecraft/textures/gui/widgets.png"
    sheet.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA",(256,256),(0,0,255,255)).save(sheet)
    ctx = ConversionContext(root=root)
    gui_sprites(ctx)
    out = root/"assets/minecraft/textures/gui/sprites/hud/hotbar.png"
    assert out.exists()
```

- [ ] **Step 2: Run test, verify fail**

Run: `pytest tests/test_gui_sprites.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement gui_sprites.json + gui_sprites.py**

```python
# mc_pack_converter/stages/gui_sprites.py
from __future__ import annotations
import json
from ..pipeline import ConversionContext, Severity
from ..data import load_table
from ..imaging import slice_sheet

def gui_sprites(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    for sheet_rel, spec in load_table("gui_sprites").items():
        sheet = mc / sheet_rel
        if not sheet.exists():
            continue
        out_dir = mc / spec["dir"]
        slice_sheet(sheet, out_dir, spec["sprites"])
        for name, border in spec.get("ninepatch", {}).items():
            meta = out_dir / f"{name}.png.mcmeta"
            l, t, r, b = border
            meta.write_text(json.dumps({
                "gui": {"scaling": {"type": "nine_slice",
                        "width": 0, "height": 0,
                        "border": {"left": l, "top": t, "right": r, "bottom": b}}}
            }, indent=2))
        ctx.add("gui_sprites", Severity.INFO,
                f"sliced {sheet_rel} -> {len(spec['sprites'])} sprites")
```

```json
// mc_pack_converter/data/gui_sprites.json
{
  "textures/gui/widgets.png": {
    "dir": "textures/gui/sprites/hud",
    "sprites": [{"name": "hotbar", "x": 0, "y": 0, "w": 182, "h": 22}],
    "ninepatch": {}
  }
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_gui_sprites.py -v`
Expected: PASS.

- [ ] **Step 5: Expand gui_sprites.json** — add the full 26.2 HUD/container sprite set (hotbar selection, health/food/armor icons from `icons.png`, etc.), with `ninepatch` borders where 26.2 uses `nine_slice` scaling (fill `width`/`height` from the real sprite size). Verify names against 26.2 vanilla assets. Re-run tests.

- [ ] **Step 6: Commit**

```bash
git add mc_pack_converter/data/gui_sprites.json mc_pack_converter/stages/gui_sprites.py tests/test_gui_sprites.py
git commit -m "feat: gui-sprite-slice stage + sprite map (hotbar seed)"
```

---

## Task 11: Sounds stage + sound_map.json

**Files:**
- Create: `mc_pack_converter/data/sound_map.json`, `mc_pack_converter/stages/sounds.py`
- Test: `tests/test_sounds.py`

**Interfaces:**
- Produces: `def sounds(ctx: ConversionContext) -> None` — for each `{old_rel: new_rel}` in `sound_map.json` (paths relative to `assets/minecraft/sounds/`), move the `.ogg` if present. INFO per move. This preserves the "old OGGs" the user likes at paths modern MC reads.

**Data-table task — `sound_map.json`:** 1.8.9 sound file paths → 26.2 sound file paths. Since itsme's converter already gets the OGGs working, cross-check parity against a pack itsme converted (the user has one) plus the 26.2 vanilla `sounds.json` event→file paths. Seed with a confident, verifiable subset; expand to full parity. If a source path has no known modern target, leave it in place and add an INFO (not an error) — silent vanilla fallback is acceptable.

Seed content:
```json
{}
```

- [ ] **Step 1: Write failing test**

```python
# tests/test_sounds.py
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.sounds import sounds
import mc_pack_converter.stages.sounds as mod

def test_sound_moved(mini_pack, monkeypatch):
    root = mini_pack({"assets/minecraft/sounds/random/click.ogg": b"OggS"})
    monkeypatch.setattr(mod, "load_table",
                        lambda n: {"random/click.ogg": "ui/button/click.ogg"})
    ctx = ConversionContext(root=root)
    sounds(ctx)
    s = root/"assets/minecraft/sounds"
    assert (s/"ui/button/click.ogg").exists()
    assert not (s/"random/click.ogg").exists()
```

- [ ] **Step 2: Run test, verify fail**

Run: `pytest tests/test_sounds.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement sound_map.json + sounds.py**

```python
# mc_pack_converter/stages/sounds.py
from __future__ import annotations
from ..pipeline import ConversionContext, Severity
from ..data import load_table

def sounds(ctx: ConversionContext) -> None:
    base = ctx.root / "assets" / "minecraft" / "sounds"
    if not base.is_dir():
        return
    for old_rel, new_rel in load_table("sound_map").items():
        old, new = base / old_rel, base / new_rel
        if not old.exists() or new.exists():
            continue
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
        ctx.add("sounds", Severity.INFO, f"{old_rel} -> {new_rel}")
```

```json
// mc_pack_converter/data/sound_map.json
{}
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_sounds.py -v`
Expected: PASS.

- [ ] **Step 5: Build sound_map.json to itsme-parity** from the 26.2 vanilla `sounds.json` and the user's itsme-converted pack. Re-run tests after each batch.

- [ ] **Step 6: Commit**

```bash
git add mc_pack_converter/data/sound_map.json mc_pack_converter/stages/sounds.py tests/test_sounds.py
git commit -m "feat: sounds stage remaps 1.8.9 sound paths"
```

---

## Task 12: pack.mcmeta bump + pack_format.json

**Files:**
- Create: `mc_pack_converter/data/pack_format.json`, `mc_pack_converter/stages/pack_meta.py`
- Test: `tests/test_pack_meta.py`

**Interfaces:**
- Produces: `def pack_meta(ctx: ConversionContext) -> None` — rewrite `pack.mcmeta`: set `pack.pack_format` to `pack_format.json[ctx.target]`, preserve `description`. INFO with old→new format.

**Data-table task — `pack_format.json`:** version→pack_format. The 26.2 number MUST be verified against the official Minecraft Wiki "pack_format" list before shipping — do not guess. Seed with the known 1.8.9 value and a clearly-marked placeholder for 26.2 that the test pins once verified.

Seed content (verify 26.2 value before Step 5):
```json
{
  "1.8.9": 1,
  "26.2": 0
}
```

- [ ] **Step 1: Write failing test**

```python
# tests/test_pack_meta.py
import json
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.pack_meta import pack_meta
import mc_pack_converter.stages.pack_meta as mod

def test_pack_format_bumped(mini_pack, monkeypatch):
    root = mini_pack()
    monkeypatch.setattr(mod, "load_table", lambda n: {"26.2": 99})
    ctx = ConversionContext(root=root, target="26.2")
    pack_meta(ctx)
    data = json.loads((root/"pack.mcmeta").read_text())
    assert data["pack"]["pack_format"] == 99
    assert data["pack"]["description"] == "test"
```

- [ ] **Step 2: Run test, verify fail**

Run: `pytest tests/test_pack_meta.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement pack_format.json + pack_meta.py**

```python
# mc_pack_converter/stages/pack_meta.py
from __future__ import annotations
import json
from ..pipeline import ConversionContext, Severity, FatalConversionError
from ..data import load_table

def pack_meta(ctx: ConversionContext) -> None:
    meta = ctx.root / "pack.mcmeta"
    data = json.loads(meta.read_text())
    new_fmt = load_table("pack_format").get(ctx.target)
    if not new_fmt:
        raise FatalConversionError(f"no pack_format for target {ctx.target}")
    old_fmt = data["pack"].get("pack_format")
    data["pack"]["pack_format"] = new_fmt
    meta.write_text(json.dumps(data, indent=2))
    ctx.add("pack_meta", Severity.INFO, f"pack_format {old_fmt} -> {new_fmt}")
```

```json
// mc_pack_converter/data/pack_format.json
{"1.8.9": 1, "26.2": 0}
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_pack_meta.py -v`
Expected: PASS.

- [ ] **Step 5: Verify + set the real 26.2 pack_format** from the official pack_format reference; replace the `0` placeholder. Add a test asserting `load_table("pack_format")["26.2"] > 1`.

- [ ] **Step 6: Commit**

```bash
git add mc_pack_converter/data/pack_format.json mc_pack_converter/stages/pack_meta.py tests/test_pack_meta.py
git commit -m "feat: pack.mcmeta format bump"
```

---

## Task 13: Validate stage (null-texture safety)

**Files:**
- Create: `mc_pack_converter/stages/validate.py`
- Test: `tests/test_validate.py`

**Interfaces:**
- Produces: `def validate(ctx: ConversionContext) -> None` — scans the converted tree and adds WARNING/ERROR findings (stage `"validate"`) for:
  1. Any `*.png.mcmeta` with an `animation` whose implied frame height doesn't divide the PNG height evenly, or references a frame index out of range → WARNING.
  2. Corrupt / zero-byte `.png` (via `imaging.is_valid_png`) → ERROR.
  3. OptiFine `.properties` `source=`/`tiles=` referencing missing files → WARNING. (Re-uses `parse_properties`.)
  4. Any sprite referenced in `gui_sprites.json` whose output file is missing → WARNING.

- [ ] **Step 1: Write failing test**

```python
# tests/test_validate.py
from PIL import Image
from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages.validate import validate

def test_zero_byte_png_flagged(mini_pack):
    root = mini_pack({"assets/minecraft/textures/block/stone.png": b""})
    ctx = ConversionContext(root=root)
    validate(ctx)
    assert any(f.stage=="validate" and f.severity is Severity.ERROR
               for f in ctx.findings)

def test_bad_mcmeta_dims_flagged(mini_pack):
    root = mini_pack()
    b = root/"assets/minecraft/textures/block"
    Image.new("RGBA",(16,20)).save(b/"fire_0.png")  # 20 not divisible by 16
    (b/"fire_0.png.mcmeta").write_text('{"animation":{}}')
    ctx = ConversionContext(root=root)
    validate(ctx)
    assert any(f.stage=="validate" and f.severity is Severity.WARNING
               for f in ctx.findings)
```

- [ ] **Step 2: Run test, verify fail**

Run: `pytest tests/test_validate.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement validate.py**

```python
# mc_pack_converter/stages/validate.py
from __future__ import annotations
import json
from ..pipeline import ConversionContext, Severity
from ..imaging import is_valid_png, png_size
from .optifine import parse_properties

def _check_pngs(ctx, mc):
    for png in mc.rglob("*.png"):
        if not is_valid_png(png):
            ctx.add("validate", Severity.ERROR, "corrupt or empty png",
                    str(png.relative_to(mc)))

def _check_mcmeta(ctx, mc):
    for meta in mc.rglob("*.png.mcmeta"):
        try:
            data = json.loads(meta.read_text())
        except Exception:
            ctx.add("validate", Severity.WARNING, "unparseable mcmeta",
                    str(meta.relative_to(mc)))
            continue
        if "animation" not in data:
            continue
        png = meta.with_suffix("")  # drop .mcmeta -> foo.png
        if not png.exists():
            continue
        w, h = png_size(png)
        # square-frame assumption: frame height == width; height must be a multiple
        if w and h % w != 0:
            ctx.add("validate", Severity.WARNING,
                    f"animation frame height mismatch ({w}x{h})",
                    str(png.relative_to(mc)))

def _check_optifine(ctx, mc):
    of = mc / "optifine"
    if not of.is_dir():
        return
    for prop in of.rglob("*.properties"):
        props = parse_properties(prop.read_text())
        src = props.get("source")
        if src and not (prop.parent / src).resolve().exists():
            ctx.add("validate", Severity.WARNING, f"missing source {src}",
                    str(prop.relative_to(mc)))

def validate(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    if not mc.is_dir():
        return
    _check_pngs(ctx, mc)
    _check_mcmeta(ctx, mc)
    _check_optifine(ctx, mc)
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_validate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mc_pack_converter/stages/validate.py tests/test_validate.py
git commit -m "feat: validate stage (null-texture safety checks)"
```

---

## Task 14: Package stage

**Files:**
- Create: `mc_pack_converter/stages/package.py`
- Test: `tests/test_package.py`

**Interfaces:**
- Produces: `def write_output(ctx, out_path: Path, reports: dict[str,str]) -> None` — writes each report string into `ctx.root` (e.g. `conversion-report.md`), then zips `ctx.root` contents to `out_path` (if `out_path` ends `.zip`) or copytrees to a folder. Raises `FatalConversionError` if `out_path` parent is unwritable.

- [ ] **Step 1: Write failing test**

```python
# tests/test_package.py
import zipfile
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.package import write_output

def test_write_zip(mini_pack, tmp_path):
    root = mini_pack()
    ctx = ConversionContext(root=root)
    out = tmp_path/"converted.zip"
    write_output(ctx, out, {"conversion-report.md": "# hi"})
    assert out.exists()
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert any(n.endswith("pack.mcmeta") for n in names)
    assert any(n.endswith("conversion-report.md") for n in names)
```

- [ ] **Step 2: Run test, verify fail**

Run: `pytest tests/test_package.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement package.py**

```python
# mc_pack_converter/stages/package.py
from __future__ import annotations
import shutil, zipfile
from pathlib import Path
from ..pipeline import ConversionContext, FatalConversionError

def write_output(ctx: ConversionContext, out_path: Path,
                 reports: dict[str, str]) -> None:
    for name, text in reports.items():
        (ctx.root / name).write_text(text)
    parent = out_path.parent
    if not parent.exists() or not parent.is_dir():
        raise FatalConversionError(f"output dir not writable: {parent}")
    if out_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in ctx.root.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(ctx.root))
    else:
        shutil.copytree(ctx.root, out_path, dirs_exist_ok=True)
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_package.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mc_pack_converter/stages/package.py tests/test_package.py
git commit -m "feat: package stage writes reports + zip/folder output"
```

---

## Task 15: CLI wiring + golden end-to-end test

**Files:**
- Create: `mc_pack_converter/cli.py`
- Modify: `mc_pack_converter/stages/__init__.py` (populate STAGES)
- Test: `tests/test_cli_e2e.py`

**Interfaces:**
- Consumes: every stage above + `prepare_working_copy`, `render_conversion_report`, `render_null_texture_report`, `write_output`.
- Produces:
  - `STAGES` = ordered list: ingest, clean, restructure, flatten_rename, atlas_remap, optifine_translate, gui_sprites, sounds, pack_meta, validate.
  - `def convert(source: Path, out_path: Path, target: str, report_only: bool) -> ConversionContext`.
  - `def main(argv=None) -> int` — argparse: `convert <source> [-o OUT] [--target 26.2] [--report-only]`.

- [ ] **Step 1: Populate STAGES**

```python
# mc_pack_converter/stages/__init__.py
from .ingest import ingest
from .clean import clean
from .restructure import restructure
from .flatten_rename import flatten_rename
from .atlas_remap import atlas_remap
from .optifine import optifine_translate
from .gui_sprites import gui_sprites
from .sounds import sounds
from .pack_meta import pack_meta
from .validate import validate

STAGES = [
    ("ingest", ingest), ("clean", clean), ("restructure", restructure),
    ("flatten_rename", flatten_rename), ("atlas_remap", atlas_remap),
    ("optifine", optifine_translate), ("gui_sprites", gui_sprites),
    ("sounds", sounds), ("pack_meta", pack_meta), ("validate", validate),
]
```

- [ ] **Step 2: Write failing golden e2e test**

```python
# tests/test_cli_e2e.py
from pathlib import Path
import pytest
from mc_pack_converter.cli import convert

PACK = Path("/home/daedalus/linux/M8SON 1.8 PVP PACK")

@pytest.mark.skipif(not PACK.exists(), reason="golden pack absent")
def test_golden_conversion(tmp_path):
    out = tmp_path/"converted.zip"
    ctx = convert(PACK, out, target="26.2", report_only=False)
    assert out.exists()
    # structural expectations
    from mc_pack_converter.pipeline import Severity
    errors = [f for f in ctx.findings if f.severity is Severity.ERROR]
    assert errors == [], f"unexpected errors: {errors}"
```

- [ ] **Step 3: Run test, verify fail**

Run: `pytest tests/test_cli_e2e.py -v`
Expected: FAIL (ImportError: convert).

- [ ] **Step 4: Implement cli.py**

```python
# mc_pack_converter/cli.py
from __future__ import annotations
import argparse, tempfile
from pathlib import Path
from .pipeline import ConversionContext, run_pipeline
from .stages import STAGES
from .stages.ingest import prepare_working_copy
from .stages.package import write_output
from .report import render_conversion_report, render_null_texture_report

def convert(source: Path, out_path: Path, target: str,
            report_only: bool) -> ConversionContext:
    workroot = Path(tempfile.mkdtemp(prefix="mcpc_"))
    root = prepare_working_copy(source, workroot)
    ctx = ConversionContext(root=root, target=target)
    stages = STAGES if not report_only else [
        s for s in STAGES if s[0] in ("ingest", "clean", "restructure",
        "flatten_rename", "atlas_remap", "optifine", "validate")]
    run_pipeline(ctx, stages)
    reports = {
        "conversion-report.md": render_conversion_report(ctx.findings),
        "null-texture-report.md": render_null_texture_report(ctx.findings),
    }
    if not report_only:
        write_output(ctx, out_path, reports)
    return ctx

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mc-pack-converter")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert")
    c.add_argument("source", type=Path)
    c.add_argument("-o", "--out", type=Path, default=Path("converted.zip"))
    c.add_argument("--target", default="26.2")
    c.add_argument("--report-only", action="store_true")
    args = ap.parse_args(argv)
    ctx = convert(args.source, args.out, args.target, args.report_only)
    print(render_conversion_report(ctx.findings))
    print(render_null_texture_report(ctx.findings))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run golden test, verify pass**

Run: `pytest tests/test_cli_e2e.py -v`
Expected: PASS (or SKIP if pack absent). Then run the full suite: `pytest -v`. Expected: all pass.

- [ ] **Step 6: Manual in-game spot-check (documented, not automated)**

Convert the real pack, load it in Minecraft 26.2 + OptiFine (or Fabric+Skyboxify), and visually confirm: fire animates, crafting/HUD GUI renders, chest is correctly mapped, custom sky appears. Record any texture still wrong → drives new `region_remap.json` / `gui_sprites.json` / `flattening.json` entries (each with its own test). This is the loop that populates the data tables to full coverage.

- [ ] **Step 7: Commit**

```bash
git add mc_pack_converter/cli.py mc_pack_converter/stages/__init__.py tests/test_cli_e2e.py
git commit -m "feat: CLI wiring + golden end-to-end conversion test"
```

---

## Self-Review Notes

- **Spec coverage:** every pipeline stage (ingest→package), both reports, all six data tables, error handling (fail-soft + FatalConversionError), idempotency warning (Task 4), and TDD tests are represented. `--report-only` implemented in Task 15.
- **Data honesty:** flattening/ctm/gui/sound/pack_format tables ship with confident seeds + explicit "expand from verified reference" steps and tests — never fabricated bulk entries. The golden test + manual spot-check (Task 15) is the loop that drives them to full coverage.
- **Type consistency:** `ConversionContext.add`, `Finding`, `Severity`, `load_table`, `parse_properties`, `crop_paste`, `slice_sheet` names are used identically across tasks.
