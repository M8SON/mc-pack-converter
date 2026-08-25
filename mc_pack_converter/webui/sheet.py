"""Build the QA sheet model from a converted pack's output zip.

Read from the ZIP, not from the pipeline's working root: convert() deletes
that root in a finally block before any front end sees the result. The zip is
also the honest subject — it is what the user loads into Minecraft.
"""
from __future__ import annotations
import base64, io, json, re, zipfile
from pathlib import Path
from PIL import Image

from .glint_preview import glint_frames
from .sky import render_sky
from .sky_composite import (clock, composite, phase, sample_times,
                            visible_at)
from .armor import (crossed_spin_frames, cube_spin_frames, fire_spin_frames,
                    render_armor, spin_frames)

A = "assets/minecraft/"

# Ordered, and the order is load-bearing twice over: it is the order the page
# scrolls in, and the first prefix that matches wins. Armor must precede the
# mob exclusion because textures/entity/equipment/ sits inside textures/entity/.
SECTIONS: list[tuple[str, tuple[str, ...]]] = [
    ("GUI",       (A + "textures/gui/",)),
    ("Blocks",    (A + "textures/block/",)),
    ("Items",     (A + "textures/item/",)),
    ("Particles", (A + "textures/particle/",)),
    ("Sky",       (A + "textures/environment/", A + "optifine/sky/")),
    ("Animated",  ()),   # derived, not path-matched: see animation_of()
    ("Armor",     (A + "textures/entity/equipment/",)),
    ("Other",     (A + "textures/painting/", A + "textures/mob_effect/",
                   A + "textures/misc/", A + "textures/map/",
                   A + "textures/effect/")),
]

# Named rather than silently dropped: the page reports what it did not show.
EXCLUSIONS: list[tuple[str, tuple[str, ...]]] = [
    ("CTM tiles",    (A + "optifine/ctm/",)),
    ("Mob textures", (A + "textures/entity/",)),
    ("Font glyphs",  (A + "textures/font/",)),
    ("Colormaps",    (A + "optifine/colormap/", A + "optifine/lightmap/")),
]


def _match(name: str, table) -> str | None:
    if not name.lower().endswith(".png"):
        return None
    for label, prefixes in table:
        if name.startswith(prefixes):
            return label
    return None


def section_for(name: str) -> str | None:
    """The sheet section this zip entry belongs to, or None."""
    return _match(name, SECTIONS)


def exclusion_for(name: str) -> str | None:
    """The named exclusion this zip entry falls under, or None.

    A section always wins: textures/entity/equipment/ is Armor even though
    textures/entity/ is excluded wholesale.
    """
    if _match(name, SECTIONS):
        return None
    return _match(name, EXCLUSIONS)


THUMB = 64
# Frames in one full turn. 24 reads as a smooth rotation and costs
# ~0.05s per model, measured; the whole sheet still builds in seconds.
SPIN = 24
# How long one full turn takes, for everything on the page. The game does not
# rotate blocks at all, so this is a free choice; the animation frametime is
# not, and is honoured exactly. Measured on the reference pack, 3s costs 375
# frames against 508 at 4s and keeps every turn inside 3.20-4.80s rather than
# 3.20-6.40s.
TURN_MS = 3000


def spin_count(frames: int, step_ms: int) -> int:
    """Spin frames for an animation of `frames` frames stepping every `step_ms`.

    The smallest MULTIPLE of the animation's own length that reaches TURN_MS.
    A multiple is the whole point: the old flat 24 replayed part of any
    animation whose length did not divide it -- fire has 16 frames, so frames
    0-7 appeared twice per turn and 8-15 once, which is the stutter Mason saw.
    """
    need = -(-TURN_MS // step_ms)          # ceil: frames to reach the target
    return -(-need // frames) * frames     # ceil to a whole number of cycles


def thumb_data_uri(im: Image.Image, box: int = THUMB) -> str:
    """A PNG data URI, downscaled to fit `box` and NEVER upscaled.

    A 16x16 texture is emitted at 16x16 and enlarged by CSS with
    image-rendering: pixelated. Upscaling here with any filter would bake a
    blurry smear into the bytes, which reads as damaged art.
    """
    im = im.convert("RGBA")
    if max(im.size) > box:
        s = box / max(im.size)
        im = im.resize((max(1, round(im.width * s)),
                        max(1, round(im.height * s))), Image.NEAREST)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


# The lightbox's own ceiling. The bridge used to serve full-size originals on
# demand -- 22.5MB across the reference pack -- and a static page has no such
# channel. Measured: only 126 of 1019 shown tiles are downscaled at all, and
# 20.6MB of their 21.9MB is three OptiFine sky textures at 6144px. Capping
# here inlines 111 of the 126 for 0.66MB and leaves 15 atlases below native
# size, which are judged whole rather than pixel by pixel.
FULL = 512


def full_data_uri(im: Image.Image) -> str | None:
    """A larger view for the lightbox, or None when the thumbnail already is
    the original. thumb_data_uri never upscales, so anything within THUMB is
    already being shown at full resolution."""
    if max(im.size) <= THUMB:
        return None
    return thumb_data_uri(im, box=FULL)


# The shape build_sheet returns when there is nothing to show -- a report-only
# run, or a conversion that produced no zip to read back.
EMPTY_SHEET = {"sections": [], "excluded": [], "total": 0}


TICK_MS = 50  # one Minecraft tick, and the default frametime

# Two textures a cube gets wrong, in two DIFFERENT ways. Matched on the
# texture's own name.
#   Fire clings to the block's vertical faces; a cube gives it a top face,
#   flame floating in the air that never appears in game.
#   The nether portal is a single flat quad through the middle of its block,
#   drawn crossed so both build orientations read at once.
# They shared one branch before fire moved onto the faces. They must not now.
ON_THE_FACES = ("fire_",)
THROUGH_THE_MIDDLE = ("nether_portal",)


def animation_of(zf: zipfile.ZipFile, name: str) -> dict | None:
    """The `animation` object from this texture's .mcmeta sidecar, or None.

    A sidecar is not proof of animation: misc/enchanted_item_glint.png.mcmeta
    is real and carries only a `texture` block.
    """
    try:
        meta = json.loads(zf.read(name + ".mcmeta"))
    except (KeyError, ValueError, UnicodeDecodeError):
        return None
    anim = meta.get("animation")
    return anim if isinstance(anim, dict) else None


def frame_count(size: tuple[int, int]) -> int:
    """Frames in a vertical strip.

    No .mcmeta in the wild declares a frame height -- all 10 in the reference
    pack carry only frames/frametime/interpolate, two of them empty. So the
    count is derived from Minecraft's own rule: frames are square, therefore
    frame height equals the texture width.
    """
    w, h = size
    if w <= 0 or h % w or h // w < 2:
        return 1
    return h // w


def slice_frames(im: Image.Image, count: int) -> list[Image.Image]:
    fh = im.height // count
    return [im.crop((0, i * fh, im.width, (i + 1) * fh)) for i in range(count)]


def animation_frames(im: Image.Image, anim: dict) -> list[Image.Image] | None:
    """The texture's animation frames in play order, or None if it is a still.

    Kept separate from the tile it ends up on because the number of frames the
    PAGE shows is no longer the number the animation has -- the cube spin
    resamples them -- and this selection still has to be exercised on its own.
    """
    count = frame_count(im.size)
    if count < 2:
        return None
    frames = slice_frames(im.convert("RGBA"), count)
    order = anim.get("frames")
    if isinstance(order, list):
        # Out-of-range indices are real: prismarine declares up to 3 on a
        # one-frame texture. Drop them rather than raising.
        picked = [frames[i] for i in order
                  if isinstance(i, int) and 0 <= i < count]
        if picked:
            frames = picked
    return frames


def _animated_tile(name: str, im: Image.Image, anim: dict) -> dict | None:
    """An animated tile, or None if this texture is really a single frame."""
    frames = animation_frames(im, anim)
    if frames is None:
        return None
    ft = anim.get("frametime")
    tile = _tile(name, im)
    # Turn the block through a full circle while the texture animates. Angle
    # and animation frame advance together in ONE loop, so the cost is the spin
    # count rather than angles x animation-frames. A flat strip shows the art
    # but not how it tiles against itself at an edge, or how the top reads
    # against the side; on a cube you see all three.
    leaf = name.rsplit("/", 1)[-1]
    if leaf.startswith(ON_THE_FACES):
        render = fire_spin_frames
    elif leaf.startswith(THROUGH_THE_MIDDLE):
        render = crossed_spin_frames
    else:
        render = cube_spin_frames
    step = (ft if isinstance(ft, int) and ft > 0 else 1) * TICK_MS
    spun = render(frames, spin_count(len(frames), step))
    tile["frames"] = [thumb_data_uri(f, box=max(f.size)) for f in spun]
    tile["frametime"] = step
    return tile


def build_sheet(zip_path: Path) -> dict:
    """The whole QA sheet model for one converted pack.

    Eager: measured on the reference pack (M8SON 1.8 PVP PACK, 26.2 target)
    at 5.7s for 1019 tiles -- 6.36MB of base64 and JSON, comparable to the
    pack's own 7.3s conversion rather than negligible next to it, but still
    cheap enough to build up front. There is no bridge left to serve tiles
    on demand from, so up-front is the only shape available: full-size
    originals are inlined too, capped at FULL rather than left unbundled --
    see FULL's own comment above.
    """
    buckets: dict[str, list] = {}
    excluded: dict[str, int] = {}
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name.endswith("/"):
                continue
            label = section_for(name)
            if label is None:
                gone = exclusion_for(name)
                if gone:
                    excluded[gone] = excluded.get(gone, 0) + 1
                continue
            try:
                with Image.open(io.BytesIO(z.read(name))) as im:
                    anim = animation_of(z, name)
                    # `is not None`, NOT truthiness: nether_portal.png and
                    # water_flow.png both declare an EMPTY animation object,
                    # and `if {}` would skip the two biggest strips in the pack.
                    tile = _animated_tile(name, im, anim) if anim is not None else None
                    if tile is not None:
                        label = "Animated"
                    else:
                        tile = _tile(name, im)
                    if label == "Armor":
                        # The flat UV sheet means nothing to a human eye.
                        rendered = render_armor(im)
                        tile["thumb"] = thumb_data_uri(rendered, box=128)
                        # Turn it. A fixed 3/4 view hides the back and the far
                        # side, which is exactly where a bad conversion hides.
                        tile["frames"] = [thumb_data_uri(f, box=max(f.size))
                                          for f in spin_frames(im, SPIN)]
                        tile["frametime"] = TURN_MS // SPIN
                        # Clicking any other tile opens its original texture.
                        # For armor that would be the flat UV sheet again, so
                        # the model would only ever exist at thumbnail size --
                        # too small to judge the art, which is the whole point.
                        # Carry the render at its NATIVE canvas size for the
                        # lightbox instead. Native is the most information
                        # there is -- the source art is 64x32, so rendering
                        # larger would only interpolate more nearest-neighbour
                        # blocks. CSS pixelates it up to fill the window.
                        tile["full"] = thumb_data_uri(rendered, box=max(rendered.size))
            except Exception:
                # A texture the converter emitted broken is a finding, not a
                # reason to show the user no sheet at all.
                continue
            buckets.setdefault(label, []).append(tile)

        enchanted = _glint_tile(z)
        if enchanted is not None:
            buckets.setdefault("Items", []).append(enchanted)
        for tile in _sky_tiles(z):
            buckets.setdefault("Sky", []).append(tile)

    sections = []
    for label, _ in SECTIONS:
        tiles = buckets.get(label)
        if tiles:
            # Path order within a section, except where a tile asks to lead:
            # the sky composites are the summary of the layer tiles below them
            # and read as a caption if they land underneath instead. They also
            # carry their own order, because day order is not the order their
            # clock strings sort in -- 0:00 would put midnight first.
            sections.append({"label": label,
                             "tiles": sorted(tiles,
                                             key=lambda t: (t.get("order", 99),
                                                            t["path"]))})
    return {
        "sections": sections,
        "excluded": [{"label": k, "count": v}
                     for k, v in sorted(excluded.items(), key=lambda kv: -kv[1])],
        "total": sum(len(s["tiles"]) for s in sections),
    }


# What the glint is shown on. A sword is the item people look at first, and
# every 1.8.9 pack has one; the diamond one because it is the one pack authors
# actually redraw.
_GLINT_ON = A + "textures/item/diamond_sword.png"
_GLINT_TEX = A + "textures/misc/enchanted_glint_item.png"


# How far round the ring the preview turns, and in how many steps. A sky is
# judged by its horizon, and a horizon is 360 degrees of it.
_SKY_YAWS = 12
_SKY_VIEW = (320, 200)
_SKY_DIR = re.compile(r"^" + A + r"optifine/sky/(world-?\d+)/sky(\d+)\.properties$")


def _sky_layers(z: zipfile.ZipFile) -> list[tuple[str, int, str]]:
    """(world, layer number, properties path), in load order."""
    found = []
    for name in z.namelist():
        m = _SKY_DIR.match(name)
        if m:
            found.append((m.group(1), int(m.group(2)), name))
    return sorted(found, key=lambda t: (t[0], t[1]))


def _sky_props(raw: bytes) -> dict:
    props = {}
    for line in raw.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            props[k.strip()] = v.strip()
    return props


def _sky_tiles(z: zipfile.ZipFile) -> list[dict]:
    """One ground-level preview per sky layer, labelled with what it does.

    A sky layer flat is an unreadable 6144x4096 sheet of six cube faces. What
    the author wants to know is what it looks like standing in the world.

    It used to also say "never loads" against any layer above a gap in the
    numbering, on the strength of OptiFine's own documentation: reads sky<n>
    "until a .properties file is not found". THE SHIPPED CODE DOES NOT DO
    THAT. In CustomSky.readCustomSkies the `countMissing` counter is
    initialised inside the loop body, so `if (countMissing > 10) break` can
    never fire and the loop runs 0..999 whatever the gaps. Measured in game on
    26.1.2_HD_U_K1_pre2 with a probe carrying sky1/sky3/sky15 as solid
    red/green/magenta at blend=replace: the log read all three and the sky
    rendered MAGENTA -- sky15, across an eleven-layer gap. The label was a
    false warning on every pack it fired for, so it is gone.
    """
    names = set(z.namelist())
    tiles = []
    # Layers share source textures -- M8SON's sky1 and sky2 are both cloud2,
    # sky7 and sky8 both sky_sunflare -- and a source is a 6144x4096 PNG whose
    # decode dominates the cost. Keyed by texture, so a shared source is
    # decoded and rendered once: 6 layers, 4 renders.
    rendered: dict[str, list] = {}
    layers: list[tuple[str, int, dict, list]] = []
    for world, number, path in _sky_layers(z):
        props = _sky_props(z.read(path))
        src = props.get("source", f"./sky{number}.png").lstrip("./")
        tex = path.rsplit("/", 1)[0] + "/" + src.rsplit("/", 1)[-1]
        if tex not in names:
            continue
        views = rendered.get(tex)
        if views is None:
            try:
                with Image.open(io.BytesIO(z.read(tex))) as im:
                    # RGBA explicitly. Converting to RGB here happens to keep
                    # a palette tRNS alive -- Pillow carries info["transparency"]
                    # across the conversion and faces() re-applies it -- but
                    # relying on that leaves the sunflare one Pillow release
                    # away from turning white again.
                    box = im.convert("RGBA")
                    views = [render_sky(box, yaw=i * 360 / _SKY_YAWS, size=_SKY_VIEW)
                             for i in range(_SKY_YAWS)]
            except Exception:
                continue
            rendered[tex] = views
        layers.append((world, number, props, views))

        window = ""
        if "startFadeIn" in props and "endFadeOut" in props:
            window = f", {props['startFadeIn']}-{props['endFadeOut']}"
        label = f"sky{number} ({props.get('blend', 'add')}{window})"
        tiles.append({
            "name": label,
            "path": path,
            "size": "sky layer",
            "thumb": thumb_data_uri(views[0], box=128),
            "frames": [thumb_data_uri(v, box=max(_SKY_VIEW)) for v in views],
            "frametime": TURN_MS * 2 // _SKY_YAWS,
            "full": thumb_data_uri(views[0], box=FULL),
        })
    return _composite_tiles(layers) + tiles


def _composite_tiles(layers: list[tuple[str, int, dict, list]]) -> list[dict]:
    """The sky itself: every layer that reaches the eye at that moment, stacked.

    THE TIMES COME FROM THE PACK. Fixed ones do not work, and the reference
    pack is why: sampling at 6:00, 12:00 and 18:00 put all three inside sky3's
    5:30-18:20 replace, so all three tiles were the same blue picture, and the
    pack's red sunrise and sunset -- cloud2, mean RGB 85/10/0 against cloud1's
    125/141/180 -- never appeared at all, being up for only 40 and 50 minutes.
    sample_times walks the day instead and takes the fewest moments that show
    every layer at least once.

    Free, or near enough. The costly part -- decoding a 6144x4096 PNG and
    ray-tracing the cube -- has already happened for the per-layer tiles above,
    and this reuses the yaw-0 render each of them already holds.
    """
    tiles = []
    worlds = sorted({world for world, _, _, _ in layers})
    for world in worlds:
        here = sorted((n, p, v) for w, n, p, v in layers if w == world)
        views_by = {n: v for n, _, v in here}
        spec = [(n, p) for n, p, _ in here]
        for order, (ticks, _) in enumerate(sample_times(spec)):
            stack = visible_at(spec, ticks)
            if not stack:
                continue
            try:
                view = composite([(views_by[n][0], props.get("blend", "add"), level)
                                  for n, props, level in stack])
            except Exception:
                continue
            at = clock(ticks)
            which = ", ".join(f"sky{n}" for n, _, _ in stack)
            where = "" if world == "world0" or len(worlds) == 1 else f" [{world}]"
            tiles.append({
                "name": f"{phase(ticks)} {at}{where} - {which}",
                "path": f"{world} at {at}",
                "size": f"sky at {at}",
                "order": order,
                "thumb": thumb_data_uri(view, box=128),
                "full": thumb_data_uri(view, box=FULL),
            })
    return tiles


def _glint_tile(z: zipfile.ZipFile) -> dict | None:
    """The glint over the pack's own sword, moving, or None if either is absent.

    Flat, a glint is diagonal streaks on a square: it says nothing about
    whether an enchanted item will read in game, which is the only question
    anyone has about it.
    """
    names = set(z.namelist())
    if _GLINT_ON not in names or _GLINT_TEX not in names:
        return None
    try:
        with Image.open(io.BytesIO(z.read(_GLINT_ON))) as item, \
             Image.open(io.BytesIO(z.read(_GLINT_TEX))) as glint:
            frames = glint_frames(item.convert("RGBA"), glint.convert("RGBA"))
    except Exception:
        # Same rule as the tile loop: a broken texture is a finding elsewhere,
        # not a reason to withhold the whole sheet.
        return None
    return {
        "name": "diamond_sword.png (enchanted)",
        "path": _GLINT_ON + "#enchanted",
        "size": "preview",
        "thumb": thumb_data_uri(frames[0], box=128),
        "frames": [thumb_data_uri(f, box=128) for f in frames],
        "frametime": TURN_MS // len(frames),
        "full": thumb_data_uri(frames[0], box=FULL),
    }


def _tile(name: str, im: Image.Image) -> dict:
    return {
        "name": name.rsplit("/", 1)[-1],
        "path": name,
        "w": im.width,
        "h": im.height,
        "thumb": thumb_data_uri(im),
        "full": full_data_uri(im),
        "frames": None,
        "frametime": None,
    }
