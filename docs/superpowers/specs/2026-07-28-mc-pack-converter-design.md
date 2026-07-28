# Minecraft Texture Pack Converter — Design (1.8.9 → 26.2)

**Date:** 2026-07-28
**Status:** Approved design, pre-implementation
**Proving-ground fixture:** `M8SON 1.8 PVP PACK` (a "Faithful 32x32 edit", `pack_format: 1`)

## Goal

Build a reusable CLI tool that converts a Minecraft **Java** 1.8.9-era resource
pack into one that works on **26.2**, correctly handling the things existing
converters (e.g. itsme64's) leave broken: fire, the crafting/HUD GUI, reorganized
entity textures (chest), and OptiFine custom sky. Start by fully converting the
M8SON pack (proving ground), then generalize.

**Target runtime:** OptiFine feature set. Custom sky is authored in OptiFine
format (`optifine/sky/world0/skyN.properties`), which is the lingua franca read
by OptiFine and, on 26.2, by Fabric sky mods (Skyboxify, Nuit). Vanilla has never
supported custom skies and never will — that is *why* vanilla-targeting updaters
drop them.

## Core Philosophy

**Fix and format — never create.** The tool never draws or invents art. Every
fix is a structural transform on pixels/files that already exist: rename, region
remap (cut/paste sub-rectangles), sheet slice, or validate. The pack's visual
identity is preserved byte-for-byte where possible and only *rearranged* where
the modern layout differs. Un-themed modern blocks fall back to vanilla textures
(the normal 26.2 look) — that is acceptable and is **not** the purple/black
missing-texture placeholder.

## What the M8SON pack actually contains (inventory)

- **Pure texture + sound + OptiFine pack** — zero model/blockstate `.json` files.
  This dramatically lowers null-texture risk (no custom references to dangle).
- Textures: `blocks/` (782), `items/` (464), `gui/` (64), `entity/` (294),
  `environment/`, `particle/`.
- OptiFine features in use (**only these**): CTM (glass, 19 configs), custom sky
  (`sky1..8.properties` + PNGs), colormaps, custom lightmap, `color.properties`.
  No CIT, no emissive, no random-entity, no CEM.
- Sounds: 513 `.ogg` at 1.8.9 paths, **no `sounds.json`**.
- Junk to strip: 2,536 `*:Zone.Identifier`, `Thumbs.db`, `.DS_Store`,
  `desktop.ini`, `*.png~`.
- Known pre-existing broken ref: `sky4.properties` references `starfield01.png`
  but the folder ships `starfield03.png`.

## Architecture

A CLI tool running an **ordered pipeline of isolated stages** over a working
copy. Each stage is an independent, testable unit taking a shared
`ConversionContext` (working-dir path + `findings` accumulator), mutating the
file tree and appending findings. Stages share only the context and the
filesystem — never each other's internals. All large lookup tables live as
**JSON data files** separate from code, so version bumps are data edits.

**Approach chosen:** rule-driven pipeline with data-driven mapping tables
(over: a monolithic fix-it script, or wrapping an existing black-box converter).
It is the only option that is testable per-stage, stays maintainable across MC
versions, and can emit the transparency reports that make it better than itsme's.

**Stack:** Python (stdlib) + Pillow for image work. CLI-driven.

## Pipeline stages (in order)

1. **ingest** — accept `.zip` or folder; extract to temp working dir;
   sanity-check it is a 1.8.9-era pack (`pack_format: 1`, has `blocks/`/`mcpatcher/`).
2. **clean** — strip junk (`*:Zone.Identifier`, `Thumbs.db`, `.DS_Store`,
   `desktop.ini`, `*.png~`, stray `.db`/`.ini`). Log counts.
3. **restructure** — `textures/blocks → block`, `textures/items → item`,
   `mcpatcher/ → optifine/`.
4. **flatten-rename** — apply the Flattening rename map (blocks/items/entities),
   incl. `fire_layer_0 → fire_0`. Data-driven from `flattening.json`.
5. **atlas-remap** — pixel-level cut/paste for textures whose *internal layout*
   changed (chest, and any similar entity/model textures). Crop source
   sub-regions and paste into modern coordinates. Data-driven from
   `region_remap.json` (source rect → dest rect per texture). Content that
   exists only in the modern layout falls back to vanilla — never purple/black.
6. **optifine-translate** —
   - *sky:* keep OptiFine format, fix broken `source=` refs, verify `world0` paths.
   - *ctm:* translate legacy `tiles=`/numeric-ID matching → modern `matchBlocks=`
     via a block-name map (`ctm_blocks.json`).
   - *colormap / color.properties / lightmap:* copy, drop deprecated keys.
7. **gui-sprite-slice** — slice `widgets.png` / `icons.png` into modern
   `gui/sprites/*` files per `gui_sprites.json`, emitting 9-slice `.mcmeta`
   where modern stretches. Fixes crafting/HUD breakage.
8. **sounds** — remap 1.8.9 sound paths → modern paths via `sound_map.json`
   and/or generate `sounds.json`. Match-or-beat itsme's result.
9. **pack.mcmeta** — bump `pack_format` to the pinned 26.2 value
   (`pack_format.json`), preserve description.
10. **validate** — null-texture safety check: animated `.mcmeta` frame/dimension
    mismatches, broken OptiFine `source=` refs, missing gui sprites, corrupt/
    zero-byte PNGs.
11. **report + package** — write both reports; repackage as `.zip`.

## Code layout

```
mc_pack_converter/
  cli.py            # arg parsing + orchestration
  pipeline.py       # ordered stage runner + ConversionContext
  imaging.py        # Pillow helpers: slice sheet, read dims, validate PNG, region remap
  report.py         # collects findings -> renders the two reports
  stages/           # one module per stage (ingest, clean, ..., validate)
  data/             # mapping tables (below)
tests/
  fixtures/         # tiny synthetic packs + the M8SON pack (golden)
```

## Data files (the maintainable core)

- `flattening.json` — old→new file renames (block/item/entity).
- `region_remap.json` — per-texture source rect → dest rect (chest-class remaps).
- `ctm_blocks.json` — legacy CTM folder/ID → modern `matchBlocks` names.
- `gui_sprites.json` — slice specs: source sheet → `{name, x, y, w, h, ninepatch?}`.
- `sound_map.json` — 1.8.9 sound path → modern path.
- `pack_format.json` — target-version → `pack_format` number.

Built and verified during implementation against documented 1.8.9-vs-26.2 texture
templates and 26.2 asset references.

## Reports (the "better than itsme's" differentiator)

- **Conversion report** (`conversion-report.md`) — per stage: files cleaned,
  renamed, translated, dropped, skipped. Full audit trail.
- **Null-texture safety report** — `0 risks`, or an itemized list (bad mcmeta
  dims, dangling OptiFine `source=`, missing gui sprites, corrupt PNGs). Scope is
  *only what the pack ships* — it does **not** require theming every vanilla asset.

## Error handling

- **Fail-soft per file:** a bad/unexpected file logs a warning and is recorded;
  it never aborts the run.
- **Hard-fail only** on: not a valid pack, or unwritable output.
- **Idempotency:** if `pack_format` is already modern, warn
  ("looks already converted") instead of double-processing.

## Testing (TDD)

- **Per-stage unit tests** with tiny synthetic pack fixtures.
- **Golden end-to-end test** on the M8SON pack: assert `fire_0.png` exists,
  `gui/sprites/` populated, sky under `optifine/sky/world0/`, sounds mapped,
  and **zero null-texture warnings**.
- **Data-table tests:** no duplicate keys, targets well-formed.
- **Region-remap verification:** assert output dimensions + checksum that a known
  region landed at expected coords. Final visual correctness (does the chest
  *look* right in-game) is a **manual spot-check** noted in the plan.

## CLI

```
mc-pack-converter convert <pack.zip|folder> [-o OUT] [--target 26.2] [--report-only]
```

`--report-only` runs ingest→validate without writing output (dry-run audit).

## Out of scope (v1)

- Bedrock edition.
- OptiFine features the pack doesn't use (CIT, emissive, random entities, CEM).
- Generating/drawing any new artwork.
- Full "diff against every vanilla asset" completeness list (explicitly rejected
  as over-scoped; the null-texture safety check covers the real concern).
