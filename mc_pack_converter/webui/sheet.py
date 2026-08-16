"""Build the QA sheet model from a converted pack's output zip.

Read from the ZIP, not from the pipeline's working root: convert() deletes
that root in a finally block before any front end sees the result. The zip is
also the honest subject — it is what the user loads into Minecraft.
"""
from __future__ import annotations
import base64, io, zipfile
from pathlib import Path
from PIL import Image

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


def build_sheet(zip_path: Path) -> dict:
    """The whole QA sheet model for one converted pack.

    Eager: measured at 1.75s and 1.72MB of base64 for 1021 tiles on the
    reference pack, against a conversion that takes far longer. Full-size
    originals are 22.5MB and are NOT bundled -- api.texture() serves those on
    demand.
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
                    tile = _tile(name, im)
            except Exception:
                # A texture the converter emitted broken is a finding, not a
                # reason to show the user no sheet at all.
                continue
            buckets.setdefault(label, []).append(tile)

    sections = []
    for label, _ in SECTIONS:
        tiles = buckets.get(label)
        if tiles:
            sections.append({"label": label,
                             "tiles": sorted(tiles, key=lambda t: t["path"])})
    return {
        "sections": sections,
        "excluded": [{"label": k, "count": v}
                     for k, v in sorted(excluded.items(), key=lambda kv: -kv[1])],
        "total": sum(len(s["tiles"]) for s in sections),
    }


def _tile(name: str, im: Image.Image) -> dict:
    return {
        "name": name.rsplit("/", 1)[-1],
        "path": name,
        "w": im.width,
        "h": im.height,
        "thumb": thumb_data_uri(im),
        "frames": None,
        "frametime": None,
    }
