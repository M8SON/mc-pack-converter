# Chest Texture Research — 1.8.9 → 26.2

**Date:** 2026-07-28
**Method:** Empirical pixel comparison of Mojang's own vanilla chest textures
(1.8.9 vs 1.21.4) pulled from the `InventivetalentDev/minecraft-assets`
version-pinned mirror. No coordinates were guessed.

## Verified findings

### Single chests — NO change, NO remap needed
`normal.png`, `trapped.png`, `ender.png`, `christmas.png` (all 64×64).

- 1.8.9 `normal.png` vs 1.21.4 `normal.png`: **alpha masks byte-identical, 0
  differing pixels**; opaque bounding box identical `(0,0,56,43)`.
- Conclusion: the single-chest UV layout is unchanged from 1.8.9 through modern.
- **Action: none.** The converter copies these files unchanged to
  `entity/chest/`, and they render correctly on 26.2. `region_remap.json`
  correctly has no entry for them.
- Implication: if a user reports single chests "messed up," it was likely the
  *other* converter mangling them (or the missing double-chest files below).
  Our pipeline leaves singles correct.

### Double chests — split + UV rearrangement (NOT a simple crop)
1.8.9 ships `normal_double.png` (128×64). Modern (1.15+) replaced it with
`normal_left.png` + `normal_right.png` (64×64 each); `normal_double.png` no
longer exists in vanilla.

Empirical checks (alpha masks):
- `normal_left` == `normal_double[:, 0:64]`? **No** (874 px differ).
- `normal_right` == `normal_double[:, 64:128]`? **No** (1406 px differ).
- `normal_left`/`normal_right` == single-chest layout? **No** (310 px differ each).

Conclusion: the double-chest faces were re-unwrapped into a new topology when
split. A correct conversion must (a) produce two output files from one source,
and (b) remap per-face UV rectangles — it is not a half-crop and not the
single-chest layout.

Affected doubles in the M8SON pack: `normal_double.png`, `trapped_double.png`,
`christmas_double.png` (all 128×64).

## Why this is not yet implemented

Two blockers, both deliberate under the project's "verify, don't guess" rule:

1. **Mechanism gap:** the current `atlas_remap` stage + `region_remap.json`
   schema writes back to the *same* file (one in → one out). The double-chest
   fix is one source → *two* output files, which needs a small schema/stage
   extension (a "split" output list).
2. **Coordinate certainty:** the per-face old→new rectangle mapping cannot be
   pixel-verified without rendering the chest model in-game. Mojang's `slicer`
   tool does NOT encode it (chests predate the slicer's scope — the 26.2 slicer
   handles beds/signs/etc., not chests). Shipping guessed rects risks making
   double chests look *worse*, which violates the project philosophy.

## Recommended path (calibration loop)

1. User loads the converted pack in 26.2 + OptiFine and reports what chests look
   like — **single vs double separately**.
2. If singles are correct (expected) and only doubles are wrong: implement the
   double-split by empirically matching each UV face region between vanilla
   `normal_double.png` and vanilla `normal_left/right.png` (the vanilla art is
   identical wood, so per-face template-matching yields exact source→dest
   rects), then apply the same rects to the pack's `*_double.png`. Verify the
   result in-game before committing the mapping.
3. Add a one-source→many-files "split" capability to the atlas stage to emit
   `normal_left.png`/`normal_right.png` from `normal_double.png`.

## Reference textures used
- `1.8.9` vanilla: `entity/chest/normal.png` (64×64), `normal_double.png` (128×64)
- `1.21.4` vanilla: `entity/chest/normal.png`, `normal_left.png`,
  `normal_right.png` (all 64×64)
- Source mirror: `raw.githubusercontent.com/InventivetalentDev/minecraft-assets/<version>/assets/minecraft/textures/entity/chest/`
