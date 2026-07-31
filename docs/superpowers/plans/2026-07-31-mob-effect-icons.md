# Mob-Effect Icons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover the M8SON pack's 19 custom potion-effect icons by emitting `textures/mob_effect/<name>.png` from the 18px grid inside the pack's 1.8.9 `inventory.png`.

**Architecture:** Mojang's vendored 1.14 slicer already defines the exact cell → effect-name mapping, and re-measurement proved that mapping is valid for a 1.8.9 pack. So this is a generator change only: un-skip the slicer's `effect()` helper in `tools/gen_slices.py`, filter it through an allowlist of the 19 effects vanilla 1.8.9 actually draws, and regenerate `mc_pack_converter/data/slices.json`. The existing `slice` stage consumes the new records unchanged.

**Tech Stack:** Python 3.12, Pillow, pytest. Repo venv at `.venv/`. Run everything from `/home/daedalus/linux/mc-pack-converter`.

**Spec:** `docs/superpowers/specs/2026-07-31-mob-effect-icons-design.md`

## Global Constraints

- Branch: `feature/mob-effect-icons`. Already created, spec already committed at `6c5aa0b`.
- Use the repo venv: `.venv/bin/python`, `.venv/bin/pytest`. Never bare `python`.
- **Fix and format — never create art.** Every output must be a sub-rectangle of pixels the pack already ships.
- Supported input is a 1.8.9-era pack (`pack_format: 1`), per `docs/known-issues.md` §0. Do not widen it.
- `mc_pack_converter/data/slices.json` is **generated**. Never hand-edit it; only regenerate via `tools/gen_slices.py`.
- Baseline before any change: 89 tests pass, `slices.json` has 543 records, `parse_file` on `slicer_1.14.java` yields 134.
- Effect grid facts, all measured and fixed: origin `(0,198)`, cells 18×18, reference `256,256`, no rebase.

## File Structure

| file | responsibility | change |
|---|---|---|
| `tools/gen_slices.py` | turn vendored slicer Java into records | add the `effect()` branch + `EFFECTS_1_8_9` allowlist + skip reporting |
| `mc_pack_converter/data/slices.json` | shipped record table | regenerated, 543 → 562 |
| `tests/test_gen_slices.py` | generator parser tests | replace the "not ported" test; update the two count guards |
| `tests/test_slice.py` | slice-stage behaviour tests | add two resolution-independence tests for the new records |
| `docs/known-issues.md` | open defects and unrecovered art | rewrite §2 — the entry closes |

`mc_pack_converter/stages/slice.py` is **not** modified.

---

### Task 1: Port `effect()` behind the 1.8.9 allowlist

**Files:**
- Modify: `tools/gen_slices.py:91` (`SKIPPED_HELPERS`), `tools/gen_slices.py:126-154` (`parse_helper_output`), `tools/gen_slices.py:284-286` (skip reporting in `main`)
- Test: `tests/test_gen_slices.py`

**Interfaces:**
- Consumes: `gen.parse_helper_output(expr: str, input_path: str) -> dict | None` and `gen.parse_file(path: Path) -> list[dict]`, both already present.
- Produces: `gen.EFFECTS_1_8_9: set[str]` (19 names) and `gen.SKIPPED_EFFECTS: list[str]` (names dropped by the allowlist, appended in encounter order). Task 2 relies on `parse_file` now yielding 153 records for `slicer_1.14.java`, 19 of them under `assets/minecraft/textures/mob_effect/`.

- [ ] **Step 1: Replace the "not ported" test with the ported-behaviour tests**

In `tests/test_gen_slices.py`, delete `test_effect_and_sweep_are_not_ported` entirely and put these in its place:

```python
def test_effect_emits_18px_cell_at_origin_198(gen):
    # effect("regeneration", 7, 0) -> gridSprite(x, y, 1, 1, 0, 198, 18, 18)
    # -> Box(18*7, 198 + 18*0, 18, 18, 256, 256). No reference rebase:
    # inventory.png is 256x256 in 1.8.9 and in 1.13 alike.
    rec = gen.parse_helper_output(
        'effect("regeneration", 7, 0)',
        "assets/minecraft/textures/gui/container/inventory.png")
    assert rec == {
        "input": "assets/minecraft/textures/gui/container/inventory.png",
        "output": "assets/minecraft/textures/mob_effect/regeneration.png",
        "box": [126, 198, 18, 18, 256, 256], "op": "crop"}


def test_effect_second_row_offsets_by_18(gen):
    rec = gen.parse_helper_output(
        'effect("jump_boost", 2, 1)',
        "assets/minecraft/textures/gui/container/inventory.png")
    assert rec["box"] == [36, 216, 18, 18, 256, 256]
    assert rec["output"] == "assets/minecraft/textures/mob_effect/jump_boost.png"


def test_effects_without_1_8_9_art_are_dropped(gen):
    # levitation/glowing/luck/unluck are 1.9 additions sitting in row-2 gaps
    # that hold only vanilla's 20px corner guide marks in 1.8.9; health_boost
    # is a 1.8.9 effect that is simply undrawn; slow_falling/conduit_power/
    # dolphins_grace are 1.13 additions at (8,0)-(10,0) with 0px behind them.
    # Emitting any of them would override vanilla with a near-invisible sprite.
    inv = "assets/minecraft/textures/gui/container/inventory.png"
    for name, x, y in [("levitation", 3, 2), ("glowing", 4, 2), ("luck", 5, 2),
                       ("unluck", 6, 2), ("health_boost", 7, 2),
                       ("slow_falling", 8, 0), ("conduit_power", 9, 0),
                       ("dolphins_grace", 10, 0)]:
        assert gen.parse_helper_output(f'effect("{name}", {x}, {y})', inv) is None
        assert name in gen.SKIPPED_EFFECTS
    assert len(gen.EFFECTS_1_8_9) == 19


def test_sweep_is_still_not_ported(gen):
    # Needs the slicer's SQUARE post-op, and the texture is 1.9+.
    assert gen.parse_helper_output(
        "sweep(3, 3, 0)", "assets/minecraft/textures/entity/sweep.png") is None
    assert gen.SKIPPED_HELPERS["sweep"] >= 1
    assert "effect" not in gen.SKIPPED_HELPERS
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
.venv/bin/pytest tests/test_gen_slices.py -v -k "effect or sweep"
```

Expected: `test_effect_emits_18px_cell_at_origin_198`, `test_effect_second_row_offsets_by_18` FAIL (`parse_helper_output` returns `None`); `test_effects_without_1_8_9_art_are_dropped` and `test_sweep_is_still_not_ported` FAIL with `AttributeError` on `gen.SKIPPED_EFFECTS` / `gen.EFFECTS_1_8_9`, and `"effect" not in gen.SKIPPED_HELPERS` is false.

- [ ] **Step 3: Narrow `SKIPPED_HELPERS` and add the allowlist**

In `tools/gen_slices.py`, replace the line `SKIPPED_HELPERS = {"effect": 0, "sweep": 0}` with:

```python
SKIPPED_HELPERS = {"sweep": 0}

# Effects that vanilla 1.8.9 actually draws in the 18px grid at (0,198) inside
# gui/container/inventory.png. Measured cell-by-cell against the version-pinned
# vanilla mirror (InventivetalentDev/minecraft-assets): these 19 cells carry
# 25-72% opaque pixels. The eight names the 1.14 slicer also emits do not:
#   levitation, glowing, luck, unluck  1.9 additions in row-2 gaps that hold
#                                      only vanilla's corner guide marks in
#                                      1.8.9 - exactly 20px per cell
#   health_boost                       a 1.8.9 effect, but undrawn at (7,2);
#                                      the same 20px of guide marks
#   slow_falling, conduit_power,       1.13 additions at (8,0)-(10,0), off the
#   dolphins_grace                     1.8.9 art entirely - 0px
# Emitting the excluded eight would ship near-invisible sprites that OVERRIDE
# vanilla's icons - the invisible-attack-indicator defect again. The grid
# ITSELF is stable 1.8.9 -> 1.13 (see the 2026-07-31 spec); only this
# drawn/undrawn split is ours to know, so it lives here rather than in the
# slicer source.
EFFECTS_1_8_9 = {
    "speed", "slowness", "haste", "mining_fatigue", "strength", "weakness",
    "poison", "regeneration",
    "invisibility", "hunger", "jump_boost", "nausea", "night_vision",
    "blindness", "resistance", "fire_resistance",
    "water_breathing", "wither", "absorption",
}
SKIPPED_EFFECTS: list[str] = []
```

- [ ] **Step 4: Add the `effect` branch to `parse_helper_output`**

In the same file, update the docstring of `parse_helper_output` — replace its "Not ported, deliberately:" block with:

```python
    """Resolve a 1.14 helper call to a record, or None if not one / not ported.

    Not ported, deliberately:
      sweep()  - needs the slicer's SQUARE post-op; the texture is 1.9+.

    effect() IS ported, but only for the effects vanilla 1.8.9 draws; the rest
    are dropped into SKIPPED_EFFECTS (see EFFECTS_1_8_9).
    """
```

Then insert this branch immediately after the `if fn == "explosion":` block and before the `# particle(n,x,y) | ...` comment:

```python
    if fn == "effect":
        if name not in EFFECTS_1_8_9:
            SKIPPED_EFFECTS.append(name)
            return None
        x, y = nums
        return {"input": input_path,
                "output": f"assets/minecraft/textures/mob_effect/{name}.png",
                "box": [18 * x, 198 + 18 * y, 18, 18, 256, 256], "op": "crop"}
```

- [ ] **Step 5: Report dropped effects in `main`**

In `main()`, directly after the existing `for fn, n in SKIPPED_HELPERS.items():` loop, add:

```python
    if SKIPPED_EFFECTS:
        print(f"skipped {len(SKIPPED_EFFECTS)} effect() outputs with no 1.8.9 "
              f"art: {', '.join(sorted(SKIPPED_EFFECTS))}")
```

- [ ] **Step 6: Run the new tests to verify they pass**

```bash
.venv/bin/pytest tests/test_gen_slices.py -v -k "effect or sweep"
```

Expected: 4 passed.

- [ ] **Step 7: Update the 1.14-source count guard**

`test_full_1_14_source_record_counts` still asserts the old totals. In `tests/test_gen_slices.py`, change its body:

- `assert len(recs) == 134` → `assert len(recs) == 153` with the comment updated to `# 27 painting + 90 particle + 16 explosion + 1 hook + 19 mob_effect`
- replace `assert not any("/textures/mob_effect/" in o for o in outs)` with:

```python
    assert sum(1 for o in outs if "/textures/mob_effect/" in o) == 19
    assert "assets/minecraft/textures/mob_effect/speed.png" in outs
    assert "assets/minecraft/textures/mob_effect/levitation.png" not in outs
```

- [ ] **Step 8: Run the full generator suite**

```bash
.venv/bin/pytest tests/test_gen_slices.py -v
```

Expected: all pass. `test_shipped_slices_table_contains_1_14_records` still passes because `slices.json` has not been regenerated yet — that is Task 2.

- [ ] **Step 9: Commit**

```bash
git add tools/gen_slices.py tests/test_gen_slices.py
git commit -m "feat: port the 1.14 slicer's effect() behind a 1.8.9 allowlist

The 18px effect grid inside inventory.png is stable from 1.8.9 to 1.13, so
the slicer's coordinates apply directly. Only the 19 effects vanilla 1.8.9
draws are emitted; the other eight cells hold nothing but guide marks and
would override vanilla with near-invisible sprites.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Regenerate `slices.json`

**Files:**
- Modify: `mc_pack_converter/data/slices.json` (regenerated, do not hand-edit)
- Test: `tests/test_gen_slices.py` (`test_shipped_slices_table_contains_1_14_records`)

**Interfaces:**
- Consumes: `gen.EFFECTS_1_8_9`, the `effect` branch of `parse_helper_output` from Task 1.
- Produces: a 562-record `slices.json` including 19 records whose `output` is under `assets/minecraft/textures/mob_effect/`. Task 3 and Task 4 both read this table.

- [ ] **Step 1: Update the shipped-table guard to the post-regeneration values**

In `tests/test_gen_slices.py`, in `test_shipped_slices_table_contains_1_14_records`:

- `assert len(table) == 543` → `assert len(table) == 562`
- replace `assert not any("/textures/mob_effect/" in o for o in by_out)` with:

```python
    assert sum(1 for o in by_out if "/textures/mob_effect/" in o) == 19
    assert by_out["assets/minecraft/textures/mob_effect/regeneration.png"] == {
        "input": "assets/minecraft/textures/gui/container/inventory.png",
        "output": "assets/minecraft/textures/mob_effect/regeneration.png",
        "box": [126, 198, 18, 18, 256, 256], "op": "crop"}
    for absent in ("levitation", "glowing", "luck", "unluck", "health_boost",
                   "slow_falling", "conduit_power", "dolphins_grace"):
        assert f"assets/minecraft/textures/mob_effect/{absent}.png" not in by_out
```

- [ ] **Step 2: Run it to verify it fails**

```bash
.venv/bin/pytest tests/test_gen_slices.py::test_shipped_slices_table_contains_1_14_records -v
```

Expected: FAIL — `assert 543 == 562`.

- [ ] **Step 3: Regenerate the table**

```bash
.venv/bin/python tools/gen_slices.py
```

Expected output includes `slicer_1.14.java: 153 slice records`, a line reading `skipped 8 effect() outputs with no 1.8.9 art: conduit_power, dolphins_grace, glowing, health_boost, levitation, luck, slow_falling, unluck`, and `TOTAL: 562 records`.

- [ ] **Step 4: Run it to verify it passes**

```bash
.venv/bin/pytest tests/test_gen_slices.py -v
```

Expected: all pass.

- [ ] **Step 5: Confirm the regeneration is deterministic and touched nothing else**

`slices.json` is pretty-printed at `indent=0`, so a record spans 13 lines — a line count is not a record count. Check determinism by hash and the delta by parsing:

```bash
sha1sum mc_pack_converter/data/slices.json
.venv/bin/python tools/gen_slices.py >/dev/null
sha1sum mc_pack_converter/data/slices.json
git diff --numstat mc_pack_converter/data/slices.json
git show HEAD:mc_pack_converter/data/slices.json | .venv/bin/python -c "import json,sys;print('before',len(json.load(sys.stdin)))"
.venv/bin/python -c "import json;print('after',len(json.load(open('mc_pack_converter/data/slices.json'))))"
```

Expected: the two hashes match — regeneration is deterministic. `--numstat` reports `247  0` (19 records × 13 lines, nothing removed), and the counts print `before 543` / `after 562`. If anything is *removed*, stop: the change is not purely additive and something else regressed.

- [ ] **Step 6: Run the whole suite**

```bash
.venv/bin/pytest -q
```

Expected: **92 passed** — the baseline is 89, and Task 1 deleted one test and added four. State the actual number you observe; do not assume.

- [ ] **Step 7: Commit**

```bash
git add mc_pack_converter/data/slices.json tests/test_gen_slices.py
git commit -m "feat: regenerate slices.json with 19 mob_effect records

543 -> 562 records.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Prove the new records cut correctly at any pack resolution

**Files:**
- Test: `tests/test_slice.py`

**Interfaces:**
- Consumes: the record shape produced in Task 1 — `box [18x, 198+18y, 18, 18, 256, 256]`, `op "crop"`.
- Produces: nothing consumed by later tasks. No source file changes; `stages/slice.py` handles these records as-is.

The point of these two tests is the proportional-box invariant: the M8SON pack's `inventory.png` is 512×512, so a `256`-referenced box must scale up. A regression here would silently cut the wrong cell and mislabel every icon.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_slice.py`:

```python
def _grid_atlas(root, rel, size, cell_px, marked_cell, color=(200, 30, 40, 255)):
    """A transparent atlas with one 18px-grid cell filled, at origin (0,198).

    cell_px is the scaled cell size (18 at 1x, 36 at 2x).
    """
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    cx, cy = marked_cell
    scale = size[0] // 256
    x0 = cx * cell_px
    y0 = 198 * scale + cy * cell_px
    im.paste(Image.new("RGBA", (cell_px, cell_px), color), (x0, y0))
    im.save(p)
    return p


JUMP_BOOST_REC = {
    "input": "assets/minecraft/textures/gui/container/inventory.png",
    "output": "assets/minecraft/textures/mob_effect/jump_boost.png",
    "box": [36, 216, 18, 18, 256, 256], "op": "crop"}


def test_effect_cell_is_cut_at_standard_res(mini_pack, monkeypatch):
    root = mini_pack()
    _grid_atlas(root, "assets/minecraft/textures/gui/container/inventory.png",
                (256, 256), 18, (2, 1))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [JUMP_BOOST_REC])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    out = root / "assets/minecraft/textures/mob_effect/jump_boost.png"
    assert out.exists()
    im = Image.open(out).convert("RGBA")
    assert im.size == (18, 18)
    # the whole crop is the marked cell, nothing bled in from a neighbour
    assert im.getchannel("A").getbbox() == (0, 0, 18, 18)
    assert im.getpixel((0, 0)) == (200, 30, 40, 255)


def test_effect_cell_is_cut_at_2x_res(mini_pack, monkeypatch):
    # M8SON ships a 512x512 inventory.png; the 256-referenced box must scale.
    root = mini_pack()
    _grid_atlas(root, "assets/minecraft/textures/gui/container/inventory.png",
                (512, 512), 36, (2, 1))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [JUMP_BOOST_REC])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    im = Image.open(
        root / "assets/minecraft/textures/mob_effect/jump_boost.png"
    ).convert("RGBA")
    assert im.size == (36, 36)
    assert im.getchannel("A").getbbox() == (0, 0, 36, 36)
    assert im.getpixel((0, 0)) == (200, 30, 40, 255)
```

- [ ] **Step 2: Run them to verify they fail**

```bash
.venv/bin/pytest tests/test_slice.py -v -k effect_cell
```

Expected: FAIL — `_grid_atlas` and `JUMP_BOOST_REC` do not exist until the append lands, so run this only after Step 1 and expect a genuine assertion failure if the cut is wrong. If both pass on the first run, that is the correct outcome here: the slice stage is unmodified by design and these tests are characterising it. Say so plainly in the task report rather than inventing a failure.

- [ ] **Step 3: Run the whole suite**

```bash
.venv/bin/pytest -q
```

Expected: all pass, two more than Task 2's total.

- [ ] **Step 4: Commit**

```bash
git add tests/test_slice.py
git commit -m "test: cut an effect cell at 1x and 2x pack resolution

Guards the proportional-box invariant for the mob_effect records: a
regression would cut the wrong cell and mislabel every icon.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Verify against the real pack and close `known-issues.md` §2

**Files:**
- Modify: `docs/known-issues.md:100-133` (§2)
- Modify: `docs/superpowers/specs/2026-07-31-mob-effect-icons-design.md:4` (Status line)

**Interfaces:**
- Consumes: the regenerated `slices.json` from Task 2.
- Produces: the verified icon count and coverage figures quoted in the rewritten §2.

- [ ] **Step 1: Convert the real pack**

```bash
.venv/bin/python -m mc_pack_converter.cli convert "../M8SON 1.8 PVP PACK" \
  -o /tmp/claude-1000/-home-daedalus-linux/df2935d5-74f4-4be8-901c-b7dcad69b944/scratchpad/effects.zip \
  --target 26.1.2
```

- [ ] **Step 2: Assert the output contract**

```bash
.venv/bin/python - <<'EOF'
import zipfile
from io import BytesIO
from PIL import Image
Z = ("/tmp/claude-1000/-home-daedalus-linux/df2935d5-74f4-4be8-901c-b7dcad69b944"
     "/scratchpad/effects.zip")
EXPECTED = {
    "speed", "slowness", "haste", "mining_fatigue", "strength", "weakness",
    "poison", "regeneration", "invisibility", "hunger", "jump_boost", "nausea",
    "night_vision", "blindness", "resistance", "fire_resistance",
    "water_breathing", "wither", "absorption"}
with zipfile.ZipFile(Z) as zf:
    names = [n for n in zf.namelist()
             if n.startswith("assets/minecraft/textures/mob_effect/")]
    got = {n.rsplit("/", 1)[1][:-4] for n in names}
    print("count:", len(names))
    assert got == EXPECTED, f"missing={EXPECTED - got} unexpected={got - EXPECTED}"
    for n in sorted(names):
        with Image.open(BytesIO(zf.read(n))) as im:
            im = im.convert("RGBA")
            a = list(im.getchannel("A").get_flattened_data())
            pct = 100 * sum(1 for p in a if p > 0) / len(a)
            assert im.size == (36, 36), (n, im.size)
            # 6.2% is the guide-mark signature of an undrawn cell
            assert pct > 15, f"{n} is {pct:.1f}% opaque - guide marks, not art"
            print(f"  {n.rsplit('/',1)[1]:24s} {im.size} {pct:5.1f}%")
print("OK: 19 mob_effect sprites, all real art")
EOF
```

Expected: `count: 19`, every sprite 36×36 with 19–65% coverage, and `OK: 19 mob_effect sprites, all real art`.

- [ ] **Step 3: Render a review sheet of the recovered icons**

This is for eyeball confirmation only — it writes to the scratchpad and changes no shipped code. The shipped contact sheet covers the three 1.14 atlases and is deliberately left alone.

```bash
.venv/bin/python - <<'EOF'
import zipfile
from io import BytesIO
from PIL import Image, ImageDraw
S = ("/tmp/claude-1000/-home-daedalus-linux/df2935d5-74f4-4be8-901c-b7dcad69b944"
     "/scratchpad")
with zipfile.ZipFile(f"{S}/effects.zip") as zf:
    names = sorted(n for n in zf.namelist()
                   if n.startswith("assets/minecraft/textures/mob_effect/"))
    Z, COLS = 3, 7
    tile = 36 * Z
    rows = (len(names) + COLS - 1) // COLS
    sheet = Image.new("RGBA", (COLS * tile, rows * (tile + 14)), (35, 35, 45, 255))
    d = ImageDraw.Draw(sheet)
    for i, n in enumerate(names):
        with Image.open(BytesIO(zf.read(n))) as im:
            im = im.convert("RGBA").resize((tile, tile), Image.NEAREST)
        x, y = (i % COLS) * tile, (i // COLS) * (tile + 14)
        sheet.alpha_composite(im, (x, y))
        d.rectangle([x, y, x + tile - 1, y + tile - 1], outline=(90, 90, 110, 255))
        d.text((x + 2, y + tile + 2), n.rsplit("/", 1)[1][:-4][:16],
               fill=(220, 220, 230, 255))
    sheet.convert("RGB").save(f"{S}/mob_effect_review.png")
    print("wrote", f"{S}/mob_effect_review.png", len(names), "icons")
EOF
```

Then open `mob_effect_review.png` and confirm each icon sits under the right name — swirl/`speed`, ball-and-chain/`slowness`, rabbit/`jump_boost`, shield/`resistance`, fish/`water_breathing`, and so on. **Report any mismatch instead of proceeding**; a mismatch means the grid mapping is wrong and the whole premise needs re-examination.

- [ ] **Step 4: Rewrite `docs/known-issues.md` §2**

Replace the whole of §2 — from the `## 2. 23 custom mob-effect icons are silently dropped` heading down to (not including) the `## Not defects` heading — with:

```markdown
## 2. Custom mob-effect icons

**Status:** FIXED 2026-07-31 — `tools/gen_slices.py` emits the 1.14 slicer's
`effect()` records for the 19 effects vanilla 1.8.9 draws.
**Design:** `docs/superpowers/specs/2026-07-31-mob-effect-icons-design.md`

Modern Minecraft reads potion-effect icons from `textures/mob_effect/<name>.png`;
nothing reads the 18px icon strip inside `textures/gui/container/inventory.png`
anymore. The pack's custom icons were therefore lost to vanilla.

**This entry previously claimed 1.9 rearranged the grid, and that recovering the
icons needed a hand-researched 1.8.9 cell → name table. Both were wrong.** The
occupancy figures behind that claim were measured at `y=166`, which is where the
effect *background* box lives; the icon strip starts at `y=198`. Re-measured at
the right origin against the version-pinned vanilla mirror, the layout is stable
from 1.8.9 through 1.13 — 1.9 and 1.13 only *filled cells that are empty in
1.8.9*, and no cell was ever repurposed. Mojang's 1.14 slicer coordinates apply
to a 1.8.9 pack directly.

The count was wrong too: the M8SON pack holds **19** custom icons, not 23. It
mirrors vanilla 1.8.9 cell-for-cell.

Eight names the slicer emits are deliberately **not** produced, because 1.8.9 has
no art behind them (`EFFECTS_1_8_9` in `tools/gen_slices.py`):

| not produced | 1.8.9 cell | what is actually there |
|---|---|---|
| `levitation`, `glowing`, `luck`, `unluck` | `(3,2)`–`(6,2)` | 1.9 additions; 20px of vanilla corner guide marks |
| `health_boost` | `(7,2)` | a 1.8.9 effect, but undrawn; same 20px of guide marks |
| `slow_falling`, `conduit_power`, `dolphins_grace` | `(8,0)`–`(10,0)` | 1.13 additions; 0px |

They fall back to vanilla, which is correct — drawing them would be creating art.
The exclusion is done at generation time rather than by a coverage threshold in
`stages/slice.py`, because a threshold is a heuristic that could suppress a
legitimately sparse sprite, while this is a measured fact about 1.8.9.
```

- [ ] **Step 5: Flip the spec's status line**

In `docs/superpowers/specs/2026-07-31-mob-effect-icons-design.md`, change

```
**Status:** Designed, not yet implemented — `feature/mob-effect-icons`
```

to

```
**Status:** Implemented on `feature/mob-effect-icons`
```

- [ ] **Step 6: Run the whole suite one last time**

```bash
.venv/bin/pytest -q
```

Expected: all pass. Report the actual count.

- [ ] **Step 7: Commit**

```bash
git add docs/known-issues.md docs/superpowers/specs/2026-07-31-mob-effect-icons-design.md
git commit -m "docs: close known-issues #2, correct the grid-rearrangement claim

19 custom effect icons recovered and verified against the real pack.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Not in this plan

- **Rebuilding the delivered pack zip.** The output filename question (overwrite `M8SON-converted-26.1.2-slicer.zip` in place vs. dated filenames) is unresolved with Mason and is not this change's call.
- **Adding `inventory.png` to the shipped contact sheet's `ATLAS_1_14`.** Out of the approved spec; Task 4 Step 3 gets the same review value in the scratchpad.
- **In-game verification.** Mason's loop, after the branch merges. Requires deleting the old copy in `.minecraft/resourcepacks/`, restarting Minecraft, and confirming the `[conv 26.1.2 <MMDD-HHMM>]` build tag — OptiFine caches textures and a stale copy makes every fix look like it did nothing.
- **Later-version source packs.** A 1.9–1.12 pack would ship art in the four 1.9 cells and the allowlist would discard it. Consistent with §0's 1.8.9-only scope; widening it is a separate decision.
