# 1.14 Slicer Port: Particles, Paintings, Explosion — Design

**Date:** 2026-07-29
**Status:** Approved design, pre-implementation
**Proving-ground fixture:** `M8SON 1.8 PVP PACK` (a "Faithful 32x32 edit", `pack_format: 1`)
**Builds on:** `2026-07-28-mc-pack-converter-design.md`

## Goal

Recover the pack's custom **particle**, **painting**, and **explosion** art, which
modern Minecraft cannot read because 1.14 split those atlases into individual
per-sprite files. Do it by porting Mojang's official 1.14 slicer (already vendored
at `tools/slicer_src/slicer_1.14.java`) through the existing generator → `slices.json`
→ `slice` stage pipeline.

Fix, in the same change, a defect this work uncovered: **the slice stage currently
writes fully-transparent PNGs for GUI elements that did not exist in 1.8.9,
overriding vanilla and rendering them invisible in-game.**

Core philosophy is unchanged: **fix and format — never create art.** Every output
is a sub-rectangle of pixels the pack already ships.

## Findings that drive the design

All measured empirically against the version-pinned vanilla mirror
(`InventivetalentDev/minecraft-assets`), comparing 1.8.9 against 1.13.2 — the
version pair the 1.14 slicer sits between.

### The five 1.14 slicer atlases

| atlas | 1.8.9 → 1.13 layout | in M8SON | custom art | verdict |
|---|---|---|---|---|
| `particle/particles.png` | **stable** — only additions, in cells empty in 1.8.9 | 128×128 | **61 of 76** sprites differ from vanilla, incl. `critical_hit`, `enchanted_hit` | port |
| `painting/paintings_kristoffer_zetterstrand.png` | **byte-identical** | 512×512 (2×) | **55%** of pixels | port |
| `entity/explosion.png` | **byte-identical** | 128×128 | **0%** (pure vanilla) | port for reusability; no visual gain on this pack |
| `entity/sweep.png` | n/a | absent (1.9+ texture) | — | out of scope |
| `gui/container/inventory.png` → `mob_effect/*` | **REARRANGED in 1.9** | 23 custom icons | — | out of scope, own spec |

Per-cell diff of the particles grid, 1.8.9 vs 1.13.2: 54 of 256 cells differ, and
all but eight are cells that are *empty in 1.8.9* and filled in 1.13 (`glitter_*`,
`nautilus`, `damage`, `bubble_pop_*`). The eight genuine art changes are `spark_4`,
`spark_6`, and six SGA runes. **No cell was ever repurposed**, so the slicer's
1.13-era coordinates are valid against a 1.8.9 atlas.

The mob-effect grid is the exception. Occupancy of the 18px effect grid inside
`inventory.png` goes 7/8/8 in 1.8.9 → 11/11/8 in 1.9.4 (3331 differing pixels),
so 1.9 re-arranged it to fit `levitation`, `glowing`, `luck`, `unluck`. The
slicer's coordinates describe the *post*-rearrangement grid and would mis-map a
1.8.9 pack. Recovering those 23 custom icons needs its own researched
1.8.9 grid→name table; deferred to a separate spec.

### The invisible-sprite defect

`stages/slice.py` crops a region and writes it unconditionally. For any modern GUI
element whose region is blank in a 1.8.9 atlas, that writes a fully transparent
PNG — which **overrides** vanilla rather than falling back to it. Verified in a
real run of the current `master`: of 153 produced `gui/sprites`, **23 are fully
transparent**:

- `hud/crosshair_attack_indicator_{background,full,progress}.png`
- `hud/hotbar_attack_indicator_{background,progress}.png`
- `hud/hotbar_offhand_{left,right}.png`
- `hud/effect_background{,_ambient}.png`
- `hud/heart/frozen_{full,half,hardcore_full,hardcore_half}{,_blinking}.png` (8)
- `container/horse/{saddle,llama_armor}_slot.png`
- `container/brewing_stand/fuel_length.png`
- `icon/draft_report.png`
- `statistics/item_{dropped,picked_up}.png`

The attack indicator is the one that matters for a PVP pack. This defect ships in
`M8SON-converted-26.1.2-FRESH.zip`.

The fix — skip a crop whose result is empty and let vanilla show through — is also
exactly what the new particle records need: 10 of the 91 named particle cells are
empty in a 1.8.9 atlas (`glitter_0..7`, `nautilus`, `damage`) and 5 more
(`bubble_pop_0..4`) sit below a 128-tall canvas entirely. One rule serves both.

## Architecture

Five files change. No new stage, no new op, no new concept in the pipeline.

| file | change |
|---|---|
| `tools/slicer_src/slicer_1.14.java` | none — already vendored |
| `tools/gen_slices.py` | expand the 1.14 helper calls into records |
| `mc_pack_converter/data/slices.json` | regenerated: 409 → ~513 records |
| `mc_pack_converter/stages/slice.py` | skip empty crops; record them as findings |
| `mc_pack_converter/contact_sheet.py` (new) + `cli.py` | emit the review sheet |

### Generator: helper expansion

`slicer_1.14.java` wraps every output in one of five private helpers over a single
primitive:

```java
gridSprite(path,x,y,w,h,xOff,yOff,xScale,yScale)
  -> new Box(xScale*x + xOff, yScale*y + yOff, w*xScale, h*yScale, 256, 256)
```

The existing parser only matches literal `new Box(...)`, which is why
`slicer_1.14.java` currently yields zero records. Teach it these call forms, with
their arithmetic evaluated:

- `painting(n,x,y,w,h)` → `assets/minecraft/textures/painting/<n>.png`,
  box `[16x, 16y, 16w, 16h, 256, 256]`
- `explosion(n,x,y)` → `assets/minecraft/textures/particle/<n>.png`,
  box `[32x, 32y, 32, 32, 128, 128]`
- `particle(n,x,y)`, `particle(n,x,y,w,h)`, `particle(n,x,y,xOff,yOff,w,h)`
  → `assets/minecraft/textures/particle/<n>.png`,
  box `[8x + xOff, 8y + yOff, 8w, 8h, `**`128, 128`**`]`
- a bare `new SimpleOutputFile(path, b256(...))` inside the particles input
  → `assets/minecraft/textures/entity/fishing_hook.png`, same 128 reference

All emit `op: "crop"`, the existing record shape. `effect(...)` and `sweep(...)`
emit nothing; the generator prints a skip note stating why.

**The 128 rebase is the crux.** Boxes in this project are proportional
(`x,y,w,h` relative to `totalW,totalH`), which is what makes the pipeline
resolution-independent. Naively keeping the slicer's `256,256` reference for
particles would halve every coordinate against M8SON's 128×128 atlas and produce
garbage, because 1.13 did not scale the atlas up — **it kept the 8px cell size and
grew the canvas** to fit new rows. Restating the same coordinates against a
`128,128` reference makes proportional scaling yield `cell = width / 16`, which is
correct for a 1× *or* a 4× 1.8.9-layout atlas. Paintings (`256,256`) and explosion
(`128,128`) already match their 1.8.9 canvases and are emitted unrebased.

### slice.py: the skip rule

After computing the cropped region:

```python
if sub.getchannel("A").getbbox() is None:   # empty source region
    ctx.add("slice", Severity.INFO,
            "source region empty; left to vanilla", rec["output"])
    continue
```

Checking the alpha channel's bbox specifically (not `sub.getbbox()`) avoids
treating a transparent-but-nonzero-RGB region as content. Zero-size crops are
skipped by the same guard. Out-of-bounds boxes need no special case: PIL pads a
crop past the edge with transparent pixels, so `bubble_pop_*` falls out for free.
Applies to `crop` and `clip` alike — a `clip` canvas whose kept region is empty is
itself empty. The stage summary line gains `; N left to vanilla`.

This is a behavior change for the 409 pre-existing records, and an intended one:
it is what fixes the 23 invisible sprites.

### Contact sheet

`contact_sheet.py` builds one labelled grid PNG from the sprites produced off the
three 1.14 atlases (~104 tiles): 64px nearest-neighbour tiles, 8 per row, a
checkerboard behind each so alpha reads, sprite name captioned under each tile in
PIL's default bitmap font.

It is written **next to** the output archive as `<out>-slices.png`, never inside
it — `write_output` zips everything under `ctx.root`, so a sheet written there
would ship inside the pack.

Plumbing: the slice stage appends each produced output path to a `ctx.sliced` list;
`cli.convert` renders the sheet after `run_pipeline` and before the temporary
working copy is removed.

## Out of scope

- **`mob_effect` icons** — needs a hand-built, separately-verified 1.8.9 effect-grid
  map. Own spec. 23 custom icons stay on vanilla until then.
- **`sweep.png`** — absent from this pack; needs the slicer's `SQUARE` post-op.
- **Deleting the now-dead source atlases.** `particles.png`, `explosion.png` and
  the paintings atlas are unread by 26.x after slicing, but so are `widgets.png`
  and `icons.png` already. Leaving them is consistent, costs ~100KB, and removing
  them is a separate cleanup with its own fallback risk.

## Testing

Unit tests stay synthetic and fast; the real 65MB pack is verified by hand.

**Generator** (`tests/test_gen_slices.py`)
- a fixture Java snippet with `particle("critical_hit", 1, 4)` yields
  `box == [8, 32, 8, 8, 128, 128]`, `op == "crop"`, output
  `assets/minecraft/textures/particle/critical_hit.png`
- the `xOff/yOff` particle form and the `w,h` particle form evaluate correctly
- `painting(...)` and `explosion(...)` yield their documented boxes and references
- `effect(...)` and `sweep(...)` yield no records

**Slice stage** (extend `tests/test_slice.py`)
- a record over a fully transparent source region writes no file and adds an INFO
  finding
- an out-of-bounds box writes no file
- a 512×512 particles atlas cuts a sprite at cell size 32 — resolution
  independence, the point of the rebase
- the 58 existing tests stay green

**Contact sheet** (`tests/test_contact_sheet.py`)
- three input sprites produce a sheet of the expected dimensions, non-blank

**Real-pack run** (manual)
- **zero** fully-transparent PNGs anywhere in the output, down from 23

## Success criteria

1. `pytest` green — 58 existing plus the new tests.
2. Real-pack conversion produces zero fully-transparent output PNGs.
3. 91 new sprites land in `textures/particle/` (75 particle sprites + 16 explosion
   frames — all 16 explosion cells are confirmed non-empty in this pack),
   `textures/entity/fishing_hook.png` exists, and 27 land in `textures/painting/`
   — all non-empty. Both directories also still contain their source atlases, which
   are left in place by design.
4. The contact sheet renders every sliced sprite legibly.
5. In-game on 26.1.2 + OptiFine: the attack indicator is visible, and crit /
   enchanted-hit particles show the pack's art. Requires deleting the old copy in
   `.minecraft/resourcepacks/`, restarting Minecraft, and confirming the
   `[conv 26.1.2 <MMDD-HHMM>]` build tag in the resource-pack list — OptiFine
   caches textures, and a stale copy makes every fix look like it did nothing.

## References

- `github.com/Mojang/slicer`, `1.14/Main.java` — vendored at
  `tools/slicer_src/slicer_1.14.java`. Authoritative source of every coordinate
  in this design.
- `github.com/InventivetalentDev/minecraft-assets` — version-pinned vanilla asset
  mirror; source of the 1.8.9 vs 1.13.2 diffs above. Fetch raw at
  `raw.githubusercontent.com/InventivetalentDev/minecraft-assets/<version>/assets/minecraft/...`
- `github.com/agentdid127/ResourcePackConverter` — cross-check. Its
  `ParticlesSlicer1_14` covers the same ground; its `InventoryConverter` treats
  the effect strip as a pure y-shift, which the 1.9 rearrangement measured above
  shows is insufficient.
