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


def test_anvil_and_enchanting_table_are_not_dropped():
    """Guard the 2026-07-31 correction (docs/known-issues.md #4).

    Both were dropped on the theory that their slot layout had drifted. It had
    not: the 176x166 panel is 99.9% identical between 1.8.9 and modern, and the
    slicer's read boxes land exactly on 1.8.9's art. Dropping them discarded the
    pack's custom GUIs — 87% and 37% custom respectively — for nothing.
    """
    from mc_pack_converter.data import load_table
    dropped = set(load_table("drop_list")["drop"])
    assert "textures/gui/container/anvil.png" not in dropped
    assert "textures/gui/container/enchanting_table.png" not in dropped


def test_missing_files_are_noop(mini_pack, monkeypatch):
    root = mini_pack()
    monkeypatch.setattr(drop_mod, "load_table",
                        lambda n: {"drop": ["textures/entity/chest/normal.png"]})
    ctx = ConversionContext(root=root)
    drop_textures(ctx)  # must not raise
    assert any(f.stage == "drop" and f.severity is Severity.INFO for f in ctx.findings)
