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

---

## Not defects

- **`entity/sweep.png`** — absent from the M8SON pack (1.9+ texture). Porting the
  slicer's `sweep()` case also needs its `SQUARE` post-op. N/A until a pack ships it.
- **Dead source atlases.** After slicing, `particles.png`, `entity/explosion.png`
  and the paintings atlas are unread by 26.x, as are `widgets.png` and `icons.png`
  already. Left in place deliberately (~100KB); removing them is separate cleanup.
- **Creative-inventory GUI stays vanilla.** The pack's creative textures are
  unfinished dev placeholders (red `UN SEL` / blue `SEL` boxes, ~94% transparent
  panels). Vanilla is the correct outcome — a source-pack limitation, not a bug.
