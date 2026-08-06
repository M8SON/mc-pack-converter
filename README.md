# mc-pack-converter

[![tests](https://github.com/M8SON/mc-pack-converter/actions/workflows/tests.yml/badge.svg)](https://github.com/M8SON/mc-pack-converter/actions/workflows/tests.yml)

Converts Minecraft Java 1.8.9 resource packs to modern versions (26.1, 26.1.2, 26.2).

## Install

Requires Python 3.11+.

```
pip install .
```

The only runtime dependency is [Pillow](https://python-pillow.org/).

## Quickstart

```
mc-pack-converter convert MyPack.zip
```

This is the real output of a real run, against a real 1.8.9 pack, from an empty
working directory:

```
[1/20] ingest
[2/20] clean
[3/20] repair_mcmeta
[4/20] lowercase_paths
[5/20] restructure
[6/20] flatten_rename
[7/20] model_refs
[8/20] atlas_remap
[9/20] chest
[10/20] gui_remap
[11/20] legacy
[12/20] drop
[13/20] conformance
[14/20] optifine
[15/20] slice
[16/20] derive_sprites
[17/20] prune_atlases
[18/20] sounds
[19/20] pack_meta
[20/20] validate
contact sheet: MyPack-26.2-slices.png (119 sprites)

0 errors, 5 warnings, 408 notes
wrote MyPack-26.2.zip
report: MyPack-26.2-report.md
null-textures: MyPack-26.2-null-textures.md
```

Four files land in the working directory:

- `MyPack-26.2.zip` — the converted pack
- `MyPack-26.2-report.md` — every finding, grouped by stage
- `MyPack-26.2-null-textures.md` — null-texture safety report
- `MyPack-26.2-slices.png` — a contact sheet of the GUI sprites cut out of old
  atlases, for eyeballing. Only produced when the pack has atlases that needed
  slicing.

`source` can be a `.zip` or an unpacked folder. Useful flags:

```
usage: mc-pack-converter convert [-h] [-o OUT] [--target {26.1,26.1.2,26.2}]
                                 [--report-only] [-v]
                                 source

positional arguments:
  source                the 1.8.9 pack to convert: a .zip or an unpacked
                        folder

options:
  -h, --help            show this help message and exit
  -o OUT, --out OUT     output zip (default: <pack>-<target>.zip in the
                        current directory)
  --target {26.1,26.1.2,26.2}
                        Minecraft version to convert to (default: 26.2)
  --report-only         analyse the pack and write reports without producing a
                        converted pack
  -v, --verbose         also print the full reports to the terminal
```

A pack that doesn't exist fails cleanly, exit status 1, no traceback:

```
$ mc-pack-converter convert /tmp/does-not-exist.zip
no such pack: /tmp/does-not-exist.zip
```

## What it does

The converter runs 20 stages in a fixed order:

1. **ingest** — unzips (or copies) the pack into a working directory, finds the
   real pack root, and guards against unsafe zip entries.
2. **clean** — removes OS and editor junk files (`Thumbs.db`, `.DS_Store`,
   macOS resource forks, stray backups) that would otherwise ship as corrupt
   textures.
3. **repair_mcmeta** — repairs `.mcmeta` files with common syntax mistakes
   (trailing commas, single quotes, wrong value types) where possible, and
   drops the texture with it where it isn't recoverable, because an
   unparseable `.mcmeta` makes Minecraft drop the whole texture.
4. **lowercase_paths** — lowercases resource paths outside the OptiFine and
   MCPatcher trees, because Minecraft silently refuses to load any path
   containing a capital letter or a space.
5. **restructure** — renames the top-level `textures/blocks`, `textures/items`,
   and `mcpatcher` folders to their modern names.
6. **flatten_rename** — applies the several hundred individual 1.8.9-to-modern
   filename renames, preferring the 1.8.9 name when a pack ships both, since
   that's the file 1.8.9 actually rendered.
7. **model_refs** — rewrites texture paths inside custom model JSON, and bare
   model names inside blockstates, so they still resolve after the previous
   two stages moved the files.
8. **atlas_remap** — remaps regions of legacy combined-atlas textures into the
   layout modern versions expect.
9. **chest** — re-maps 1.8.9 chest textures onto the modern chest model's UV
   layout (re-unwrapped in 1.15), preserving the pack's own art instead of
   discarding it.
10. **gui_remap** — shifts GUI elements Mojang repositioned between 1.8.9 and
    modern (currently the survival-inventory crafting grid), healing the
    vacated area with the pack's own sampled background colour.
11. **legacy** — grayscales pre-tinted water textures so modern's biome tint
    applies correctly, and splits the compass/clock animation strips into the
    individual frame files modern items expect.
12. **drop** — deletes a small, fixed list of textures whose 1.8.9 art cannot
    survive the version jump (the 1.11 horse rework, the 1.14 villager-GUI
    redesign), so modern vanilla renders in their place.
13. **conformance** — measures, per pack, whether specific screens (the
    enchanting table, the creative-inventory tabs) still have usable art
    against the modern layout, and drops only the ones that measurably don't.
14. **optifine** — translates OptiFine/MCPatcher extensions — connected
    textures, custom skies, colour properties — so they keep working,
    including inferring `matchBlocks` for connected-texture folders that
    relied on old MCPatcher's name-based matching, and drops the one known-bad
    colour override (a lily pad tint that renders invisible) so that block
    falls back to vanilla while every other custom colour passes through
    untouched.
15. **slice** — runs Mojang's own official slicer definitions to cut legacy
    combined atlases (widgets, icons, particles, GUI containers) into the
    modern one-sprite-per-file layout.
16. **derive_sprites** — composes the handful of modern sprites the slicer
    cannot correctly cut from 1.8.9 source, out of the pack's own neighbouring
    art.
17. **prune_atlases** — deletes the old combined-atlas source files once
    they're sliced, since modern Minecraft no longer reads them.
18. **sounds** — renames sound files that moved between the 1.8.9 and modern
    sound-event layout.
19. **pack_meta** — rewrites `pack.mcmeta` to the modern `min_format`/
    `max_format` schema and tags the description with the target version and
    build time.
20. **validate** — checks the finished output for in-game symptoms the
    earlier stages can't see themselves causing: null-texture model
    references, magenta-cube blockstate references, squashed GUI canvases,
    and un-animated texture strips.

## Limitations

The only supported input is a 1.8.9-era pack (`pack_format: 1`). Converting a
later-version source pack is out of scope: every coordinate table in this
project is derived from the 1.8.9 layout, and applying it to a newer pack can
mis-map textures rather than merely convert them worse. See
[`docs/known-issues.md`](docs/known-issues.md), §0.

Three accepted limitations, also recorded in
[`docs/known-issues.md`](docs/known-issues.md):

- **The enchanting-table GUI** (§16): kept only when the pack's own art draws
  two item slots where 1.8.9 puts them, measured per pack by the `conformance`
  stage. 1.8 added the lapis slot, so 1.7-era art with a single slot renders
  with modern Minecraft's two functional slots drawn on top of it. The check is
  deliberately conservative, and this is the converter's most visible decision:
  **13 of the 142 packs in a 173-pack test corpus keep their enchanting table —
  the other 91% fall back to vanilla's.** The same stage drops
  creative-inventory tab art that measures as mostly transparent (unfinished
  placeholders), on the same per-pack basis.
- **Custom mob-effect icons** (§2): icons for the 19 potion effects that
  existed in 1.8.9 are recovered from the pack's own art. 8 icons have no
  1.8.9 art to recover from and fall back to vanilla: `levitation`, `glowing`,
  `luck`, and `unluck` are 1.9 additions; `slow_falling`, `conduit_power`, and
  `dolphins_grace` are 1.13 additions; and `health_boost`, though a 1.8.9
  effect, was never drawn in the icon strip.
- **The villager trading GUI** (§5): always dropped to vanilla. 1.14 redesigned
  its canvas with a trade-list panel that has no 1.8.9 counterpart, so keeping
  the pack's texture would render squashed and with misplaced slots.

For the full list of known issues, fixed defects, and how each was measured,
see [`docs/known-issues.md`](docs/known-issues.md).

## Credits

The conversion pipeline was validated against two authoritative references:

- [Mojang's own resource-pack slicer](https://github.com/Mojang/slicer),
  vendored under `tools/slicer_src/` and used to regenerate the GUI-sprite
  crop table.
- [agentdid127/ResourcePackConverter](https://github.com/agentdid127/ResourcePackConverter),
  an open-source converter whose chest-remap logic (`ChestConverter1_15`) this
  project ports, along with its water-grayscale (`WaterConverter1_13`) and
  compass/clock frame-splitting (`CompassConverter1_9`) logic.
