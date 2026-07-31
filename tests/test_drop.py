from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages import drop as drop_mod
from mc_pack_converter.stages.drop import drop_textures


def test_drops_listed_textures(mini_pack, monkeypatch):
    root = mini_pack({
        "assets/minecraft/textures/entity/chest/normal.png": b"x",
        "assets/minecraft/textures/entity/chest/normal_double.png": b"x",
        "assets/minecraft/textures/block/stone.png": b"keep",
    })
    monkeypatch.setattr(drop_mod, "load_table", lambda n: {"drop": [
        "textures/entity/chest/normal.png",
        "textures/entity/chest/normal_double.png",
    ]})
    ctx = ConversionContext(root=root)
    drop_textures(ctx)
    mc = root / "assets/minecraft"
    assert not (mc / "textures/entity/chest/normal.png").exists()
    assert not (mc / "textures/entity/chest/normal_double.png").exists()
    assert (mc / "textures/block/stone.png").exists()  # untouched
    assert any(f.stage == "drop" and "2" in f.message for f in ctx.findings)


def test_anvil_is_not_dropped():
    """Guard the 2026-07-31 correction (docs/known-issues.md #4).

    It was dropped on the theory that its slot layout had drifted. It had not:
    the 176x166 panel is 99.9% identical between 1.8.9 and modern, and the
    pack's own anvil is a pixel-exact structural match to both. Dropping it
    discarded an 87%-custom GUI for nothing.
    """
    from mc_pack_converter.data import load_table
    assert "textures/gui/container/anvil.png" not in set(load_table("drop_list")["drop"])


def test_enchanting_table_is_dropped():
    """Guard docs/known-issues.md #4 — dropped, but NOT for the recorded reason.

    The pack's own art predates 1.8: one item slot where 1.8.9 has two (lapis
    was added to enchanting in 1.8), in a different position, and no dark
    level-number caps on the bars. It never matched the 1.8.9 layout it ships
    as, so it renders wrong on any modern version.
    """
    from mc_pack_converter.data import load_table
    assert "textures/gui/container/enchanting_table.png" in set(
        load_table("drop_list")["drop"])


def test_villager_gui_is_dropped():
    """Guard docs/known-issues.md #5.

    The only GUI whose modern reference canvas differs from 1.8.9's: 240x166 on
    256x256 becomes 276x166 on 512x256. Same filename in both eras and no slice
    record reads it, so without this entry a 1.8.9 villager.png passes straight
    through and modern samples it at scale (1.0, 2.0) — squashed and misplaced.
    """
    from mc_pack_converter.data import load_table
    assert "textures/gui/container/villager.png" in set(load_table("drop_list")["drop"])


def test_missing_files_are_noop(mini_pack, monkeypatch):
    root = mini_pack()
    monkeypatch.setattr(drop_mod, "load_table",
                        lambda n: {"drop": ["textures/entity/chest/normal.png"]})
    ctx = ConversionContext(root=root)
    drop_textures(ctx)  # must not raise
    assert any(f.stage == "drop" and f.severity is Severity.INFO for f in ctx.findings)
