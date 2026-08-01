#!/usr/bin/env python3
"""Generate mc_pack_converter/data/ctm_blocks.json.

OptiFine/MCPatcher CTM folders in 1.8.9-era packs carry no `matchBlocks` — old
MCPatcher inferred the target block from the folder name. Modern OptiFine does
not, so the converter has to supply it, and a folder it cannot map loses its
connected-texture behaviour silently.

Pack authors name those folders every which way. A 173-pack corpus produced 161
distinct spellings for what are really about 40 blocks: `glass gray`,
`glass_gray`, `glass/Grey Glass`, `Glass/Light Grey Glass`, `ore coal`,
`ore/ore_coal`, `wood spruce ends`, `wood_ends/wood_spruce`, and so on.

So this emits every spelling explicitly rather than relying on clever matching
at convert time: the table stays greppable, and a wrong mapping is visible in a
diff. Keys are normalised (lowercased, `_-/` collapsed to single spaces) and
matched against the normalised folder name by stages/optifine.py.

Every block id emitted is validated against the real block list for 1.21.4,
fetched from the version-pinned vanilla mirror. An id that is not a real block
is a hard error, not a warning — a bad mapping is worse than no mapping,
because it silently points CTM at the wrong block.
"""
from __future__ import annotations
import json
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent.parent / "mc_pack_converter" / "data" / "ctm_blocks.json"
TREE = ("https://api.github.com/repos/InventivetalentDev/minecraft-assets"
        "/git/trees/1.21.4?recursive=1")

# colour -> the spellings packs use for it
COLOURS = {
    "black": ["black"], "blue": ["blue"], "brown": ["brown"], "cyan": ["cyan"],
    "gray": ["gray", "grey"], "green": ["green"],
    "light_blue": ["light blue"],
    "light_gray": ["light gray", "light grey", "silver"],
    "lime": ["lime"], "magenta": ["magenta"], "orange": ["orange"],
    "pink": ["pink"], "purple": ["purple"], "red": ["red"], "white": ["white"],
    "yellow": ["yellow"],
}
WOODS = {"oak": ["oak"], "spruce": ["spruce"], "birch": ["birch"],
         "jungle": ["jungle"], "acacia": ["acacia"], "dark_oak": ["dark oak"]}
ORES = ["coal", "diamond", "emerald", "gold", "iron", "redstone", "lapis", "quartz"]

# folder name -> block ids, for everything that is not a colour/wood/ore family
SINGLES = {
    "glass": "glass glass_pane",
    "glass normal": "glass glass_pane",
    "normal": "glass glass_pane",
    "glass clear": "glass glass_pane",
    "glass pane": "glass_pane",
    "crafting table": "crafting_table",
    "bookshelf": "bookshelf", "bookcase": "bookshelf",
    "vine": "vine", "vines": "vine",
    # 1.8 sandstone variants, per this project's own verified flattening table:
    # sandstone_smooth.png -> cut_sandstone.png, sandstone_carved -> chiseled.
    "sandstone": "sandstone",
    "sandstone normal": "sandstone",
    "sandstone smooth": "cut_sandstone",
    "sandstone carved": "chiseled_sandstone",
    "red sandstone": "red_sandstone",
    "red sandstone normal": "red_sandstone",
    "red sandstone smooth": "cut_red_sandstone",
    "red sandstone carved": "chiseled_red_sandstone",
    "cake": "cake",
    "melon": "melon",
    "ladder": "ladder", "ladders": "ladder",
    "rail": "rail", "rails": "rail",
    "trapdoor": "oak_trapdoor",
    "repeater": "repeater",
    "portal": "nether_portal",
    "stone": "stone",
    "andesite": "andesite", "diorite": "diorite", "granite": "granite",
    "deadbush": "dead_bush", "dead bush": "dead_bush",
    "tallgrass": "short_grass", "grass": "grass_block", "grass top": "grass_block",
    "lily pad": "lily_pad",
    "monster spawner": "spawner", "spawner": "spawner",
    "sugar cane": "sugar_cane",
    "brewing stand": "brewing_stand",
    "pumpkin": "pumpkin", "pumpkin bottom": "pumpkin",
    "fenceiron": "iron_bars", "iron fence": "iron_bars",
    "nether fence": "nether_brick_fence",
    "fence nether brick": "nether_brick_fence",
    "fence wooden fence": "oak_fence", "fence wooden gate": "oak_fence_gate",
    "fence": "oak_fence", "gate": "oak_fence_gate",
    "mushroom brown": "brown_mushroom", "mushroom small brown": "brown_mushroom",
    "mushroom red": "red_mushroom", "mushroom small red": "red_mushroom",
    "mushroom big stem": "mushroom_stem",
    "mushroom big red skin": "red_mushroom_block",
    "mushrooms": "brown_mushroom red_mushroom",
    "flower allium": "allium",
    "flower blue orchid": "blue_orchid",
    "flower dandelion": "dandelion",
    "flower houstonia": "azure_bluet",
    "flower oxeye daisy": "oxeye_daisy",
    "flower poppy": "poppy",
    "hardened clay": "terracotta",
}

# Deliberately NOT mapped, with the reason. Listed so the next person does not
# rediscover them; each still warns at convert time, which is the honest outcome.
SKIP = {
    "default": "not a block — a fallback folder name",
    "leaves fancy": "applies to every leaf type, and 'fancy'/'fast' are two "
                    "folders for the same blocks — mapping both would have them "
                    "fight over the same matchBlocks",
    "leaves fast": "see 'leaves fancy'",
    "wool": "applies to all 16 wools; per-colour folders are mapped instead",
    "wools b p o t": "multi-colour group folder, no single target",
    "wools b w": "multi-colour group folder, no single target",
    "wools p g y c": "multi-colour group folder, no single target",
    "wools r g b v": "multi-colour group folder, no single target",
}


def norm(s: str) -> str:
    for ch in "_-/":
        s = s.replace(ch, " ")
    return " ".join(s.lower().split())


def build() -> dict[str, str]:
    t: dict[str, str] = {}

    def put(key: str, value: str) -> None:
        # namespaced, matching what matchBlocks= lines already carry
        value = " ".join(f"minecraft:{b}" for b in value.split())
        k = norm(key)
        if k in t and t[k] != value:
            raise SystemExit(f"conflicting mapping for {k!r}: {t[k]!r} vs {value!r}")
        t[k] = value

    for canon, spellings in COLOURS.items():
        for s in spellings:
            glass = f"{canon}_stained_glass {canon}_stained_glass_pane"
            for form in (f"glass {s}", f"{s} glass", f"stained glass {s}",
                         f"glass stained glass {s}"):
                put(form, glass)
            for form in (f"hardened clay {s}", f"hardened clay stained hardened clay {s}",
                         f"stained hardened clay {s}", f"{s} terracotta"):
                put(form, f"{canon}_terracotta")
            for form in (f"wool {s}", f"{s} wool"):
                put(form, f"{canon}_wool")
    for canon, spellings in WOODS.items():
        for s in spellings:
            for form in (f"planks {s}", f"{s} planks", f"planks planks {s}"):
                put(form, f"{canon}_planks")
            for form in (f"wood {s} ends", f"wood {s}", f"{s} log",
                         f"wood ends wood {s}", f"log {s}"):
                put(form, f"{canon}_log")
    for ore in ORES:
        block = "lapis_ore" if ore == "lapis" else (
            "nether_quartz_ore" if ore == "quartz" else f"{ore}_ore")
        for form in (f"ore {ore}", f"{ore} ore", f"ore ore {ore}"):
            put(form, block)
    for k, v in SINGLES.items():
        put(k, v)
    # cloth_N: the pre-flattening wool data value, used as a PROPERTIES FILENAME
    # by terrain.png-era packs (cloth_0.properties ... cloth_15.properties).
    # Confirmed independently of any image comparison: in every pack that uses
    # them, the grouping folder's abbreviation matches the colours this mapping
    # predicts - wools-b-w holds cloth 0/7/8/15 (black..white), wools-r-g-b-v
    # holds 10/11/13/14 (red, green, blue, violet), and so on.
    CLOTH = ["white", "orange", "magenta", "light_blue", "yellow", "lime",
             "pink", "gray", "light_gray", "cyan", "purple", "blue", "brown",
             "green", "red", "black"]
    for i, colour in enumerate(CLOTH):
        put(f"cloth {i}", f"{colour}_wool")
    return t


def main() -> int:
    print("fetching the 1.21.4 block list from the vanilla mirror...")
    with urllib.request.urlopen(TREE, timeout=120) as r:
        tree = json.load(r)
    if tree.get("truncated"):
        raise SystemExit("mirror tree listing was truncated; cannot validate")
    valid = {p["path"].rsplit("/", 1)[1][:-5] for p in tree["tree"]
             if p["path"].startswith("assets/minecraft/blockstates/")
             and p["path"].endswith(".json")}
    print(f"  {len(valid)} real block ids")

    table = build()
    bad = sorted({b for v in table.values() for b in v.split()
                  if b.removeprefix("minecraft:") not in valid})
    if bad:
        raise SystemExit(f"NOT REAL BLOCK IDS: {bad}")

    payload = {
        "_comment": (
            "OptiFine CTM folder name -> the modern block ids its matchBlocks "
            "should name. GENERATED by tools/gen_ctm_blocks.py; do not hand-edit. "
            "Keys are normalised: lowercased, with _ - / collapsed to single "
            "spaces. stages/optifine.py normalises the folder name the same way "
            "before looking it up, trying the last path component first and then "
            "the whole relative path, so 'glass/Grey Glass', 'glass_gray' and "
            "'glass gray' all resolve. Spellings come from a 173-pack corpus that "
            "produced 161 distinct folder names for ~40 blocks. Every id here is "
            "validated against the real 1.21.4 block list at generation time; a "
            "wrong mapping is worse than none, because it points connected "
            "textures at the wrong block. Folders deliberately left unmapped are "
            "listed in _unmapped with the reason."),
        "_unmapped": SKIP,
        "blocks": table,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n")
    print(f"wrote {len(table)} mappings -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
