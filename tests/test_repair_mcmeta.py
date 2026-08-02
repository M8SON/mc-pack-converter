import json
from PIL import Image
from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages.repair_mcmeta import repair_mcmeta

ITEM = "assets/minecraft/textures/item"

# The real file that made Minecraft drop 9XethaFaith's ender pearl: a trailing
# comma before ']' and a fractional frametime.
REAL = ('{\r\n  "animation": {\r\n    "frametime": 1.5,\n    "frames": [\r\n'
        '      0,\n      1,\n      2,   ]\r\n  }\r\n}\r\n')


def _strip(root, name="ender_pearl", frames=3, meta=REAL):
    d = root / ITEM
    d.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (16, 16 * frames), (10, 20, 30, 255)).save(d / f"{name}.png")
    (d / f"{name}.png.mcmeta").write_text(meta)
    return d


def test_trailing_comma_is_repaired(mini_pack):
    root = mini_pack()
    d = _strip(root)
    ctx = ConversionContext(root=root)
    repair_mcmeta(ctx)
    data = json.loads((d / "ender_pearl.png.mcmeta").read_text())   # parses now
    assert data["animation"]["frames"] == [0, 1, 2]
    assert (d / "ender_pearl.png").exists(), "the texture must survive a repair"


def test_fractional_frametime_becomes_an_integer(mini_pack):
    """The animation codec requires an int; 1.5 is rejected outright."""
    root = mini_pack()
    d = _strip(root)
    repair_mcmeta(ConversionContext(root=root))
    ft = json.loads((d / "ender_pearl.png.mcmeta").read_text())["animation"]["frametime"]
    assert isinstance(ft, int) and ft >= 1


def test_unrepairable_mcmeta_drops_the_texture(mini_pack):
    """Convert or drop — never ship a file that makes the game throw.

    The strip is dropped with its metadata: without valid frame data it is not
    a still image, and shipping it as one sprite warps the item atlas.
    """
    root = mini_pack()
    d = _strip(root, meta='{"animation": {{{ totally broken')
    ctx = ConversionContext(root=root)
    repair_mcmeta(ctx)
    assert not (d / "ender_pearl.png.mcmeta").exists()
    assert not (d / "ender_pearl.png").exists()
    assert any(f.severity is Severity.WARNING and "unrepairable" in f.message
               for f in ctx.findings)


def test_valid_mcmeta_is_left_byte_identical(mini_pack):
    root = mini_pack()
    good = '{"animation": {"frametime": 2}}'
    d = _strip(root, meta=good)
    repair_mcmeta(ConversionContext(root=root))
    assert (d / "ender_pearl.png.mcmeta").read_text() == good


def test_single_quoted_value_is_repaired_to_a_boolean(mini_pack):
    """Conquest's real glowstone.png.mcmeta.

    `'true'` is not JSON, so the file was unparseable and the whole animated
    glowstone texture was being dropped. Quoting it correctly is not enough
    either: the animation codec wants a boolean, not the string "true".
    """
    root = mini_pack()
    d = _strip(root, name="glowstone",
               meta='{\n  "animation": {\n    "frametime": 2,\n'
                    "    \"interpolate\": 'true'\n  }\n}\n")
    ctx = ConversionContext(root=root)
    repair_mcmeta(ctx)
    assert (d / "glowstone.png").exists(), "the texture must survive"
    anim = json.loads((d / "glowstone.png.mcmeta").read_text())["animation"]
    assert anim["interpolate"] is True
    assert anim["frametime"] == 2
