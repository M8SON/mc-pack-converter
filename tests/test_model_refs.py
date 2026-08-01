"""Model JSONs must point at where the textures actually ended up.

A 1.8.9 pack's models reference 'blocks/anvil_base' and 'items/apple'. The
converter renames the texture FILES (textures/blocks -> textures/block, plus
376 flattening renames) but the models kept pointing at the old paths, so every
block and item with a custom model drew the missing-texture placeholder.

Found by in-game testing of 7[9bluefault7], which ships 1595 models: all 578
texture paths they referenced were missing from the output.
"""
import json
from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages import model_refs as mr_mod
from mc_pack_converter.stages.model_refs import model_refs


def _model(root, rel, textures, parent=None):
    p = root / "assets/minecraft" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    d = {"textures": textures}
    if parent:
        d["parent"] = parent
    p.write_text(json.dumps(d))
    return p


def _run(root, table=None):
    ctx = ConversionContext(root=root)
    if table is not None:
        orig = mr_mod.load_table
        mr_mod.load_table = lambda n: table
        try:
            model_refs(ctx)
        finally:
            mr_mod.load_table = orig
    else:
        model_refs(ctx)
    return ctx


def test_folder_rename_is_applied(mini_pack):
    root = mini_pack()
    p = _model(root, "models/block/anvil.json", {"top": "blocks/anvil_base"})
    _run(root, table={})
    assert json.loads(p.read_text())["textures"]["top"] == "block/anvil_base"


def test_items_folder_rename(mini_pack):
    root = mini_pack()
    p = _model(root, "models/item/apple.json", {"layer0": "items/apple"})
    _run(root, table={})
    assert json.loads(p.read_text())["textures"]["layer0"] == "item/apple"


def test_flattening_rename_is_applied(mini_pack):
    root = mini_pack()
    p = _model(root, "models/block/wool.json", {"all": "blocks/wool_colored_black"})
    _run(root, table={"textures/block/wool_colored_black.png":
                      "textures/block/black_wool.png"})
    assert json.loads(p.read_text())["textures"]["all"] == "block/black_wool"


def test_namespaced_reference(mini_pack):
    root = mini_pack()
    p = _model(root, "models/block/x.json", {"all": "minecraft:blocks/stone"})
    _run(root, table={})
    assert json.loads(p.read_text())["textures"]["all"] == "minecraft:block/stone"


def test_variable_references_are_left_alone(mini_pack):
    """'#texture' refers to another key in the same model, not to a file."""
    root = mini_pack()
    p = _model(root, "models/block/x.json", {"all": "#side", "side": "blocks/stone"})
    _run(root, table={})
    t = json.loads(p.read_text())["textures"]
    assert t["all"] == "#side"
    assert t["side"] == "block/stone"


def test_already_modern_reference_is_untouched(mini_pack):
    root = mini_pack()
    p = _model(root, "models/block/x.json", {"all": "block/stone"})
    _run(root, table={})
    assert json.loads(p.read_text())["textures"]["all"] == "block/stone"


def test_parent_is_not_rewritten(mini_pack):
    """parent names a MODEL, whose folder did not change."""
    root = mini_pack()
    p = _model(root, "models/block/x.json", {"all": "blocks/stone"},
               parent="block/cube_all")
    _run(root, table={})
    assert json.loads(p.read_text())["parent"] == "block/cube_all"


def test_unparseable_model_is_skipped(mini_pack):
    root = mini_pack()
    p = root / "assets/minecraft/models/block/bad.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json")
    ctx = _run(root, table={})
    assert p.read_text() == "{not json"
    assert any(f.stage == "model_refs" and f.severity is Severity.WARNING
               for f in ctx.findings)


def test_reports_how_many_it_rewrote(mini_pack):
    root = mini_pack()
    _model(root, "models/block/a.json", {"all": "blocks/stone"})
    _model(root, "models/block/b.json", {"all": "block/stone"})   # already fine
    ctx = _run(root, table={})
    assert any("rewrote 1" in f.message for f in ctx.findings)


# --- blockstates -------------------------------------------------------------

def _blockstate(root, rel, data):
    p = root / "assets/minecraft/blockstates" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))
    return p


def test_bare_blockstate_model_ref_gets_the_block_prefix(mini_pack):
    """1.8.9 resolved blockstate model names relative to models/block/.

    Modern needs the full path, so a bare 'oak_stairs' makes it look for
    models/oak_stairs.json, find nothing, and draw the missing model — a
    magenta cube. 2596 refs in one corpus pack were in this state.
    """
    root = mini_pack()
    p = _blockstate(root, "oak_stairs.json", {"variants": {
        "facing=east": {"model": "oak_stairs"},
        "facing=west": {"model": "oak_stairs", "y": 180, "uvlock": True},
    }})
    _run(root, table={})
    v = json.loads(p.read_text())["variants"]
    assert v["facing=east"]["model"] == "block/oak_stairs"
    assert v["facing=west"]["model"] == "block/oak_stairs"
    assert v["facing=west"]["y"] == 180, "other keys must survive"


def test_blockstate_variant_lists_are_handled(mini_pack):
    root = mini_pack()
    p = _blockstate(root, "x.json", {"variants": {
        "normal": [{"model": "stone_a"}, {"model": "stone_b", "weight": 2}]}})
    _run(root, table={})
    got = [e["model"] for e in json.loads(p.read_text())["variants"]["normal"]]
    assert got == ["block/stone_a", "block/stone_b"]


def test_blockstate_multipart_is_handled(mini_pack):
    root = mini_pack()
    p = _blockstate(root, "fence.json", {"multipart": [
        {"apply": {"model": "fence_post"}},
        {"when": {"north": "true"}, "apply": [{"model": "fence_side"}]}]})
    _run(root, table={})
    d = json.loads(p.read_text())
    assert d["multipart"][0]["apply"]["model"] == "block/fence_post"
    assert d["multipart"][1]["apply"][0]["model"] == "block/fence_side"


def test_already_qualified_blockstate_ref_is_untouched(mini_pack):
    root = mini_pack()
    p = _blockstate(root, "x.json", {"variants": {
        "a": {"model": "block/stone"},
        "b": {"model": "minecraft:block/dirt"}}})
    _run(root, table={})
    v = json.loads(p.read_text())["variants"]
    assert v["a"]["model"] == "block/stone"
    assert v["b"]["model"] == "minecraft:block/dirt"


def test_namespaced_bare_blockstate_ref(mini_pack):
    root = mini_pack()
    p = _blockstate(root, "x.json", {"variants": {"a": {"model": "minecraft:stone"}}})
    _run(root, table={})
    assert json.loads(p.read_text())["variants"]["a"]["model"] == "minecraft:block/stone"
