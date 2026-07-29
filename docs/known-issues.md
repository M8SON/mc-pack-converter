# Known Issues

Open defects and unrecovered art, with enough detail to resume cold.
Verified findings only — each entry says how it was measured.

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

## 2. 23 custom mob-effect icons are silently dropped

**Status:** open · needs its own spec
**Blocked on:** a researched 1.8.9 effect-grid → name table

Modern Minecraft reads potion-effect icons from `textures/mob_effect/<name>.png`.
Nothing reads the 18px icon strip inside `textures/gui/container/inventory.png`
anymore, so the pack's **23 custom effect icons are lost** and vanilla's are used.

Mojang's 1.14 slicer *does* extract that strip — but its coordinates cannot be
reused here, because **1.9 rearranged the grid** to fit `levitation`, `glowing`,
`luck` and `unluck`. Measured occupancy of the 18px grid across the vanilla mirror:

| version | row 0 | row 1 | row 2 |
|---|---|---|---|
| 1.8.9 | 7 | 8 | 8 |
| 1.9.4 / 1.11.2 / 1.12.2 | 11 | 11 | 8 |
| 1.13.2 | 12 | 12 | 12 |

1.8.9 vs 1.9.4 differ by 3331 pixels within the strip. The slicer's coordinates
describe the post-rearrangement grid, so applying them to a 1.8.9 pack would
mis-map icons — e.g. it expects `regeneration` at cell (7,0), which is empty in
1.8.9. agentdid127's `InventoryConverter` treats the change as a pure
`y166 → y198` shift, which the numbers above show is insufficient.

In the M8SON pack the strip holds **23 custom icons** (4 cells blank:
`regeneration`, `slow_falling`, `conduit_power`, `dolphins_grace` — the latter
three are post-1.8.9 effects).

**To resume:** build the 1.8.9 cell → effect-name table, verified against the
Minecraft Wiki effect list and the vanilla mirror, then emit `mob_effect/*.png`
records. Note the icon art itself was redrawn in 1.13, so pixel-matching a 1.8.9
cell against a modern vanilla icon will not identify it — the mapping has to come
from the effect ordering, not image similarity.

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
