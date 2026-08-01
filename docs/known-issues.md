# Known Issues

Open defects and unrecovered art, with enough detail to resume cold.
Verified findings only — each entry says how it was measured.

---

## 0. Project scope: 1.8.9-era input only

**Status:** deliberate scope, set 2026-07-29 · not a defect

**Supported input is a 1.8.9-era pack (`pack_format: 1`).** Output targets are the
modern versions in `mc_pack_converter/data/pack_format.json` (26.1.2 = 84,
26.2 = 88). Converting a *later-version* source pack is **future work**, to be
scoped when it is actually wanted. Scope and features expand incrementally.

Every version-specific coordinate table in this project is derived from the
1.8.9 layout. A newer source pack does not merely convert worse — it can convert
*wrongly*, because a table that is correct for 1.8.9 may silently mis-map a
later layout. One such case is already known and guarded:

- **1.13+ input, `particles.png`.** A 1.8.9 atlas is 128×128 with 8px cells; a
  1.13+ atlas is 256×256 **with the same 8px cells** — 1.13 grew the canvas
  rather than scaling up. Records referenced to `128,128` therefore read a 1.13
  atlas as a 2× 1.8.9 atlas and cut 16px cells, producing wrong-rectangle
  sprites that then override vanilla. `stages/slice.py` skips `particles.png`
  records with a WARNING when the source declares `pack_format >= 4`, so they
  fall back to vanilla instead. 1.9–1.12 inputs are unaffected — they still ship
  the 128×128 atlas. The paintings atlas and `entity/explosion.png` are
  byte-identical between 1.8.9 and 1.13.2 at the same canvas size and are **not**
  gated.

**How to handle a future finding of this shape:** add a defensive gate plus an
entry here. Do **not** build a new conversion path, and do not let a review
finding quietly widen the supported-input matrix — that is a scoping decision,
not a bug fix.

---

## 1. Fully-transparent sprites override vanilla (invisible in-game)

**Status:** FIXED 2026-07-29 — `stages/slice.py` skips crops with no visible
pixels. Kept here for the record; the reproduce block below now reports 0.
**Fix lives in:** `docs/superpowers/specs/2026-07-29-particles-slicer-design.md`
**Affects:** `M8SON-converted-26.1.2-FRESH.zip` (2026-07-28 21:50) and every earlier build

`stages/slice.py` cropped a region from a 1.8.9 atlas and wrote it unconditionally.
For any modern GUI element whose region was blank in a 1.8.9 atlas, that wrote a
fully-transparent PNG — which **overrode** vanilla rather than falling back to it,
so the element rendered invisible.

Measured on a real run of `master` @ `623cc45`: **23 of 153** produced
`gui/sprites` are fully transparent.

| sprite | in-game effect |
|---|---|
| `hud/crosshair_attack_indicator_{background,full,progress}.png` | **attack indicator invisible (PVP-relevant)** |
| `hud/hotbar_attack_indicator_{background,progress}.png` | same, hotbar variant |
| `hud/hotbar_offhand_{left,right}.png` | offhand slot backdrop invisible |
| `hud/effect_background{,_ambient}.png` | potion-effect HUD backdrop invisible |
| `hud/heart/frozen_{full,half,hardcore_full,hardcore_half}{,_blinking}.png` | freezing hearts invisible (8 files) |
| `container/horse/{saddle,llama_armor}_slot.png` | slot markers invisible |
| `container/brewing_stand/fuel_length.png` | fuel gauge invisible |
| `icon/draft_report.png`, `statistics/item_{dropped,picked_up}.png` | minor UI icons invisible |

**Fix:** skip a crop whose alpha bbox is `None`, log it INFO, let vanilla show
through. Applies to all slice records, not just new ones.

**Reproduce:** this must be scoped to sprites the slicer itself produced —
cross-referenced against `mc_pack_converter/data/slices.json`. The pack ships
23 fully-transparent textures of its own on purpose (19 clear-glass CTM tiles,
a transparent `environment/clouds.png`, blank
`redstone_dust_{cross,line}_overlay` and `leather_chestplate_overlay`) — those
are the source pack's intent, not slicer output, and an unscoped count will
wrongly include them.

```bash
.venv/bin/python -m mc_pack_converter.cli convert "../M8SON 1.8 PVP PACK" \
  -o /tmp/out.zip --target 26.1.2
.venv/bin/python - <<'EOF'
import json, zipfile
from io import BytesIO
from PIL import Image
with zipfile.ZipFile("/tmp/out.zip") as zf:
    slice_outs = {r["output"] for r in
                  json.load(open("mc_pack_converter/data/slices.json"))}
    empty = []
    for n in zf.namelist():
        if n not in slice_outs:
            continue
        with Image.open(BytesIO(zf.read(n))) as im:
            if im.convert("RGBA").getchannel("A").getbbox() is None:
                empty.append(n)
    print("transparent slicer-produced sprites:", len(empty), empty[:5])
EOF
```

---

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

One consequence is undocumented until now: the converter cannot tell "the pack
redrew the effect strip" from "the pack shipped vanilla 1.8.9 `inventory.png`
untouched", so a pack of the latter kind now gets 1.8.9-era icons overriding
modern vanilla's 1.13 redraw of those same 19 cells — consistent with this
project's existing stance on porting `entity/explosion.png` (0% custom in
M8SON, ported anyway for reusability), but worth calling out here since the
effect art is one of the few atlases that visibly changed between versions.

---

## 3. `effect_background_small.png` slices the effect-icon grid, not a background

**Status:** FIXED 2026-07-31 — `stages/derive_sprites.py` composes the sprite
from the pack's own effect panel and overwrites the slicer's output.
**Affected:** every build up to and including `[conv 26.1.2 0731-1445]` —
pre-existing, exposed by the mob-effect-icons work proving what lives at
`y=198`.

`tools/slicer_src/slicer_1.20.2.java` emits
`assets/minecraft/textures/gui/sprites/container/inventory/effect_background_small.png`
from `Box(0, 198, 32, 32, 256, 256)` — **the exact region this branch proves is
the 1.8.9 effect-icon grid** (see §2 above; the grid starts at `(0,198)` and is
stable 1.8.9→1.13). Verified on a real conversion of the M8SON proving-ground
pack: the produced sprite is **64×64, 40% opaque**, and is visibly four potion
icons (`speed`, `slowness`, `invisibility`, `hunger`) stitched together — not a
background at all — overriding vanilla's inventory effect-list background.

This is the same defect family as §1 (a slice record whose region no longer
means what a modern sprite name expects) but with the opposite symptom: not
empty, but wrong content. `stages/slice.py`'s `_is_empty` guard tests whether
the alpha bbox is `None`; a 40%-opaque crop has a non-`None` bbox, so the guard
cannot catch it.

**The fix.** A gate would have dropped the sprite to vanilla. Instead, the new
`derive_sprites` stage *composes* it: 1.8.9 has one effect panel — the 120×32
rounded box at `(0,166)`, which `effect_background_large` already cuts correctly
— and the 32×32 small variant is a later Mojang addition with no 1.8.9 art. Its
left and right 16 ref-columns joined give a closed 32×32 box carrying the pack's
own border art, corner notches included. Every pixel is the pack's own, so this
stays inside *fix and format, never create art*.

The stage runs after `slice` and overwrites it, rather than gating the record.
That keeps `stages/slice.py` a generic executor of Mojang's records, with the
version-specific knowledge in `data/derived_sprites.json` alongside the rest of
this project's lookup data. Adding an entry there is how the next sprite of this
shape gets handled.

**Reproduce (now reports a closed panel, not icons):**

```bash
.venv/bin/python -m mc_pack_converter.cli convert "../M8SON 1.8 PVP PACK" \
  -o /tmp/out.zip --target 26.1.2
.venv/bin/python - <<'EOF'
import zipfile
from io import BytesIO
from PIL import Image
with zipfile.ZipFile("/tmp/out.zip") as zf:
    data = zf.read(
        "assets/minecraft/textures/gui/sprites/container/inventory/"
        "effect_background_small.png")
    with Image.open(BytesIO(data)) as im:
        im = im.convert("RGBA")
        alpha = im.getchannel("A")
        n = im.width * im.height
        opaque_frac = sum(alpha.getdata()) / 255 / n
        print("size:", im.size, "mean alpha:", round(opaque_frac * 100, 1), "%")
EOF
```

---

## 4. The anvil and enchanting-table GUIs were dropped on a wrong measurement

**Status:** RESOLVED 2026-07-31, and the two split apart. **Anvil:** undropped —
the recorded reason was false and its art is correct. **Enchanting table:**
stays dropped, but for a different and real reason found by in-game testing
(see *The enchanting table is a separate problem* below).
**Guarded by:** `tests/test_drop.py::test_anvil_is_not_dropped` and
`::test_enchanting_table_is_dropped`

`textures/gui/container/anvil.png` and `enchanting_table.png` were dropped to
vanilla on the recorded theory that their **slot layout had drifted** between
1.8.9 and modern, so a 1.8.9 background would misalign with modern's functional
slots. Measured against the version-pinned vanilla mirror, that is false:

| panel | 1.8.9 vs modern vanilla, over the 176×166 GUI |
|---|---|
| `anvil.png` | **0.1%** of pixels differ (only `y=1..28`, the text-field strip) |
| `enchanting_table.png` | **0.2%** of pixels differ (one 12×12 box at `(37,49)`) |

The slots did not move. What *did* change is that 1.20.2 sliced the dynamic
pieces out into `gui/sprites/...`, leaving modern vanilla's copy of those
regions **empty** — which is why a naive old-vs-new diff of the sliced regions
reads 100% and looks like a redesign. The 1.20.2 slicer's read boxes land
exactly on the art a 1.8.9 pack already ships, because that layout was stable
from 1.8.9 through 1.19.

Dropping them therefore discarded custom art for nothing. In the M8SON pack the
two panels are **87%** and **37%** custom against vanilla 1.8.9. Undropping
recovers, verified on a real conversion:

- both GUI panels
- `anvil/text_field`, `anvil/text_field_disabled`, `anvil/error`
- `enchanting_table/enchantment_slot{,_highlighted,_disabled}`

### The enchanting table is a separate problem

Undropping both shipped a visibly wrong enchanting screen, reported from
in-game testing of build `[conv 26.1.2 0731-1539]`. The measurement above is
still correct — the *vanilla* panel did not drift — but it says nothing about
whether **the pack's own art** matches the 1.8.9 layout. It does not:

| | item slots | bar level-number caps |
|---|---|---|
| vanilla 1.8.9 | **2** (second holds the lapis glyph) | present |
| vanilla modern | **2** (both plain) | present |
| M8SON pack | **1**, and offset from either | **absent** |

Lapis was added to enchanting in 1.8, so a one-slot enchanting GUI is **1.7-era
art**. The pack ships it under a 1.8.9 pack format, but it never matched the
1.8.9 layout, and would have rendered wrong in 1.8.9 too. That makes it a
source-pack limitation like the creative-inventory placeholders, not a
conversion defect — so it goes back on the drop list, under its own rationale.

The anvil is unaffected: the pack's anvil is a pixel-exact structural match to
both eras (hammer, text bar, three slots, arrow and grid all in the same
places), and it stays undropped. Its recovered sprites — `text_field`,
`text_field_disabled`, `error` — are all exactly 2× vanilla's dimensions with
semantically matching content.

`enchanting_table/level_1..3{,_disabled}` never mattered here: the pack has no
content below `y=223`, so the empty-region guard in `stages/slice.py` was
already leaving them to vanilla.

**Two lessons worth keeping:**

1. Diffing a *sliced* region against modern vanilla compares the pack's art to
   an empty rectangle — 1.20.2 vacated those regions. Compare against the
   pre-slice version, or against the sprite the slicer produces.
2. "The vanilla layout didn't change" does **not** imply "the pack's art fits
   it." Check the pack against its *own* era before undropping something. A
   symmetric edge-difference metric hides this: the pack scored 6.6% against
   modern and 6.7% against 1.8.9, which looks like pure styling until you zoom
   in and count slots.

---

## 5. The villager GUI is squashed and misplaced

**Status:** FIXED 2026-07-31 — `textures/gui/container/villager.png` added to
`data/drop_list.json`.
**Affected:** every build up to and including `[conv 26.1.2 0731-1539]`.
Pre-existing, not a regression; found by in-game testing.
**Guarded by:** `tests/test_drop.py::test_villager_gui_is_dropped`

`villager.png` is the one GUI whose **reference canvas** changed between 1.8.9
and modern:

| | content | canvas |
|---|---|---|
| 1.8.9 | 240×166 | 256×256 |
| modern | 276×166 | **512×256** |

The filename is identical in both eras, nothing renames it, and no slice record
reads it — the records read `villager2.png`, which a 1.8.9 pack does not ship,
so all ten skip. The pack's 1.8.9 file therefore passes straight through, and
modern samples it at scale `(texW/512, texH/256)` = **(1.0, 2.0)** for a 512×512
pack texture: vertically squashed, slots misplaced, GUI overflowing its own
bounds.

There is also no remap available even in principle. 1.14's trading redesign
added a **trade-list panel on the left** with no 1.8.9 counterpart, and shifted
the trade slots and inventory grid right to make room. Reconstructing the panel
would be creating art.

**The general check this suggests:** every other GUI a 1.8.9 pack ships keeps a
256×256 reference, so `villager.png` is currently the only instance. A
`validate`-stage check comparing a shipped GUI's canvas aspect against the
reference the slice table expects would catch the next one automatically. Not
built — worth doing if a third case appears.

---

## 6. Pack intake rejected 14 of 173 real packs

**Status:** FIXED 2026-07-31 — **170 of 170** in-scope corpus packs now convert,
zero crashes, zero stage crashes.
**Found by:** running the whole 173-pack corpus through the converter. None of
this was reachable from the single proving-ground pack.

Every crash was in intake; nothing in the conversion logic itself ever crashed.

### `pack.mcmeta` is parsed more strictly than Minecraft parses it (12 packs)

Minecraft uses GSON, which is lenient. `json.loads` is not. Three malformations
occur in the wild, all inside the decorative `description` string:

| malformation | packs | example |
|---|---|---|
| UTF-8 BOM (Windows editors) | 5 | — |
| backslash before a non-escape character | 5 | `"§f\Made by: §6§o\@cellsaver"`, `"§b\ [by Gosu]"` |
| raw control character in a string | 2 | a literal CRLF; the `\x15` bytes of old colour codes |

`mc_pack_converter/mcmeta.py` now reads the file with `utf-8-sig` and, only if
strict parsing fails, re-parses through a sanitiser that rewrites what appears
**inside string literals** — dropping a stray backslash, escaping a raw control
character. A structurally broken file still raises; leniency covers known
sloppiness, not arbitrary garbage.

Three call sites read `pack.mcmeta` and they failed differently. The third is
the one worth remembering:

| site | symptom |
|---|---|
| `stages/ingest.py` | `FatalConversionError` — pack unconvertible |
| `stages/pack_meta.py` | would crash next, once ingest was fixed |
| `stages/slice.py` `_pack_format` | **silent.** It catches everything and returns `None`, meaning "not gated" — so a malformed file turned a 1.13+ pack into an ungated one and its `particles.png` would be mis-cut into wrong-rectangle sprites overriding vanilla: the exact failure §0 exists to prevent, reached by a route nobody was watching. |

A fail-open guard is only as good as its ability to read its input. When adding
one, check what makes the *read* fail, not just what makes the value wrong.

### A directory stored as a file inside the zip (2 packs)

`bPantone` and `#Pvpmen` store `assets/minecraft/textures/models/armor` with no
trailing slash, alongside `.../armor/iron_layer_1.png`. `extractall` writes the
first as a zero-length **file**, then dies with `NotADirectoryError` creating
anything inside it. `_dirs_stored_as_files` now skips any entry that another
entry treats as a directory.

### The `validate` stage crashed on OptiFine `.properties` (8 packs)

`read_text()` raised `UnicodeDecodeError` on ISO-8859-1 files and on macOS
AppleDouble `._*` sidecars, which are binary resource forks that match
`*.properties`. `run_pipeline` caught it, so **validation was silently skipped
for those packs and they reported clean.** `read_properties_text` falls back to
latin-1 (which decodes any byte sequence) and `iter_properties` skips `._*`.
Both are now used by every reader in `optifine.py` and `validate.py`.

---

## 7. Connected textures were silently lost by 38% of packs

**Status:** FIXED 2026-07-31 — `data/ctm_blocks.json` went from 19 to 327
mappings, generated by `tools/gen_ctm_blocks.py`.
**Found by:** the 173-pack corpus. The proving-ground pack showed this as a
*single* warning (`glass_gray`), which read as one dormant folder rather than a
systemic gap.

Old MCPatcher inferred a CTM folder's target block from the folder *name*.
Modern OptiFine does not, so the converter must write a `matchBlocks=` line —
and a folder it cannot map keeps its connected-texture behaviour only in name.
`stages/optifine.py` leaves it unchanged and warns.

Pack authors name those folders every which way. The corpus produced **161
distinct spellings for about 40 blocks**: `glass gray`, `glass_gray`,
`glass/Grey Glass`, `Glass/Light Grey Glass`, `ore coal`, `ore/ore_coal`,
`wood spruce ends`, `wood_ends/wood_spruce`.

| | before | after |
|---|---|---|
| CTM warnings | 1562 | **53** (97% resolved) |
| distinct unmapped names | 161 | 8 |
| packs affected | 65 of 170 | 8 |

Keys are normalised — lowercased, `_ - /` collapsed to single spaces — at both
generation and lookup, and the leaf path component is tried before the whole
relative path so `hardened_clay/stained/hardened_clay_black` resolves.

**Every emitted block id is validated at generation time** against the real
1.21.4 block list (1099 ids, from the vanilla mirror's `blockstates/`). An id
that is not a real block is a hard error: a wrong mapping is worse than a
missing one, because it points connected textures at the wrong block silently,
where a missing one at least warns.

**The `wools-*` folders were resolved on 2026-08-01** by a second lookup key.
Those folders hold several colours at once (`wools-b-w` is black-through-white),
so no folder name can identify one block — but the PROPERTIES FILENAME can:
terrain.png-era packs name them `cloth_0.properties` … `cloth_15.properties`,
where `cloth_N` is the pre-flattening wool data value. Old MCPatcher inferred
the target from exactly that filename when a file carried no `matchBlocks`, so
this restores behaviour the pack really had. The filename is tried **last**,
after both folder lookups, so it can only add resolutions and never change one
that already worked.

The `cloth_N` mapping was confirmed without any image comparison: in every pack
using them, the grouping folder's abbreviation matches the colours the mapping
predicts — `wools-b-w` holds cloth 0/7/8/15 (white, gray, silver, black),
`wools-r-g-b-v` holds 10/11/13/14 (purple, blue, green, red), and so on. A
colour-matching check was tried first and gave 20/32; it was the check that was
unreliable, not the mapping — CTM tiles are mostly border pixels.

That leaves **9 warnings**, all on the table's `_unmapped` list with a reason:
`default` (not a block), `wool` (all 16 colours at once), and `leaves fancy` /
`leaves fast` (two folders for the same blocks, which would fight over the same
`matchBlocks`). A test asserts they keep warning rather than silently passing.

**Two lessons from getting this wrong first:**

1. The rewrite to a normalised table silently dropped `glass_clear` and
   `glass_pane`, which the original 19-entry table had mapped — 33 corpus hits.
   Caught only by diffing the old keys against the new coverage, not by the 93%
   headline. `test_pre_2026_07_31_keys_still_resolve` pins them now.
2. `sandstone smooth` was skipped as "ambiguous between `cut_sandstone` and
   `smooth_sandstone`" — but this project's own `flattening.json` already
   records `sandstone_smooth.png -> cut_sandstone.png`. The answer was in a
   table built here weeks earlier. Check your own verified data before
   declaring something unknowable.

---

## 8. Packs shipping both filenames lost their animated textures

**Status:** FIXED 2026-07-31 — `flatten_rename` now prefers the source-era name.
**Found by:** in-game testing of a random corpus pack (`4OTF EUM3`): its fire
rendered as one stretched still image.

Some packs ship a texture under **both** its 1.8.9 and its modern name. The
stage renamed old → new, saw the target already present, and skipped — keeping
the modern-named file. That is backwards for a `pack_format: 1` pack: 1.8.9
renders the **1.8.9** name, so that is the file the author saw and maintained,
and the modern-named one is inert there — a leftover from a newer edit.

It also silently broke animation, which is what made it visible:

| `4OTF EUM3` ships | size | animation `.mcmeta` |
|---|---|---|
| `blocks/fire_layer_0.png` (1.8.9) | 32×1024, 32 frames | **yes** |
| `blocks/fire_0.png` (modern) | 128×2048 | **no** |

The `.mcmeta` sits beside the *old* name, so keeping the modern file left it
with no animation data and Minecraft drew the whole strip as a single texture.
`_move` now replaces the target and clears any stale `.mcmeta` on it first, so
metadata cannot outlive its texture.

Scale: the corpus warned on this **44 times across 22 packs for fire alone**,
plus `dispenser_front_horizontal`, `furnace_front_off`, `piston_top_normal`,
`rail_normal`, `repeater_off`, `torch_on` and others in ~9 packs each.

**The mistake worth remembering.** This exact warning class was audited earlier
the same day and written off as benign, on the grounds that both files were "the
pack's own art in the same style, near-identical." That compared how the two
files *looked*. It never asked which one the source version actually renders, and
never looked at the `.mcmeta` at all — so an animation bug hid behind a
similarity check. When two candidates disagree, compare what depends on them,
not just how they appear.

---

## 9. Five drop entries are pack-specific, and stay that way deliberately

**Status:** decided 2026-08-01 · not a defect · **do not "fix" this by adding
auto-detection without reading the history below.**

`data/drop_list.json` drops `enchanting_table.png` and the four
`creative_inventory` tabs because in the proving-ground pack they are
unusable — 1.7-era enchanting art (one item slot where 1.8.9 has two), and
unfinished dev placeholders (~6–8% opaque). Those are judgements about *that
pack*, not facts about 1.8.9. A different pack with good art loses five
textures for no reason.

**Six attempts were made to decide this automatically. All failed**, measured
against a 173-pack corpus with hand-labelled ground truth:

| attempt | measure | why it failed |
|---|---|---|
| 1 | slot border-vs-interior contrast | boundary at 11.2 vs 11.3 — coincidence, not signal |
| 2 | edge-density ratio slot2/slot1 | a two-slot pack scored 1.00, same as one-slot |
| 3 | slot-2 edge density | margin of 0.01 across 20 packs |
| 4 | absolute ink in slot 2 | same overlap |
| 5 | fraction differing from panel colour | textured panels score 1.00 regardless |
| 6 | correlation against vanilla 1.8.9's edge template | best yet — 19/20 held-out, 0.66 vs 0.21 on fit — but drops packs that draw one *merged* box across both slots, which is legitimate art; held-out margin collapsed to 0.01 |

The root cause is consistent: pack authors restyle these GUIs completely, so
"differs from vanilla" carries no information about being structurally wrong.
The signal a human uses is shape recognition; attempts 1–5 discarded shape
entirely, and attempt 6 recognised only one of several valid container shapes.

**The decision.** Always dropping is deterministic, correct for the proving-
ground pack, and costs another pack five textures out of thousands while still
converting successfully. That is cheaper than a detector whose failure mode is
silently discarding good art. The list stays hand-maintained and editable —
removing an entry keeps the texture.

If this is revisited, the next principled step is a multi-template match (slot
box, merged box, no container) validated against ~60 hand labels **before**
being wired in. Do not ship a threshold whose margin is smaller than the
spread between neighbouring packs.

---

## 10. CTM claim conflicts, and what the tiebreak can and cannot decide

**Status:** scoped correctly 2026-08-01 · the cross-folder tiebreak remains
arbitrary **by admission**, not by oversight.

Expanding the CTM table made previously-unmapped folders start claiming blocks
another folder already owned. `_fix_ctm` resolves that in two passes: an
EXPLICIT claim (the file names its own `matchBlocks`/`matchTiles`) beats an
INFERRED one, and where only inferred claims collide the first by sorted path
wins. Both outcomes are reported.

**Conflicts are counted only ACROSS folders.** Several `.properties` inside one
folder are complementary by design — different faces (`melon.properties` plus
`melon_top.properties`), different methods (`bookshelf` with `horizontal` and
`random`) — and OptiFine applies them together. The first version of this
resolver treated them as rivals and dropped all but one, which broke CTM for
those blocks: **45 of 176 corpus conflicts** were that shape.

**The remaining 131 are genuine, and nothing measurable separates them.** Tile
counts and methods were pulled for the real conflict pairs looking for a
completeness signal:

| kept | dropped |
|---|---|
| `vine` — 4 tiles, vertical | `vines` — 4 tiles, vertical |
| `wood birch ends` — 48, ctm | `wood birch ends` — 48, ctm |
| `grass top` — 6, random | `grass_top` — 16, repeat |

Mostly identical, and where they differ neither is obviously the author's
intent. "More tiles wins" would be a different arbitrary rule wearing a
principle's clothes. First-by-sorted-path is therefore kept: deterministic,
stable across runs, and named in the findings so the loser is never silent.

If this is revisited, the signal to look for is which folder the pack's own
`.properties` files cross-reference — not which looks more complete.

---

## 11. The offhand slot had no 1.8.9 art

**Status:** FIXED 2026-08-01 — composed by `stages/derive_sprites.py` from the
pack's own hotbar. 134 of 170 corpus packs now get it.

1.8.9 has no offhand, so the regions the 1.20.2 slicer reads for
`hud/hotbar_offhand_{left,right}` — `(24,22)` and `(53,22)` in `widgets.png` —
are empty, and the sprites fell back to vanilla: a vanilla-styled slot sitting
beside a fully custom hotbar.

Measured from vanilla 1.21.4, both sprites are a **22×22 box on a 29×24
canvas**, at `x=0` (left) and `x=7` (right). A 1.8.9 hotbar is `182×22` =
1px border + nine 20px slots + 1px border, so its **left 11 and right 11
columns** are each a real outer border beside half a slot. Joined, they make a
closed 22×22 box in the pack's own style — only the pack's pixels, no invented
art.

A single 22px cut from one end was tried first and rejected: it leaves the box
asymmetric, with a proper outer border on one side and a thin inter-slot
divider on the other.

**This work exposed a latent bug in `derive_sprites` itself.** The stage had no
empty-composition guard, so if every source piece were blank it would write a
fully transparent sprite that **overrides** vanilla and renders invisible —
§1's defect, in a stage written after that lesson was learned. It was
unreachable while the only entry read `inventory.png`'s always-present panel,
and became reachable the moment an entry read a region a pack might leave
blank. Now guarded, with a test.

---

## Not defects

- **`entity/sweep.png`** — absent from the M8SON pack (1.9+ texture). Porting the
  slicer's `sweep()` case also needs its `SQUARE` post-op. N/A until a pack ships it.
- **Dead source atlases** — *cleaned up 2026-07-31*, `stages/prune_atlases.py`.
  After slicing, atlases like `widgets.png`, `icons.png`, `particles.png` and the
  paintings sheet are unread by 26.x. Membership in `data/dead_atlases.json` is a
  checked fact: each of the 33 paths 404s against the 1.21.4 vanilla mirror, so
  modern vanilla does not ship it and nothing can load it from a pack. The stage
  never deletes a path the slice stage wrote that run — three entries are also
  slicer `copy()` outputs, where input and output are the same path, and that
  guard is what keeps them. Removes 9 files / 614KB from the M8SON pack (the
  earlier ~100KB estimate here was low by 6×).
- **Creative-inventory GUI stays vanilla.** The pack's creative textures are
  unfinished dev placeholders (red `UN SEL` / blue `SEL` boxes, ~94% transparent
  panels). Vanilla is the correct outcome — a source-pack limitation, not a bug.
