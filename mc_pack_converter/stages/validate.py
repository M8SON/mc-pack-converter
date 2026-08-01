from __future__ import annotations
import json
from ..pipeline import ConversionContext, Severity
from ..imaging import is_valid_png, png_size
from ..data import load_table
from ..mcmeta import loads_lenient
from .optifine import parse_properties, read_properties_text, iter_properties

# Checks below assert things about the OUTPUT that map to a visible in-game
# symptom. They exist because the converter's own warnings cannot report a
# problem it does not know about: the villager GUI, the lost fire animation and
# the dangling model paths all converted with zero warnings and were found by
# looking at the screen. Each check names the symptom, not the mechanism.

_LEGACY_TEXTURE_DIRS = ("blocks/", "items/")


def _safe_size(path):
    """png_size, but None for a file that cannot be read.

    A corrupt PNG is already reported by _check_pngs; these checks must not
    crash the stage over it — that is how validation silently skipped 8 packs
    before (docs/known-issues.md #6).
    """
    try:
        return png_size(path)
    except Exception:
        return None


def _check_model_refs(ctx, mc):
    """Models pointing at pre-conversion texture folders -> null textures.

    A reference under blocks/ or items/ cannot resolve after conversion: those
    folders no longer exist, in the pack or in vanilla. Scoped to legacy
    folders on purpose — a model may legitimately name a modern texture the
    pack does not ship, because vanilla supplies it.
    """
    bad = 0
    for models in (mc.parent).glob("*/models"):
        for path in models.rglob("*.json"):
            try:
                data = loads_lenient(path.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            for ref in (data.get("textures") or {}).values():
                if isinstance(ref, str) and ref.replace("minecraft:", "").startswith(
                        _LEGACY_TEXTURE_DIRS):
                    bad += 1
                    if bad <= 5:
                        ctx.add("validate", Severity.ERROR,
                                f"model points at a pre-conversion texture path "
                                f"'{ref}' — this block/item will render as a null "
                                "texture", str(path.relative_to(mc.parent)))
    if bad > 5:
        ctx.add("validate", Severity.ERROR,
                f"{bad} model texture references point at pre-conversion paths "
                "(first 5 listed); those blocks/items render as null textures")


def _check_blockstate_refs(ctx, mc):
    """Bare blockstate model names -> missing MODEL -> magenta cubes.

    1.8.9 resolved these relative to models/block/; modern needs the full path,
    so a name with no '/' sends it looking in models/ where nothing lives.
    """
    bad = 0
    for states in (mc.parent).glob("*/blockstates"):
        for path in states.rglob("*.json"):
            try:
                data = loads_lenient(path.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            refs = []
            for v in (data.get("variants") or {}).values():
                refs += [e.get("model") for e in (v if isinstance(v, list) else [v])
                         if isinstance(e, dict)]
            for mp in (data.get("multipart") or []):
                a = mp.get("apply") if isinstance(mp, dict) else None
                refs += [e.get("model") for e in (a if isinstance(a, list) else [a])
                         if isinstance(e, dict)]
            for r in refs:
                if isinstance(r, str) and "/" not in r.replace("minecraft:", ""):
                    bad += 1
                    if bad <= 5:
                        ctx.add("validate", Severity.ERROR,
                                f"blockstate names model '{r}' with no folder — "
                                "modern cannot resolve it and the block renders "
                                "as a magenta cube",
                                str(path.relative_to(mc.parent)))
    if bad > 5:
        ctx.add("validate", Severity.ERROR,
                f"{bad} blockstate model references have no folder (first 5 "
                "listed); those blocks render as magenta cubes")


def _check_gui_canvas(ctx, mc):
    """A GUI whose canvas aspect differs from what modern samples -> squashed.

    Modern blits a GUI from a fixed reference canvas. If the pack's file has a
    different aspect, every coordinate is sampled at the wrong scale: this is
    the villager screen, 240x166 on a square canvas where modern wants 276x166
    on a 2:1 one.
    """
    expected = {}
    for rec in load_table("slices"):
        rw, rh = rec["box"][4:]
        if rw and rh:
            expected.setdefault(rec["output"], (rw, rh))
    for out_rel, (rw, rh) in expected.items():
        p = ctx.root / out_rel
        if not p.exists() or rw == rh:
            continue                      # square reference: nothing to detect
        size = _safe_size(p)
        if not size or not size[1]:
            continue
        if abs(size[0] / size[1] - rw / rh) > 0.01:
            ctx.add("validate", Severity.ERROR,
                    f"GUI canvas is {size[0]}x{size[1]} but modern samples it as "
                    f"{rw}x{rh}; it will render squashed and misaligned",
                    str(p.relative_to(mc.parent)))


def _check_animation_strips(ctx, mc):
    """A texture modern animates, shipped without its .mcmeta -> a still image.

    This is the fire bug: a pack shipping both filenames kept the modern-named
    file while the animation .mcmeta stayed beside the old one.

    Scoped to the textures vanilla actually animates (data/animated_textures.json,
    generated from the mirror). The obvious heuristic — "tall strip, no .mcmeta"
    — is wrong: vanilla itself ships environment/rain.png and
    entity/endercrystal/endercrystal_beam.png that way, and it fired on 143 of
    170 corpus packs.
    """
    for rel in load_table("animated_textures")["animated"]:
        png = mc / "textures" / f"{rel}.png"
        if not png.exists() or png.with_name(png.name + ".mcmeta").exists():
            continue
        size = _safe_size(png)
        if not size or not size[0] or size[1] <= size[0]:
            continue                       # not a strip; nothing to animate
        ctx.add("validate", Severity.ERROR,
                f"modern animates this texture but the pack ships no .mcmeta; "
                f"its {size[1] // size[0]} frames will draw as one stretched "
                "still image", str(png.relative_to(mc.parent)))


def _check_pngs(ctx, mc):
    for png in mc.rglob("*.png"):
        if not is_valid_png(png):
            ctx.add("validate", Severity.ERROR, "corrupt or empty png",
                    str(png.relative_to(mc)))

def _check_mcmeta(ctx, mc):
    for meta in mc.rglob("*.png.mcmeta"):
        try:
            data = json.loads(meta.read_text())
        except Exception:
            ctx.add("validate", Severity.WARNING, "unparseable mcmeta",
                    str(meta.relative_to(mc)))
            continue
        if "animation" not in data:
            continue
        png = meta.with_suffix("")  # drop .mcmeta -> foo.png
        if not png.exists():
            continue
        if not is_valid_png(png):
            continue
        w, h = png_size(png)
        # square-frame assumption: frame height == width; height must be a multiple
        if w and h % w != 0:
            ctx.add("validate", Severity.WARNING,
                    f"animation frame height mismatch ({w}x{h})",
                    str(png.relative_to(mc)))

def _check_optifine(ctx, mc):
    of = mc / "optifine"
    if not of.is_dir():
        return
    for prop in iter_properties(of):
        props = parse_properties(read_properties_text(prop))
        src = props.get("source")
        if src and not (prop.parent / src).resolve().exists():
            ctx.add("validate", Severity.WARNING, f"missing source {src}",
                    str(prop.relative_to(mc)))

def validate(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    if not mc.is_dir():
        return
    _check_pngs(ctx, mc)
    _check_mcmeta(ctx, mc)
    _check_optifine(ctx, mc)
    _check_model_refs(ctx, mc)
    _check_blockstate_refs(ctx, mc)
    _check_gui_canvas(ctx, mc)
    _check_animation_strips(ctx, mc)
