from PIL import Image, ImageDraw
from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages.conformance import conformance

ENCH = "assets/minecraft/textures/gui/container/enchanting_table.png"
TABS = "assets/minecraft/textures/gui/container/creative_inventory/tabs.png"


def _panel(root, slots, size=256):
    """A 1.8.9-style enchanting panel; `slots` are ref coords to draw a box at."""
    p = root / ENCH
    p.parent.mkdir(parents=True, exist_ok=True)
    s = size // 256
    im = Image.new("RGBA", (size, size), (110, 110, 110, 255))
    d = ImageDraw.Draw(im)
    for rx, ry in slots:                      # dark border, light interior
        d.rectangle([rx * s, ry * s, (rx + 17) * s, (ry + 17) * s], fill=(20, 20, 20, 255))
        d.rectangle([(rx + 2) * s, (ry + 2) * s, (rx + 15) * s, (ry + 15) * s],
                    fill=(200, 200, 200, 255))
    im.save(p)
    return p


def test_both_slots_present_keeps_the_texture(mini_pack):
    """82 of the 173 corpus packs are in this case and used to lose the art."""
    root = mini_pack()
    p = _panel(root, [(14, 46), (34, 46)])
    conformance(ConversionContext(root=root))
    assert p.exists()


def test_missing_slot_drops_to_vanilla(mini_pack):
    """M8SON's case: one slot where 1.8.9 has two."""
    root = mini_pack()
    p = _panel(root, [(14, 46)])
    ctx = ConversionContext(root=root)
    conformance(ctx)
    assert not p.exists()
    assert any(f.stage == "conformance" and "slot contrast" in f.message
               for f in ctx.findings)


def test_offset_slots_drop_to_vanilla(mini_pack):
    """The predicate asks 'are the slots WHERE 1.8.9 PUTS THEM'."""
    root = mini_pack()
    p = _panel(root, [(60, 90), (80, 90)])
    conformance(ConversionContext(root=root))
    assert not p.exists()


def test_the_measured_number_is_reported(mini_pack):
    """Mason's rule: warnings are a record of what it did, never a question."""
    root = mini_pack()
    _panel(root, [(14, 46)])
    ctx = ConversionContext(root=root)
    conformance(ctx)
    msg = next(f.message for f in ctx.findings if "dropped to vanilla" in f.message)
    assert "< 3.5" in msg


def test_predicate_is_resolution_independent(mini_pack):
    """Scores are proportional to `ref`, so a 4x pack is judged like a 1x one."""
    root = mini_pack()
    p = _panel(root, [(14, 46), (34, 46)], size=1024)
    conformance(ConversionContext(root=root))
    assert p.exists()


def test_transparent_creative_tab_is_dropped(mini_pack):
    root = mini_pack()
    p = root / TABS
    p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))          # ~6% opaque outline
    ImageDraw.Draw(im).rectangle([0, 0, 255, 7], fill=(200, 0, 0, 255))
    im.save(p)
    conformance(ConversionContext(root=root))
    assert not p.exists()


def test_solid_creative_tab_is_kept(mini_pack):
    root = mini_pack()
    p = root / TABS
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (256, 256), (80, 80, 80, 255)).save(p)
    conformance(ConversionContext(root=root))
    assert p.exists()


def test_unreadable_texture_is_kept_not_guessed_at(mini_pack):
    root = mini_pack()
    p = root / ENCH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"not a png")
    ctx = ConversionContext(root=root)
    conformance(ctx)
    assert p.exists()
    assert any(f.severity is Severity.WARNING for f in ctx.findings)
