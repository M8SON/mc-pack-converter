"""Drop a texture only when a measurement says the pack's own art cannot work.

drop_list.json holds version FACTS — the 1.11 horse re-UV, the 1.14 villager
redesign — which are true of every 1.8.9 pack. Five entries used to sit there
that were not facts at all but judgements about M8SON: its enchanting table is
1.7-era art and its creative tabs are unfinished dev placeholders. Feeding any
other pack through threw the same five textures away, and 82 of the 173 in the
corpus were losing perfectly good art that way.

This stage asks the question per pack instead, and puts the measured number in
the findings so the decision is explainable rather than asserted. The predicates
and their calibration live in data/conformance.json.

A texture that fails is deleted, exactly like a drop_list entry, so modern
Minecraft renders its own. There is no third outcome and nothing is referred
back to the user: convert it correctly or drop it.
"""
from __future__ import annotations
import statistics
from pathlib import Path
from PIL import Image
from ..pipeline import ConversionContext, Severity
from ..data import load_table


def _slot_presence(im: Image.Image, spec: dict) -> float:
    """Score each expected slot by its FOUR borders, not by one ring average.

    A ring average cannot tell a slot box from a box that merely clips one. A
    1.7-era pack has a single slot sitting BETWEEN 1.8.9's two positions, so
    both sample boxes catch a piece of its border and both score well — that is
    how SOUPSKIDZ4LIFE passed and rendered with Minecraft's two slots drawn over
    its one (Mason, in-game, 2026-08-02). The same root cause killed an earlier
    predicate on 07-31 and I failed to apply the note.

    Two conditions per slot, and the score is the margin by which the weaker is
    met so the findings can quote a number:

    - LEFT and TOP must be distinctly darker than the interior. Minecraft slots
      are inset, so those two edges carry the shadow in every styling. Not all
      four: BOTTOM and RIGHT are the bevel's lit side and can be lighter.
    - NO edge may be far LIGHTER than the interior. A bevel lifts an edge by
      single digits; a box clipping into a neighbouring slot's bright interior
      lifts it by 70+.
    """
    rw, _ = spec["ref"]
    s = im.width / rw
    margins = []
    for rx, ry in spec["slots"]:
        box = im.crop((round(rx * s), round(ry * s),
                       round((rx + 18) * s), round((ry + 18) * s))).convert("L")
        px = box.resize((18, 18), Image.BILINEAR).load()
        inner = statistics.mean([px[x, y] for x in range(5, 13) for y in range(5, 13)])
        side = lambda pts: statistics.mean([px[x, y] for x, y in pts]) - inner
        left = side([(x, y) for x in (0, 1) for y in range(2, 16)])
        right = side([(x, y) for x in (16, 17) for y in range(2, 16)])
        top = side([(x, y) for y in (0, 1) for x in range(2, 16)])
        bottom = side([(x, y) for y in (16, 17) for x in range(2, 16)])
        if max(left, right, top, bottom) > spec["max_lift"]:
            return 0.0                     # clipping a neighbouring slot
        margins.append(min(-left, -top))   # how dark the shadowed edges are
    return min(margins)


# --- the 1.7 enchanting table, redrawn rather than dropped ------------------
#
# Most packs that fail slot_presence are not badly drawn: they are drawn for
# 1.7, which had ONE item slot at (24,46), between 1.8.9's two. Their own slot
# art is fine, it is just in the wrong place. So when the panel is that layout
# and nothing else, move the pack's own slot to both 1.8.9 positions and cover
# the old one with the pack's own background from just above it, which in the
# 1.7 layout is always bare panel.


def _ink(im: Image.Image, s: float, bg) -> callable:
    """Is the pixel at ref (x, y) drawn on, rather than bare panel? Alpha
    counts: see-through packs draw slots as outlines on transparency, where
    brightness alone reads the panel and the slot interior as the same."""
    px = im.load()
    def at(rx: float, ry: float) -> bool:
        c = px[min(im.width - 1, int(rx * s)), min(im.height - 1, int(ry * s))]
        return max(abs(a - b) for a, b in zip(c, bg)) > 40
    return at


def _single_slot_layout(im: Image.Image, spec: dict) -> bool:
    """One slot box at the 1.7 position, and bare panel where 1.8.9's two
    would add anything new."""
    rw, _ = spec["ref"]
    s = im.width / rw
    hx, hy = spec["heal_from"]
    bg = statistics.median_low([im.getpixel((int((hx + dx) * s), int((hy + dy) * s)))
                                for dx in range(2, 16) for dy in range(2, 16)])
    ink = _ink(im, s, bg)
    ox, oy = spec["old_slot"]
    # The old box's outline: each ref step along its four sides, as the point
    # on the side or the one just inside it, so a 17- or 18-wide box and a
    # one- or two-pixel border all read as a box. (point, step inward)
    edge = [((ox + d, oy), (0, 1)) for d in range(1, 17)] + \
           [((ox + d, oy + 17), (0, -1)) for d in range(1, 17)] + \
           [((ox, oy + d), (1, 0)) for d in range(1, 17)] + \
           [((ox + 17, oy + d), (-1, 0)) for d in range(1, 17)]
    hit = sum(ink(x + .5, y + .5) or ink(x + ix + .5, y + iy + .5)
              for (x, y), (ix, iy) in edge)
    # Where the new slots reach beyond the old one: their outer halves.
    fresh = [(x, y) for y in range(oy + 2, oy + 16)
             for x in list(range(spec["slots"][0][0] + 2, ox - 1))
             + list(range(ox + 19, spec["slots"][1][0] + 16))]
    stray = sum(ink(x, y) for x, y in fresh)
    return hit >= 0.9 * len(edge) and stray <= 0.05 * len(fresh)


def _redraw_two_slots(im: Image.Image, spec: dict) -> Image.Image:
    """The pack's own slot at both 1.8.9 positions, its own panel over the old."""
    rw, _ = spec["ref"]
    s = im.width / rw
    box = lambda x, y: (round(x * s), round(y * s), round((x + 18) * s), round((y + 18) * s))
    slot = im.crop(box(*spec["old_slot"]))
    out = im.copy()
    out.paste(im.crop(box(*spec["heal_from"])), box(*spec["old_slot"])[:2])
    for x, y in spec["slots"]:
        out.paste(slot, box(x, y)[:2])
    return out


def _opaque_coverage(im: Image.Image, spec: dict) -> float:
    hist = im.convert("RGBA").getchannel("A").histogram()
    return 100.0 * sum(c for v, c in enumerate(hist) if v > 128) / (im.width * im.height)


_TESTS = {
    "slot_presence": (_slot_presence, "min_score", "slot contrast"),
    "opaque_coverage": (_opaque_coverage, "min_percent", "opaque coverage"),
}


def conformance(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    kept = dropped = 0
    for spec in load_table("conformance")["predicates"]:
        p: Path = mc / spec["path"]
        if not p.exists():
            continue
        fn, key, label = _TESTS[spec["test"]]
        try:
            with Image.open(p) as im:
                score = fn(im.convert("RGBA"), spec)
        except Exception as exc:          # fail-soft: keep the texture, say why
            ctx.add("conformance", Severity.WARNING,
                    f"could not measure: {exc!r}", spec["path"])
            continue
        limit = spec[key]
        if score >= limit:
            kept += 1
            continue
        repair = spec.get("repair")
        if repair:
            with Image.open(p) as im:
                im = im.convert("RGBA")
                if _single_slot_layout(im, dict(spec, **repair)):
                    _redraw_two_slots(im, dict(spec, **repair)).save(p)
                    kept += 1
                    ctx.add("conformance", Severity.WARNING,
                            f"redrawn: {repair['why']} ({label} {score:.1f} < {limit})",
                            spec["path"])
                    continue
        p.unlink()
        dropped += 1
        # WARNING, not INFO: deleting a texture the pack shipped is the most
        # consequential thing this stage does, and tools/run_corpus.py records
        # only non-INFO findings — at INFO these decisions were invisible to
        # the corpus harness, which produced a wrong per-texture tally when I
        # first checked. It is still a record, never a question for the user.
        ctx.add("conformance", Severity.WARNING,
                f"dropped to vanilla: {label} {score:.1f} < {limit} — {spec['why']}",
                spec["path"])
    ctx.add("conformance", Severity.INFO,
            f"conformance: kept {kept} textures, dropped {dropped}")
