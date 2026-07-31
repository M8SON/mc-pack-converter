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

## 6. A UTF-8 BOM in `pack.mcmeta` made a pack unconvertible

**Status:** FIXED 2026-07-31 — all three readers use `encoding="utf-8-sig"`.
**Found by:** converting the 173-pack test corpus; **5 packs** were affected.

Windows editors routinely save `pack.mcmeta` with a UTF-8 BOM. `read_text()`
leaves it in place and `json.loads` rejects it outright. Three call sites read
that file, and they failed differently — the third is the one worth remembering:

| site | symptom |
|---|---|
| `stages/ingest.py` | `FatalConversionError` — the pack could not be converted at all |
| `stages/pack_meta.py` | would crash next, once ingest was fixed |
| `stages/slice.py` `_pack_format` | **silent.** It catches everything and returns `None`, which means "not gated" — so a BOM turned a 1.13+ pack into an ungated one and its `particles.png` would be mis-cut into wrong-rectangle sprites overriding vanilla, the exact failure §0 exists to prevent. |

A fail-open guard is only as good as its ability to read its input. When adding
one, check what makes the read fail, not just what makes the value wrong.

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
