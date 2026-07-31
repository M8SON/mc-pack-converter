from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages import prune_atlases as prune_mod
from mc_pack_converter.stages.prune_atlases import prune_atlases

WIDGETS = "assets/minecraft/textures/gui/widgets.png"
OPTIONS = "assets/minecraft/textures/gui/options_background.png"
TABLE = {"dead": ["textures/gui/widgets.png", "textures/gui/options_background.png"]}


def _put(root, rel, data=b"x"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def test_removes_a_dead_atlas(mini_pack, monkeypatch):
    root = mini_pack()
    _put(root, WIDGETS, b"0" * 2048)
    monkeypatch.setattr(prune_mod, "load_table", lambda n: TABLE)
    ctx = ConversionContext(root=root)
    prune_atlases(ctx)
    assert not (root / WIDGETS).exists()
    assert any(f.stage == "prune_atlases" and "removed 1" in f.message
               for f in ctx.findings)


def test_keeps_a_path_the_slicer_wrote(mini_pack, monkeypatch):
    """The guard that matters: three dead entries are also slicer copy() outputs.

    A copy record has input == output, so the file in the output tree is the
    sprite the slice stage produced — deleting it would remove live art.
    """
    root = mini_pack()
    _put(root, OPTIONS)
    _put(root, WIDGETS)
    monkeypatch.setattr(prune_mod, "load_table", lambda n: TABLE)
    ctx = ConversionContext(root=root)
    ctx.sliced.append((OPTIONS, OPTIONS))       # slicer copied it to itself
    prune_atlases(ctx)
    assert (root / OPTIONS).exists()            # kept
    assert not (root / WIDGETS).exists()        # still pruned


def test_removes_the_sibling_mcmeta(mini_pack, monkeypatch):
    root = mini_pack()
    _put(root, WIDGETS)
    _put(root, WIDGETS + ".mcmeta", b"{}")
    monkeypatch.setattr(prune_mod, "load_table", lambda n: TABLE)
    prune_atlases(ConversionContext(root=root))
    assert not (root / (WIDGETS + ".mcmeta")).exists()


def test_missing_files_are_noop(mini_pack, monkeypatch):
    root = mini_pack()
    monkeypatch.setattr(prune_mod, "load_table", lambda n: TABLE)
    ctx = ConversionContext(root=root)
    prune_atlases(ctx)  # must not raise
    assert any(f.stage == "prune_atlases" and f.severity is Severity.INFO
               for f in ctx.findings)


def test_shipped_table_lists_only_paths_modern_cannot_read():
    """Spot-check the real table against what the slice stage consumes."""
    import json
    from pathlib import Path
    from mc_pack_converter.data import load_table
    dead = set(load_table("dead_atlases")["dead"])
    for known in ("textures/gui/widgets.png", "textures/gui/icons.png",
                  "textures/particle/particles.png",
                  "textures/painting/paintings_kristoffer_zetterstrand.png"):
        assert known in dead
    # inventory.png and anvil.png ARE still read by 26.x — never prune them
    for live in ("textures/gui/container/inventory.png",
                 "textures/gui/container/anvil.png"):
        assert live not in dead
    # every entry must be a slice input; pruning something we never sliced
    # would be deleting art the pack still needs
    slices = json.loads((Path(__file__).parent.parent / "mc_pack_converter"
                         / "data" / "slices.json").read_text())
    inputs = {r["input"].split("assets/minecraft/")[1] for r in slices}
    assert dead <= inputs
