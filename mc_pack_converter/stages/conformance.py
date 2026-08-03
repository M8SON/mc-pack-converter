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
    """Lowest border-vs-interior luminance contrast across the expected slots."""
    rw, _ = spec["ref"]
    s = im.width / rw
    scores = []
    for rx, ry in spec["slots"]:
        box = im.crop((round(rx * s), round(ry * s),
                       round((rx + 18) * s), round((ry + 18) * s))).convert("L")
        px = box.resize((18, 18), Image.BILINEAR).load()
        ring = [px[x, y] for x in range(18) for y in range(18)
                if x < 2 or y < 2 or x > 15 or y > 15]
        inner = [px[x, y] for x in range(4, 14) for y in range(4, 14)]
        scores.append(abs(statistics.mean(ring) - statistics.mean(inner)))
    return min(scores)


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
        p.unlink()
        dropped += 1
        ctx.add("conformance", Severity.INFO,
                f"dropped to vanilla: {label} {score:.1f} < {limit} — {spec['why']}",
                spec["path"])
    ctx.add("conformance", Severity.INFO,
            f"conformance: kept {kept} textures, dropped {dropped}")
