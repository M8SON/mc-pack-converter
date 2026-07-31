# Mob-Effect Icons: Recovering the 1.8.9 Effect Grid — Design

**Date:** 2026-07-31
**Status:** Designed, not yet implemented — `feature/mob-effect-icons`
**Proving-ground fixture:** `M8SON 1.8 PVP PACK` (a "Faithful 32x32 edit", `pack_format: 1`)
**Builds on:** `2026-07-29-particles-slicer-design.md`
**Supersedes:** the "1.9 rearranged the effect grid" claim in that spec and in
`docs/known-issues.md` §2. See *Correcting the record* below.

## Goal

Recover the pack's custom **potion-effect icons**, which modern Minecraft cannot
read because it loads them from `textures/mob_effect/<name>.png` rather than from
the 18px grid inside `textures/gui/container/inventory.png`.

Core philosophy is unchanged: **fix and format — never create art.** Every output
is a sub-rectangle of pixels the pack already ships.

## Correcting the record

This work was previously blocked on "a researched 1.8.9 effect-grid → name table",
because occupancy of the grid was measured at 7/8/8 cells in 1.8.9 against 11/11/8
in 1.9.4, and read as a 1.9 rearrangement that would make Mojang's slicer
coordinates mis-map a 1.8.9 pack.

**That measurement was taken at the wrong grid origin.** `y=166` is where the
effect *background* box lives (`container/inventory/effect_background_large`, an
existing slice record); the icon strip starts at `y=198` in 1.8.9, the same origin
the 1.14 slicer uses. Re-measured at `y=198` against the version-pinned vanilla
mirror, **the layout is stable from 1.8.9 through 1.13** — 1.9 and 1.13 *added*
icons into cells that are empty in 1.8.9, and no cell was ever repurposed.

Every cell of vanilla 1.8.9, labelled with the name Mojang's 1.14 slicer assigns
to that coordinate:

| | col 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| **row 0** | swirl → `speed` | ball+chain → `slowness` | gold pickaxe → `haste` | grey pickaxe → `mining_fatigue` | sword → `strength` | faded sword → `weakness` | dark heart → `poison` | pink heart → `regeneration` |
| **row 1** | ghost → `invisibility` | rotten leg → `hunger` | rabbit → `jump_boost` | zombie villager → `nausea` | green eye → `night_vision` | dark eye → `blindness` | shield → `resistance` | fire → `fire_resistance` |
| **row 2** | fish → `water_breathing` | wither heart → `wither` | yellow heart → `absorption` | *(guide marks only)* | *(guide marks)* | *(guide marks)* | *(guide marks)* | *(guide marks)* |

All 19 match. `agentdid127`'s `InventoryConverter` y-shift, cited previously as
evidence of movement, shifts the effect *background*, not the icons.

Two recorded numbers were also wrong. The M8SON pack holds **19** custom icons,
not 23 — it mirrors vanilla 1.8.9 cell-for-cell. And `health_boost` is a 1.8.9
effect that simply has no icon in the 1.8.9 sheet.

**Consequence: there is no table to research.** The 1.14 slicer's `effect()`
records are directly correct for a 1.8.9 pack, and this becomes a generator change.

## Findings that drive the design

Measured against `InventivetalentDev/minecraft-assets`, 18×18 cells at origin
`(0,198)`, comparing vanilla 1.8.9 with the M8SON pack (512×512, a 2× copy).

### Which cells hold art

Opaque-pixel coverage per cell is identical in shape between vanilla 1.8.9 and the
pack — the pack redrew all 19 icons and inherited the rest verbatim:

| cells | vanilla 1.8.9 | M8SON (2×) | meaning |
|---|---|---|---|
| the 19 named above | 80–234 px (25–72%) | 240–838 px (19–65%) | real art |
| `levitation`, `glowing`, `luck`, `unluck`, `health_boost` — `(3,2)`–`(7,2)` | **exactly 20 px** (6.2%) | **exactly 80 px** (6.2%) | vanilla corner guide marks |
| `slow_falling`, `conduit_power`, `dolphins_grace` — `(8,0)`–`(10,0)` | **0 px** | **0 px** | 1.13 additions, off the 1.8.9 art |

### The guide-mark hazard

The five row-2 gap cells are *not* empty. Vanilla 1.8.9 draws faint orange/blue
corner marks there — 20 px per cell, scaled to 80 px in the pack's 2× copy.

`stages/slice.py`'s `_is_empty` guard tests whether the alpha bbox is `None`, so it
will **not** catch them. Emitted, they would ship as near-invisible sprites that
*override* vanilla's `levitation`/`glowing`/`luck`/`unluck`/`health_boost` icons —
the same class of defect as the invisible attack indicator fixed on 2026-07-29.

They are excluded at generation time rather than at runtime. A coverage-threshold
guard in `slice.py` would be more general but is a heuristic that could suppress a
legitimately sparse sprite; the exclusion here is a fact about 1.8.9, so it belongs
in the data.

## Architecture

Two source files change, plus documentation. No new stage, no new op, no new data
file, no change to `slice.py`.

| file | change |
|---|---|
| `tools/gen_slices.py` | expand `effect()` calls into records, filtered by a 1.8.9 allowlist |
| `mc_pack_converter/data/slices.json` | regenerated: 543 → 562 records (+19 `mob_effect`) |
| `docs/known-issues.md` | §2 rewritten — the entry closes and the corrected grid finding replaces the rearrangement theory |

Data flow, all of it pre-existing:

```
tools/slicer_src/slicer_1.14.java
  -> tools/gen_slices.py            (allowlist filter)
  -> mc_pack_converter/data/slices.json    (+19 records)
  -> mc_pack_converter/stages/slice.py     (unchanged)
  -> assets/minecraft/textures/mob_effect/<name>.png  x19
  -> contact sheet + output zip
```

### Generator: the `effect()` branch

`slicer_1.14.java` defines the helper as:

```java
private static OutputFile effect(final String path, final int x, final int y) {
    return gridSprite("assets/minecraft/textures/mob_effect/" + path + ".png",
                      x, y, 1, 1, 0, 198, 18, 18);
}
```

which reduces to the project's existing record shape:

- `effect(n,x,y)` → `assets/minecraft/textures/mob_effect/<n>.png`,
  box `[18x, 198 + 18y, 18, 18, 256, 256]`, `op: "crop"`

No reference rebase, unlike the particles work: `inventory.png` is 256×256 in
1.8.9 and in 1.13, so the slicer's `256,256` reference already matches the 1.8.9
canvas. Proportional scaling then handles the pack's 2× copy for free.

`SKIPPED_HELPERS` drops to `{"sweep": 0}`; `sweep()` stays unported (1.9+ texture,
needs the slicer's `SQUARE` post-op).

### The allowlist

A module-level set of the 19 effects vanilla 1.8.9 draws. Names outside it emit no
record and are counted in the generator's skip note.

```
speed  slowness  haste  mining_fatigue  strength  weakness  poison  regeneration
invisibility  hunger  jump_boost  nausea  night_vision  blindness  resistance
fire_resistance  water_breathing  wither  absorption
```

The eight excluded names, with the reason carried in a source comment beside the
set — it encodes a measurement, not something derivable from the slicer:

| excluded | why |
|---|---|
| `levitation`, `glowing`, `luck`, `unluck` | 1.9 additions in row-2 gaps that hold only vanilla guide marks in 1.8.9 (20 px) |
| `health_boost` | exists in 1.8.9 but is undrawn at `(7,2)` — same 20 px of guide marks |
| `slow_falling`, `conduit_power`, `dolphins_grace` | 1.13 additions at `(8,0)`–`(10,0)`, off the 1.8.9 art entirely (0 px) |

All eight fall back to vanilla, which is the correct outcome: the pack has no art
for them, and drawing it would be creating art.

### Error handling

Nothing new. Every path already exists in `slice.py`:

- no `inventory.png` in the pack → records skip on the existing `src.exists()` check
- a 1.8.9 pack that left one of the 19 undrawn → existing `_is_empty` guard, INFO
  finding, falls back to vanilla
- a corrupt or unreadable crop → existing per-sprite fail-soft WARNING

## Out of scope

- **A runtime near-empty guard in `slice.py`.** Considered and rejected above.
- **Later-version source packs.** A 1.9–1.12 pack would ship art in the four
  1.9 cells and the allowlist would discard it. That is consistent with the
  project's declared 1.8.9-only input scope (`docs/known-issues.md` §0), and
  widening it is a scoping decision, not part of this change.
- **`sweep.png`** — unchanged, still unported.
- **Deleting the now-dead effect strip from `inventory.png`.** After slicing, the
  strip is unread by 26.x, like the other dead atlases already left in place.

## Testing

Unit tests stay synthetic and fast; the real 65MB pack is verified by hand.

**Generator** (extend `tests/test_gen_slices.py`)
- a fixture Java snippet with `effect("regeneration", 7, 0)` yields output
  `assets/minecraft/textures/mob_effect/regeneration.png`,
  box `== [126, 198, 18, 18, 256, 256]`, `op == "crop"`
- `effect("levitation", 3, 2)` and `effect("slow_falling", 8, 0)` yield no record
- the generated `slices.json` contains exactly 19 `mob_effect/` records

**Slice stage** (extend `tests/test_slice.py`)
- a synthetic 256×256 atlas with a marked cell at `(2,1)` produces
  `mob_effect/jump_boost.png` carrying that cell's pixels
- the same atlas at 512×512 cuts the same cell — resolution independence

**Real-pack run** (manual)
- 19 `mob_effect/*.png` in the output, each with non-trivial opaque coverage
- no `mob_effect` sprite whose coverage is the 6.2% guide-mark signature
- the 89 existing tests stay green

## Success criteria

1. `pytest` green — 89 existing plus the new tests.
2. `slices.json` regenerates deterministically to 562 records, 19 of them
   `mob_effect`.
3. Real-pack conversion writes exactly 19 `textures/mob_effect/*.png`, all
   non-empty, none of them the five guide-mark cells.
4. `docs/known-issues.md` §2 is rewritten: the entry closes, and the corrected
   grid finding replaces the rearrangement theory so the wrong premise cannot be
   picked up again.
5. In-game on 26.1.2 + OptiFine: the pack's own effect icons appear in the
   inventory effect panel and the HUD. Requires deleting the old copy in
   `.minecraft/resourcepacks/`, restarting Minecraft, and confirming the
   `[conv 26.1.2 <MMDD-HHMM>]` build tag in the resource-pack list — OptiFine
   caches textures, and a stale copy makes every fix look like it did nothing.

## References

- `github.com/Mojang/slicer`, `1.14/Main.java` — vendored at
  `tools/slicer_src/slicer_1.14.java`. Authoritative source of the coordinates and
  of the cell → effect-name mapping used above.
- `github.com/InventivetalentDev/minecraft-assets` — version-pinned vanilla asset
  mirror. Source of the 1.8.9 grid measurement, and of the confirmation that
  `textures/mob_effect/<name>.png` is 18×18 and still current at 1.21.4. Fetch raw
  at `raw.githubusercontent.com/InventivetalentDev/minecraft-assets/<version>/assets/minecraft/...`
- `github.com/agentdid127/ResourcePackConverter` — cross-check. Its
  `InventoryConverter` shifts the effect *background*, not the icon grid; it does
  not extract `mob_effect` sprites at all.
