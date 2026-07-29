# 1.14 Slicer Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover the pack's custom particle, painting and explosion art by porting Mojang's vendored 1.14 slicer, and stop the slice stage from writing fully-transparent PNGs that override vanilla.

**Architecture:** Teach `tools/gen_slices.py` to evaluate the five helper functions in `tools/slicer_src/slicer_1.14.java`, emitting ordinary proportional `crop` records into `data/slices.json`. Particle boxes are restated against a `128,128` reference so proportional scaling yields `cell = width/16`. The `slice` stage gains one rule — skip a crop with no visible pixels — which both fixes 23 pre-existing invisible sprites and handles particle cells absent from a 1.8.9 atlas. A new `contact_sheet.py` renders the produced sprites into one reviewable PNG beside the output archive.

**Tech Stack:** Python 3, Pillow, pytest. Venv at `.venv` — always invoke as `.venv/bin/python`.

**Spec:** `docs/superpowers/specs/2026-07-29-particles-slicer-design.md` — read it before starting. It carries the measurements behind every number here.

## Global Constraints

- **Fix and format — never create art.** Every output is a sub-rectangle of pixels the pack already ships. No drawing, no invention, no upscaling of pack art.
- **Boxes are proportional**, always `[x, y, w, h, totalW, totalH]`, so the pipeline works at any pack resolution. Never emit absolute pixel coordinates.
- **`slices.json` is generated, never hand-edited.** It is a pure derivative of `tools/slicer_src/*.java` via `tools/gen_slices.py`.
- **Fail-soft per sprite.** A single bad record logs a finding and continues; it never aborts the conversion.
- Falling back to vanilla is a correct outcome, not a failure. The purple/black missing-texture placeholder is the only true failure.
- Run everything through the venv: `.venv/bin/python -m pytest`, `.venv/bin/python tools/gen_slices.py`.
- Working tree is clean at `master` @ `56f03ec` with 58 tests passing. Commit after every task.

---

### Task 1: Skip empty crops in the slice stage

Fixes the 23 invisible sprites documented in `docs/known-issues.md` §1. Independent of the generator work — land it first so the fix is bisectable on its own.

**Files:**
- Modify: `mc_pack_converter/stages/slice.py`
- Test: `tests/test_slice.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `_is_empty(im: Image.Image) -> bool` in `mc_pack_converter/stages/slice.py`. No other task calls it directly.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_slice.py`:

```python
def test_transparent_region_is_left_to_vanilla(mini_pack, monkeypatch):
    # A 1.8.9 atlas has no pixels where a modern sprite lives. Writing a
    # transparent PNG would OVERRIDE vanilla and render it invisible in-game,
    # so no file may be written at all.
    root = mini_pack()
    _put(root, "assets/minecraft/textures/gui/widgets.png", (256, 256), (0, 0, 0, 0))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/widgets.png",
         "output": "assets/minecraft/textures/gui/sprites/hud/hotbar.png",
         "box": [0, 0, 182, 22, 256, 256], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert not (root / "assets/minecraft/textures/gui/sprites/hud/hotbar.png").exists()
    assert any("left to vanilla" in f.message for f in ctx.findings)


def test_zero_size_crop_is_left_to_vanilla(mini_pack, monkeypatch):
    # A box that scales down to zero pixels must not produce a file.
    root = mini_pack()
    _put(root, "assets/minecraft/textures/gui/widgets.png", (16, 16))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/widgets.png",
         "output": "assets/minecraft/textures/gui/sprites/hud/tiny.png",
         "box": [0, 0, 1, 1, 512, 512], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert not (root / "assets/minecraft/textures/gui/sprites/hud/tiny.png").exists()


def test_clip_with_empty_region_is_left_to_vanilla(mini_pack, monkeypatch):
    root = mini_pack()
    _put(root, "assets/minecraft/textures/gui/widgets.png", (256, 256), (0, 0, 0, 0))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/widgets.png",
         "output": "assets/minecraft/textures/gui/sprites/hud/clipped.png",
         "box": [0, 0, 32, 32, 256, 256], "op": "clip"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert not (root / "assets/minecraft/textures/gui/sprites/hud/clipped.png").exists()


def test_opaque_region_still_written(mini_pack, monkeypatch):
    # Guard: the skip rule must not suppress real art.
    root = mini_pack()
    _put(root, "assets/minecraft/textures/gui/widgets.png", (256, 256), (10, 20, 30, 255))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/widgets.png",
         "output": "assets/minecraft/textures/gui/sprites/hud/hotbar.png",
         "box": [0, 0, 182, 22, 256, 256], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert (root / "assets/minecraft/textures/gui/sprites/hud/hotbar.png").exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_slice.py -v`

Expected: `test_transparent_region_is_left_to_vanilla`, `test_zero_size_crop_is_left_to_vanilla` and `test_clip_with_empty_region_is_left_to_vanilla` FAIL — the files get written because nothing checks emptiness. `test_opaque_region_still_written` passes already.

- [ ] **Step 3: Add the `_is_empty` helper**

In `mc_pack_converter/stages/slice.py`, add after `_scaled_rect`:

```python
def _is_empty(im: Image.Image) -> bool:
    """True if the region has no visible pixels.

    A 1.8.9 atlas has nothing where sprites added in later versions live.
    Writing that empty region out would OVERRIDE vanilla's sprite rather than
    fall back to it, making the element invisible in-game.
    """
    if im.width == 0 or im.height == 0:
        return True
    return im.getchannel("A").getbbox() is None
```

Checking the alpha channel's bbox specifically — not `im.getbbox()` — so a transparent region carrying nonzero RGB still counts as empty.

- [ ] **Step 4: Apply the rule in `slice_atlases`**

In `slice_atlases`, change the counter setup from:

```python
    made = 0
    skipped_special = 0
```

to:

```python
    made = 0
    skipped_special = 0
    left_to_vanilla = 0
```

Then in the non-`copy` branch, insert the check immediately after `sub` is computed:

```python
                with Image.open(src) as im:
                    im = im.convert("RGBA")
                    px, py, pw, ph = _scaled_rect(rec["box"], im.width, im.height)
                    sub = im.crop((px, py, px + pw, py + ph))
                    if _is_empty(sub):
                        left_to_vanilla += 1
                        ctx.add("slice", Severity.INFO,
                                "source region empty; left to vanilla", rec["output"])
                        continue
                    if op == "clip":
```

The rest of the branch is unchanged. `continue` advances the record loop, skipping both the write and `made += 1`.

- [ ] **Step 5: Update the summary finding**

Replace the closing `ctx.add` with:

```python
    ctx.add("slice", Severity.INFO,
            f"produced {made} sprites"
            + (f"; {left_to_vanilla} left to vanilla (empty source region)"
               if left_to_vanilla else "")
            + (f"; {skipped_special} special skipped" if skipped_special else ""))
```

"gui sprites" becomes "sprites" because after Task 3 this stage also produces particle and painting sprites.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: 62 passed (58 existing + 4 new). If an existing test fails, the skip rule is suppressing real art — investigate rather than relaxing the test.

- [ ] **Step 7: Verify the fix against the real pack**

Run:

```bash
.venv/bin/python -m mc_pack_converter.cli convert "../M8SON 1.8 PVP PACK" \
  -o /tmp/slicefix --target 26.1.2 >/dev/null
.venv/bin/python - <<'EOF'
from PIL import Image
from pathlib import Path
R = Path("/tmp/slicefix")
sp = sorted(R.rglob("textures/gui/sprites/**/*.png"))
empty = [p.relative_to(R) for p in sp
         if Image.open(p).convert("RGBA").getchannel("A").getbbox() is None]
print("sprites:", len(sp), "fully transparent:", len(empty))
EOF
```

Expected: `sprites: 130 fully transparent: 0` — down from 153 produced with 23 transparent. If any transparent sprite remains, `_is_empty` is not reached on that code path.

- [ ] **Step 8: Commit**

```bash
git add mc_pack_converter/stages/slice.py tests/test_slice.py
git commit -m "fix: never write empty slice output over vanilla

A 1.8.9 atlas has no pixels where post-1.8.9 GUI elements live, so the
slice stage was writing fully-transparent PNGs that override vanilla and
render the element invisible. 23 of 153 sprites were affected, including
the crosshair and hotbar attack indicators, the offhand slot backdrop,
the potion-effect HUD backdrop and the freezing hearts.

Skip any crop with no visible pixels and log it, so vanilla shows through."
```

---

### Task 2: Expand the 1.14 slicer helpers in the generator

`slicer_1.14.java` is already vendored but yields zero records: the parser only matches a literal `new Box(...)`, and every 1.14 output is wrapped in a helper call.

**Files:**
- Modify: `tools/gen_slices.py`
- Create: `tests/test_gen_slices.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces, all in `tools/gen_slices.py`:
  - `as_int(expr: str) -> int`
  - `parse_box(expr: str) -> list[int] | None` — resolves `new Box(...)`, `b256(...)`, `b128(...)` to `[x, y, w, h, tw, th]`
  - `parse_helper_output(expr: str, input_path: str) -> dict | None`
  - `SKIPPED_HELPERS: dict[str, int]` — counts of deliberately unported helper calls
  - `PARTICLE_REF: int` = `128`
  - Existing `parse_entry(entry: str) -> list[dict]` keeps its signature.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gen_slices.py`:

```python
"""Tests for the slicer-source parser in tools/gen_slices.py.

tools/ is a script directory, not a package, so load it by path.
"""
import importlib.util
from pathlib import Path

import pytest

GEN = Path(__file__).parent.parent / "tools" / "gen_slices.py"


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("gen_slices", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_as_int_evaluates_java_arithmetic(gen):
    assert gen.as_int("0 * 2") == 0
    assert gen.as_int(" 3 * 2 ") == 6
    assert gen.as_int("16") == 16


def test_as_int_rejects_non_arithmetic(gen):
    with pytest.raises(ValueError):
        gen.as_int("open('/etc/passwd')")


def test_particle_short_form(gen):
    # particle("critical_hit", 1, 4) -> 8px cell at column 1, row 4,
    # restated against a 128x128 reference (see spec: 1.13 grew the canvas
    # but kept the 8px cell, so a 1.8.9 atlas is 128x128 at the same coords).
    rec = gen.parse_helper_output(
        'particle("critical_hit", 1, 4)',
        "assets/minecraft/textures/particle/particles.png")
    assert rec == {
        "input": "assets/minecraft/textures/particle/particles.png",
        "output": "assets/minecraft/textures/particle/critical_hit.png",
        "box": [8, 32, 8, 8, 256, 256], "op": "crop"}


def test_particle_with_width_and_height(gen):
    rec = gen.parse_helper_output(
        'particle("flash", 4, 2, 4, 4)',
        "assets/minecraft/textures/particle/particles.png")
    assert rec["box"] == [32, 16, 32, 32, 256, 256]
    assert rec["output"] == "assets/minecraft/textures/particle/flash.png"


def test_particle_with_offsets(gen):
    # particle("bubble_pop_1", 1 * 2, 16, 0, 3, 2, 2)
    rec = gen.parse_helper_output(
        'particle("bubble_pop_1", 1 * 2, 16, 0, 3, 2, 2)',
        "assets/minecraft/textures/particle/particles.png")
    assert rec["box"] == [16, 131, 16, 16, 256, 256]


def test_painting_uses_16px_cells_on_256_reference(gen):
    rec = gen.parse_helper_output(
        'painting("donkey_kong", 12, 7, 4, 3)',
        "assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png")
    assert rec == {
        "input": "assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png",
        "output": "assets/minecraft/textures/painting/donkey_kong.png",
        "box": [192, 112, 64, 48, 256, 256], "op": "crop"}


def test_explosion_uses_32px_cells_on_128_reference(gen):
    rec = gen.parse_helper_output(
        'explosion("explosion_9", 1, 2)',
        "assets/minecraft/textures/entity/explosion.png")
    assert rec == {
        "input": "assets/minecraft/textures/entity/explosion.png",
        "output": "assets/minecraft/textures/particle/explosion_9.png",
        "box": [32, 64, 32, 32, 128, 128], "op": "crop"}


def test_effect_and_sweep_are_not_ported(gen):
    # effect(): the 18px grid inside inventory.png was rearranged in 1.9, so
    # the slicer's coordinates would mis-map a 1.8.9 pack. sweep(): needs the
    # slicer's SQUARE post-op and the texture is 1.9+. Both out of scope.
    assert gen.parse_helper_output(
        'effect("speed", 0, 0)',
        "assets/minecraft/textures/gui/container/inventory.png") is None
    assert gen.parse_helper_output(
        "sweep(3, 3, 0)", "assets/minecraft/textures/entity/sweep.png") is None
    assert gen.SKIPPED_HELPERS["effect"] >= 1
    assert gen.SKIPPED_HELPERS["sweep"] >= 1


def test_parse_box_resolves_b256_and_b128(gen):
    assert gen.parse_box("b256(8 * 1, 8 * 2, 8, 8)") == [8, 16, 8, 8, 256, 256]
    assert gen.parse_box("b128(32 * 3, 32 * 1, 32, 32)") == [96, 32, 32, 32, 128, 128]
    assert gen.parse_box("new Box(0, 0, 182, 22, 256, 256)") == [0, 0, 182, 22, 256, 256]


def test_particles_input_is_rebased_to_128(gen):
    # Whole-input pass: every record cut from particles.png ends up on a
    # 128x128 reference, including the bare fishing_hook SimpleOutputFile.
    entry = '''input("assets/minecraft/textures/particle/particles.png",
        particle("critical_hit", 1, 4),
        new SimpleOutputFile("assets/minecraft/textures/entity/fishing_hook.png", b256(8 * 1, 8 * 2, 8, 8))
    )'''
    recs = gen.parse_entry(entry)
    assert len(recs) == 2
    assert all(r["box"][4:] == [128, 128] for r in recs)
    by_out = {r["output"]: r for r in recs}
    assert by_out["assets/minecraft/textures/particle/critical_hit.png"]["box"] == \
        [8, 32, 8, 8, 128, 128]
    assert by_out["assets/minecraft/textures/entity/fishing_hook.png"]["box"] == \
        [8, 16, 8, 8, 128, 128]


def test_painting_input_is_not_rebased(gen):
    entry = '''input("assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png",
        painting("kebab", 0, 0, 1, 1)
    )'''
    recs = gen.parse_entry(entry)
    assert recs[0]["box"] == [0, 0, 16, 16, 256, 256]


def test_full_1_14_source_record_counts(gen):
    recs = gen.parse_file(GEN.parent / "slicer_src" / "slicer_1.14.java")
    outs = [r["output"] for r in recs]
    assert len(recs) == 134           # 27 painting + 90 particle + 16 explosion + 1 hook
    assert sum(1 for o in outs if "/textures/painting/" in o) == 27
    assert sum(1 for o in outs if "/textures/particle/" in o) == 106  # 90 + 16
    assert "assets/minecraft/textures/entity/fishing_hook.png" in outs
    assert not any("/textures/mob_effect/" in o for o in outs)
    assert not any("sweep_" in o for o in outs)
    # every particles.png record sits on the 128 reference
    assert all(r["box"][4:] == [128, 128] for r in recs
               if r["input"].endswith("particle/particles.png"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_gen_slices.py -v`

Expected: every test errors with `AttributeError: module 'gen_slices' has no attribute 'as_int'` (and similar) — none of the new functions exist yet.

- [ ] **Step 3: Add the arithmetic evaluator and box resolver**

In `tools/gen_slices.py`, add after the `BOX` regex:

```python
# --- 1.14 slicer helpers ---------------------------------------------------
# tools/slicer_src/slicer_1.14.java wraps every output in one of five private
# helpers, all reducing to a single primitive:
#   gridSprite(x,y,w,h,xOff,yOff,xScale,yScale)
#     -> Box(xScale*x + xOff, yScale*y + yOff, w*xScale, h*yScale, 256, 256)
# The helper arguments are literal integer arithmetic ("1 * 2"), so the
# generator evaluates them directly.
BFN = re.compile(r"\bb(256|128)\(([^()]*)\)")
INT_EXPR = re.compile(r"[\d\s+*\-()]+")
PARTICLE_REF = 128
SKIPPED_HELPERS = {"effect": 0, "sweep": 0}


def as_int(expr: str) -> int:
    """Evaluate a literal integer arithmetic expression from the Java source."""
    if not INT_EXPR.fullmatch(expr.strip()):
        raise ValueError(f"not an integer expression: {expr!r}")
    return int(eval(expr, {"__builtins__": {}}, {}))


def parse_box(expr: str) -> list[int] | None:
    """Resolve `new Box(...)`, `b256(...)` or `b128(...)` to [x,y,w,h,tw,th]."""
    m = BOX.search(expr)
    if m:
        return [int(g) for g in m.groups()]
    m = BFN.search(expr)
    if m:
        ref = int(m.group(1))
        x, y, w, h = (as_int(a) for a in split_top_level(m.group(2)))
        return [x, y, w, h, ref, ref]
    return None
```

`eval` runs only over a string that fully matched `INT_EXPR` (digits, whitespace, `+ - * ( )`), with builtins stripped, against source vendored into this repo.

- [ ] **Step 4: Add the helper-call parser**

Add below `parse_box`:

```python
HELPER = re.compile(r"(painting|particle|explosion|effect|sweep)\s*\(")


def parse_helper_output(expr: str, input_path: str) -> dict | None:
    """Resolve a 1.14 helper call to a record, or None if not one / not ported.

    Not ported, deliberately:
      effect() - the 18px effect grid inside inventory.png was rearranged in
                 1.9, so these coordinates would mis-map a 1.8.9 pack.
      sweep()  - needs the slicer's SQUARE post-op; the texture is 1.9+.
    """
    expr = expr.strip()
    m = HELPER.match(expr)
    if not m:
        return None
    fn = m.group(1)
    if fn in SKIPPED_HELPERS:
        SKIPPED_HELPERS[fn] += 1
        return None
    args = split_top_level(balanced(expr, expr.index("(")))
    name = STR.match(args[0]).group(1)
    nums = [as_int(a) for a in args[1:]]
    if fn == "painting":
        x, y, w, h = nums
        return {"input": input_path,
                "output": f"assets/minecraft/textures/painting/{name}.png",
                "box": [16 * x, 16 * y, 16 * w, 16 * h, 256, 256], "op": "crop"}
    if fn == "explosion":
        x, y = nums
        return {"input": input_path,
                "output": f"assets/minecraft/textures/particle/{name}.png",
                "box": [32 * x, 32 * y, 32, 32, 128, 128], "op": "crop"}
    # particle(n,x,y) | particle(n,x,y,w,h) | particle(n,x,y,xOff,yOff,w,h)
    if len(nums) == 2:
        x, y = nums
        w = h = 1
        xoff = yoff = 0
    elif len(nums) == 4:
        x, y, w, h = nums
        xoff = yoff = 0
    else:
        x, y, xoff, yoff, w, h = nums
    return {"input": input_path,
            "output": f"assets/minecraft/textures/particle/{name}.png",
            "box": [8 * x + xoff, 8 * y + yoff, 8 * w, 8 * h, 256, 256],
            "op": "crop"}
```

Note `particle` emits a `256` reference here; the rebase to `128` happens once, per input, in Step 6 — one place expresses that decision.

- [ ] **Step 5: Route helper calls in `parse_output`**

In `parse_output`, replace:

```python
    box = BOX.search(expr)
    if box:
        b = [int(g) for g in box.groups()]
        op = "special" if special else "crop"
        return {"input": input_path, "output": out_path, "box": b, "op": op}
    return None
```

with:

```python
    b = parse_box(expr)
    if b:
        op = "special" if special else "crop"
        return {"input": input_path, "output": out_path, "box": b, "op": op}
    return None
```

That is what lets the bare `fishing_hook` output resolve its `b256(...)` box.

- [ ] **Step 6: Wire helpers and the rebase into `parse_entry`**

In `parse_entry`, replace the `if fn == "input":` block with:

```python
    if fn == "input":
        in_path = parse_name_to_path(args[0])
        if not in_path:
            return recs
        for out_expr in args[1:]:
            r = parse_helper_output(out_expr, in_path) or parse_output(out_expr, in_path)
            if r:
                recs.append(r)
        if in_path.endswith("textures/particle/particles.png"):
            # 1.13 kept the 8px cell size and GREW the canvas (1.8.9 is
            # 128x128, 1.13.2 is 256x256 at the same coordinates), so restate
            # these boxes against a 128 reference. Proportional scaling then
            # yields cell = width/16, correct for a 1x or a 4x 1.8.9 atlas.
            for r in recs:
                if r["box"][4:] == [256, 256]:
                    r["box"][4:] = [PARTICLE_REF, PARTICLE_REF]
```

- [ ] **Step 7: Report skipped helpers in `main`**

In `main()`, after the per-file loop, before the dedupe:

```python
    for fn, n in SKIPPED_HELPERS.items():
        if n:
            print(f"skipped {n} {fn}() outputs (not ported - see spec)")
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_gen_slices.py -v`

Expected: all 12 tests PASS. If `test_full_1_14_source_record_counts` reports a different total, do not adjust the expected number — find the records the parser is dropping or duplicating.

- [ ] **Step 9: Commit**

```bash
git add tools/gen_slices.py tests/test_gen_slices.py
git commit -m "feat: parse the 1.14 slicer's helper calls in gen_slices

slicer_1.14.java yielded zero records because the parser only matched a
literal new Box(...) and every 1.14 output goes through a helper. Evaluate
painting/particle/explosion and resolve b256/b128 boxes.

Particle boxes are rebased onto a 128x128 reference: 1.13 kept the 8px
cell size and grew the canvas, so a 1.8.9 atlas carries the same
coordinates at half the size. effect() and sweep() stay unported."
```

---

### Task 3: Regenerate `slices.json` and guard it

**Files:**
- Modify: `mc_pack_converter/data/slices.json` (generated)
- Test: `tests/test_gen_slices.py`

**Interfaces:**
- Consumes: `tools/gen_slices.py` from Task 2.
- Produces: `slices.json` with 543 records. Task 5's contact sheet relies on the particle/painting outputs existing.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_gen_slices.py`:

```python
def test_shipped_slices_table_contains_1_14_records():
    """Guard against regenerating slices.json without the 1.14 records."""
    import json
    from pathlib import Path
    table = json.loads(
        (Path(__file__).parent.parent / "mc_pack_converter" / "data"
         / "slices.json").read_text())
    assert len(table) == 543
    by_out = {r["output"]: r for r in table}
    assert by_out["assets/minecraft/textures/particle/critical_hit.png"]["box"] == \
        [8, 32, 8, 8, 128, 128]
    assert by_out["assets/minecraft/textures/painting/kebab.png"]["box"] == \
        [0, 0, 16, 16, 256, 256]
    assert by_out["assets/minecraft/textures/particle/explosion_0.png"]["box"] == \
        [0, 0, 32, 32, 128, 128]
    assert "assets/minecraft/textures/entity/fishing_hook.png" in by_out
    assert not any("/textures/mob_effect/" in o for o in by_out)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_gen_slices.py::test_shipped_slices_table_contains_1_14_records -v`

Expected: FAIL — `assert 409 == 543`.

- [ ] **Step 3: Regenerate the table**

Run: `.venv/bin/python tools/gen_slices.py`

The lines that matter in its output:

```
slicer_1.14.java: 134 slice records
skipped 27 effect() outputs (not ported - see spec)
skipped 8 sweep() outputs (not ported - see spec)

TOTAL: 543 records -> .../mc_pack_converter/data/slices.json
```

The per-file counts for `slicer_1.20.2.java` and `slicer262.java` must not change — they summed to 409 before this work, and the 543 total is the check on that.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: 75 passed (62 after Task 1 + 12 from Task 2 + this one).

- [ ] **Step 5: Verify against the real pack**

Run:

```bash
.venv/bin/python -m mc_pack_converter.cli convert "../M8SON 1.8 PVP PACK" \
  -o /tmp/sliced --target 26.1.2 >/dev/null
.venv/bin/python - <<'EOF'
from PIL import Image
from pathlib import Path
R = Path("/tmp/sliced/assets/minecraft/textures")
part = sorted(p for p in (R / "particle").glob("*.png") if p.name != "particles.png")
paint = sorted(p for p in (R / "painting").glob("*.png")
               if not p.name.startswith("paintings_"))
print("particle sprites:", len(part))
print("paintings:", len(paint))
print("fishing_hook:", (R / "entity/fishing_hook.png").exists())
for name in ["critical_hit", "enchanted_hit", "flame", "explosion_0"]:
    p = R / "particle" / f"{name}.png"
    print(f"  {name}: exists={p.exists()}", Image.open(p).size if p.exists() else "")
allpng = [p for p in Path("/tmp/sliced").rglob("*.png")]
empty = [p for p in allpng
         if Image.open(p).convert("RGBA").getchannel("A").getbbox() is None]
print("PNGs:", len(allpng), "fully transparent:", len(empty))
EOF
```

Expected: `particle sprites: 92` (75 particle + 16 explosion + the pack's pre-existing `footprint.png`), `paintings: 27`, `fishing_hook: True`, all four named sprites present, and **`fully transparent: 0`**.

The 15 particle names that do not appear are correct absences — `glitter_0..7`, `nautilus` and `damage` are blank in a 1.8.9 atlas, and `bubble_pop_0..4` sit below a 128-tall canvas. All fall back to vanilla.

- [ ] **Step 6: Commit**

```bash
git add mc_pack_converter/data/slices.json tests/test_gen_slices.py
git commit -m "feat: slice particles, paintings and explosion frames

Regenerated slices.json: 409 -> 543 records. Recovers 75 custom particle
sprites (including critical_hit and enchanted_hit), 27 paintings and 16
explosion frames that modern Minecraft could not read from the 1.8.9
atlases."
```

---

### Task 4: Contact sheet renderer

**Files:**
- Create: `mc_pack_converter/contact_sheet.py`
- Test: `tests/test_contact_sheet.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `ATLAS_1_14: set[str]` — the three source atlas paths whose outputs get sheeted.
  - `build_contact_sheet(root: Path, rel_paths: list[str], out_path: Path) -> bool` — writes a PNG, returns `False` if there was nothing to draw.
  - Task 5 calls both.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_contact_sheet.py`:

```python
from PIL import Image

from mc_pack_converter.contact_sheet import ATLAS_1_14, build_contact_sheet


def _sprite(root, rel, size=(8, 8), color=(200, 40, 40, 255)):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, color).save(p)


def test_sheet_lays_out_one_tile_per_sprite(tmp_path):
    rels = [f"textures/particle/p{i}.png" for i in range(3)]
    for r in rels:
        _sprite(tmp_path, r)
    out = tmp_path / "sheet.png"
    assert build_contact_sheet(tmp_path, rels, out) is True
    with Image.open(out) as im:
        # 3 sprites -> one row of 8 columns
        assert im.size == (8 * 104, 1 * 88)
        assert im.getchannel("A").getbbox() is not None  # not blank


def test_sheet_wraps_to_multiple_rows(tmp_path):
    rels = [f"textures/particle/p{i}.png" for i in range(9)]
    for r in rels:
        _sprite(tmp_path, r)
    out = tmp_path / "sheet.png"
    build_contact_sheet(tmp_path, rels, out)
    with Image.open(out) as im:
        assert im.size == (8 * 104, 2 * 88)


def test_sheet_returns_false_with_nothing_to_draw(tmp_path):
    out = tmp_path / "sheet.png"
    assert build_contact_sheet(tmp_path, [], out) is False
    assert not out.exists()


def test_sheet_ignores_missing_files(tmp_path):
    _sprite(tmp_path, "textures/particle/real.png")
    out = tmp_path / "sheet.png"
    assert build_contact_sheet(
        tmp_path, ["textures/particle/real.png", "textures/particle/gone.png"],
        out) is True
    with Image.open(out) as im:
        assert im.size == (8 * 104, 1 * 88)


def test_sheet_handles_sprites_larger_than_a_tile(tmp_path):
    # A 2x painting sprite is 128x96; it must scale down, not overflow.
    _sprite(tmp_path, "textures/painting/pigscene.png", size=(128, 96))
    out = tmp_path / "sheet.png"
    build_contact_sheet(tmp_path, ["textures/painting/pigscene.png"], out)
    with Image.open(out) as im:
        assert im.size == (8 * 104, 1 * 88)


def test_atlas_set_names_the_three_1_14_sources():
    assert ATLAS_1_14 == {
        "assets/minecraft/textures/particle/particles.png",
        "assets/minecraft/textures/entity/explosion.png",
        "assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png",
    }
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_contact_sheet.py -v`

Expected: collection error — `ModuleNotFoundError: No module named 'mc_pack_converter.contact_sheet'`.

- [ ] **Step 3: Write the module**

Create `mc_pack_converter/contact_sheet.py`:

```python
"""Render sliced sprites into one labelled PNG for eyeball review.

Written next to the output archive, never inside it: `write_output` zips
everything under the working root, so a sheet placed there would ship
inside the pack.
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw

# The 1.14 slicer's source atlases. Outputs cut from these are what the sheet
# shows; the GUI sprites from the 1.20.2 slicer are excluded to keep it small.
ATLAS_1_14 = {
    "assets/minecraft/textures/particle/particles.png",
    "assets/minecraft/textures/entity/explosion.png",
    "assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png",
}

TILE = 64          # sprites are scaled to fit this box, nearest-neighbour
PAD = 6
LABEL_H = 12
COLS = 8
CELL_W = 104       # wider than TILE so sprite names fit under each tile
CELL_H = TILE + PAD * 2 + LABEL_H
CHECK = 8          # checkerboard square size, so alpha reads
NAME_CHARS = 16

BG = (32, 32, 32, 255)
LIGHT = (90, 90, 90, 255)
DARK = (70, 70, 70, 255)
TEXT = (230, 230, 230, 255)


def _checkerboard() -> Image.Image:
    board = Image.new("RGBA", (TILE, TILE), DARK)
    d = ImageDraw.Draw(board)
    for y in range(0, TILE, CHECK):
        for x in range(0, TILE, CHECK):
            if (x // CHECK + y // CHECK) % 2 == 0:
                d.rectangle([x, y, x + CHECK - 1, y + CHECK - 1], fill=LIGHT)
    return board


def build_contact_sheet(root: Path, rel_paths: list[str], out_path: Path) -> bool:
    """Render each rel_path (relative to root) as a labelled tile.

    Returns False, writing nothing, if there is nothing to draw.
    """
    entries = [(r, root / r) for r in sorted(rel_paths)]
    entries = [(r, p) for r, p in entries if p.exists()]
    if not entries:
        return False
    rows = (len(entries) + COLS - 1) // COLS
    sheet = Image.new("RGBA", (COLS * CELL_W, rows * CELL_H), BG)
    board = _checkerboard()
    draw = ImageDraw.Draw(sheet)
    for i, (rel, path) in enumerate(entries):
        ox = (i % COLS) * CELL_W + (CELL_W - TILE) // 2
        oy = (i // COLS) * CELL_H + PAD
        sheet.paste(board, (ox, oy))
        with Image.open(path) as im:
            im = im.convert("RGBA")
            scale = TILE / max(im.width, im.height)
            w, h = max(1, round(im.width * scale)), max(1, round(im.height * scale))
            im = im.resize((w, h), Image.NEAREST)
            sheet.paste(im, (ox + (TILE - w) // 2, oy + (TILE - h) // 2), im)
        draw.text((ox, oy + TILE + 2), Path(rel).stem[:NAME_CHARS], fill=TEXT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return True
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_contact_sheet.py -v`

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add mc_pack_converter/contact_sheet.py tests/test_contact_sheet.py
git commit -m "feat: contact-sheet renderer for sliced sprites

One labelled PNG of every sprite cut from the 1.14 atlases, on a
checkerboard so alpha reads, for review before loading the pack in-game."
```

---

### Task 5: Emit the contact sheet from the CLI

**Files:**
- Modify: `mc_pack_converter/pipeline.py`
- Modify: `mc_pack_converter/stages/slice.py`
- Modify: `mc_pack_converter/cli.py`
- Test: `tests/test_slice.py`, `tests/test_cli_e2e.py`

**Interfaces:**
- Consumes: `build_contact_sheet`, `ATLAS_1_14` from Task 4.
- Produces: `ConversionContext.sliced: list[tuple[str, str]]` — `(input_atlas, output_sprite)` for each sprite actually written.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_slice.py`:

```python
def test_written_sprites_are_recorded_on_the_context(mini_pack, monkeypatch):
    root = mini_pack()
    _put(root, "assets/minecraft/textures/particle/particles.png", (128, 128))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/particle/particles.png",
         "output": "assets/minecraft/textures/particle/flame.png",
         "box": [0, 24, 8, 8, 128, 128], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert ctx.sliced == [("assets/minecraft/textures/particle/particles.png",
                           "assets/minecraft/textures/particle/flame.png")]


def test_skipped_sprites_are_not_recorded(mini_pack, monkeypatch):
    root = mini_pack()
    _put(root, "assets/minecraft/textures/particle/particles.png", (128, 128),
         (0, 0, 0, 0))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/particle/particles.png",
         "output": "assets/minecraft/textures/particle/flame.png",
         "box": [0, 24, 8, 8, 128, 128], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert ctx.sliced == []
```

Append to `tests/test_cli_e2e.py`:

```python
def test_contact_sheet_written_beside_archive(tmp_path, mini_pack):
    from PIL import Image
    root = mini_pack()
    atlas = root / "assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png"
    atlas.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (256, 256), (10, 120, 200, 255)).save(atlas)
    out = tmp_path / "converted.zip"
    convert(root, out, target="26.1.2", report_only=False)
    sheet = tmp_path / "converted-slices.png"
    assert sheet.exists(), "contact sheet not written next to the archive"
    with zipfile.ZipFile(out) as zf:
        assert "converted-slices.png" not in zf.namelist()
        assert not any(n.endswith("-slices.png") for n in zf.namelist())


def test_no_contact_sheet_when_nothing_sliced(tmp_path, mini_pack):
    root = mini_pack()
    out = tmp_path / "plain.zip"
    convert(root, out, target="26.1.2", report_only=False)
    assert not (tmp_path / "plain-slices.png").exists()
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_slice.py tests/test_cli_e2e.py -v`

Expected: the two slice tests fail with `AttributeError: 'ConversionContext' object has no attribute 'sliced'`; `test_contact_sheet_written_beside_archive` fails on the missing sheet.

- [ ] **Step 3: Add the field to the context**

In `mc_pack_converter/pipeline.py`, in `ConversionContext`:

```python
@dataclass
class ConversionContext:
    root: Path
    findings: list[Finding] = field(default_factory=list)
    target: str = "26.2"
    sliced: list[tuple[str, str]] = field(default_factory=list)
    """(input atlas, output sprite) for every sprite the slice stage wrote."""
```

- [ ] **Step 4: Record written sprites in the slice stage**

In `mc_pack_converter/stages/slice.py`, in the `try` block, change:

```python
            _copy_meta(src, dst)
            made += 1
```

to:

```python
            _copy_meta(src, dst)
            ctx.sliced.append((rec["input"], rec["output"]))
            made += 1
```

- [ ] **Step 5: Render the sheet in `convert`**

In `mc_pack_converter/cli.py`, add to the imports:

```python
from .contact_sheet import ATLAS_1_14, build_contact_sheet
```

and replace:

```python
        if not report_only:
            write_output(ctx, out_path, reports)
        return ctx
```

with:

```python
        if not report_only:
            write_output(ctx, out_path, reports)
            sheet = out_path.with_name(out_path.stem + "-slices.png")
            rels = [out for src, out in ctx.sliced if src in ATLAS_1_14]
            if build_contact_sheet(ctx.root, rels, sheet):
                print(f"contact sheet: {sheet} ({len(rels)} sprites)")
        return ctx
```

It runs before the `finally` clause removes the working copy, and writes outside `ctx.root` so `write_output` cannot zip it.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: 85 passed (75 after Task 3 + 6 from Task 4 + 4 here).

- [ ] **Step 7: Generate the sheet for the real pack and look at it**

Run:

```bash
.venv/bin/python -m mc_pack_converter.cli convert "../M8SON 1.8 PVP PACK" \
  -o /tmp/review.zip --target 26.1.2 | grep "contact sheet"
```

The line is printed by `convert` before `main` prints the reports, so grep for it rather than tailing.

Expected: `contact sheet: /tmp/review-slices.png (119 sprites)` — 75 particle + 16 explosion + 27 painting + `fishing_hook`, which is also cut from `particles.png`. Open the PNG and confirm the sprites look like the pack's art, not garbage or fragments. **Misaligned box math shows up here as sprites cut across cell boundaries** — that is the check this sheet exists for.

- [ ] **Step 8: Commit**

```bash
git add mc_pack_converter/pipeline.py mc_pack_converter/stages/slice.py \
        mc_pack_converter/cli.py tests/test_slice.py tests/test_cli_e2e.py
git commit -m "feat: write a sprite contact sheet beside the output archive"
```

---

### Task 6: Ship the build and close the tracked defect

**Files:**
- Modify: `docs/known-issues.md`

**Interfaces:**
- Consumes: everything above.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Build the deliverable**

Run:

```bash
.venv/bin/python -m mc_pack_converter.cli convert "../M8SON 1.8 PVP PACK" \
  -o ../M8SON-converted-26.1.2.zip --target 26.1.2 | tail -20
```

Target `26.1.2`, not the `26.2` default — that is the Minecraft version being tested against.

- [ ] **Step 2: Confirm every success criterion from the spec**

Run:

```bash
.venv/bin/python - <<'EOF'
import json, zipfile
from io import BytesIO
from PIL import Image
Z = "../M8SON-converted-26.1.2.zip"
with zipfile.ZipFile(Z) as zf:
    names = zf.namelist()
    T = "assets/minecraft/textures/"
    part = [n for n in names if n.startswith(T + "particle/") and n.endswith(".png")]
    paint = [n for n in names if n.startswith(T + "painting/") and n.endswith(".png")]
    print("particle/:", len(part), " painting/:", len(paint))
    print("fishing_hook:", T + "entity/fishing_hook.png" in names)
    for n in ["particle/critical_hit.png", "particle/enchanted_hit.png",
              "particle/explosion_0.png", "painting/kebab.png"]:
        print(f"  {n}: {T + n in names}")
    empty = []
    for n in names:
        if not n.endswith(".png"):
            continue
        with Image.open(BytesIO(zf.read(n))) as im:
            if im.convert("RGBA").getchannel("A").getbbox() is None:
                empty.append(n)
    print("fully transparent PNGs:", len(empty), empty[:5])
    meta = json.loads(zf.read("pack.mcmeta"))
    print("pack.mcmeta:", meta["pack"]["min_format"], meta["pack"]["max_format"])
    print("build tag:", meta["pack"]["description"])
EOF
```

Expected: `particle/: 93` — 75 particle sprites + 16 explosion frames + the pack's own `footprint.png` + the now-dead `particles.png` source atlas, which stays by design. `painting/: 28` (27 sprites + the source atlas). `fishing_hook: True`, all four named sprites `True`, **`fully transparent PNGs: 0`**, `min_format`/`max_format` both `84`, and a `[conv 26.1.2 <MMDD-HHMM>]` build tag.

Do not proceed if `fully transparent PNGs` is non-zero.

- [ ] **Step 3: Mark the defect fixed**

In `docs/known-issues.md`, replace the status line of §1:

```markdown
**Status:** open in shipped builds · fix specified, not yet implemented
```

with:

```markdown
**Status:** FIXED 2026-07-29 — `stages/slice.py` skips crops with no visible
pixels. Kept here for the record; the reproduce block below now reports 0.
```

Leave §2 (mob-effect icons) untouched — still open.

- [ ] **Step 4: Commit**

```bash
git add docs/known-issues.md
git commit -m "docs: mark the transparent-slice-output defect fixed"
```

- [ ] **Step 5: Hand off for in-game verification**

Report to the user, with the numbers from Step 2:

- what landed: 75 particle sprites, 27 paintings, 16 explosion frames, and the transparent-override fix
- the contact sheet path, for review before loading
- the delivery steps that actually matter: **copy the zip to `.minecraft/resourcepacks/`, delete the old copy first, restart Minecraft, and confirm the `[conv 26.1.2 <MMDD-HHMM>]` build tag in the resource-pack list.** OptiFine caches textures and sky, so a stale copy makes every fix look like it did nothing.
- what to look at in-game: the **attack indicator** (was invisible), **crit and enchanted-hit particles** (were vanilla), **paintings** (were vanilla), and the potion-effect HUD backdrop
- what is still expected to be vanilla, so it is not reported as a regression: the 23 **potion-effect icons** (`docs/known-issues.md` §2), `bubble_pop`, `glitter`, `nautilus` and `damage` particles, plus the anvil, enchanting-table and creative-inventory GUIs

Do not claim any in-game behaviour is verified. Only the user can confirm that.

---

## Notes for the implementer

- **Never hand-edit `slices.json`.** Change `tools/gen_slices.py` and regenerate.
- **The 128 rebase is the one subtle thing here.** If particle sprites come out as quarter-size fragments or blank, the reference is wrong — check that every record from `particles.png` ends `[..., 128, 128]`.
- **Trust `tools/slicer_src/*.java` over any recollection of Minecraft's layout.** It is Mojang's own migration source, vendored deliberately.
- If a sprite looks wrong, diff the pack's atlas against the version-pinned vanilla one rather than guessing: `raw.githubusercontent.com/InventivetalentDev/minecraft-assets/<version>/assets/minecraft/...`
- Empty output is a legitimate result. Do not "fix" a missing sprite by inventing pixels — the pack genuinely has none, and vanilla is the right fallback.
