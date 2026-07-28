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


def test_missing_files_are_noop(mini_pack, monkeypatch):
    root = mini_pack()
    monkeypatch.setattr(drop_mod, "load_table",
                        lambda n: {"drop": ["textures/entity/chest/normal.png"]})
    ctx = ConversionContext(root=root)
    drop_textures(ctx)  # must not raise
    assert any(f.stage == "drop" and f.severity is Severity.INFO for f in ctx.findings)
