"""Tests for the slicer-source parser in tools/gen_slices.py.

tools/ is a script directory, not a package, so load it by path.
"""
import importlib.util
from pathlib import Path

import pytest

GEN = Path(__file__).parent.parent / "tools" / "gen_slices.py"


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("gen_slices", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_as_int_evaluates_java_arithmetic(gen):
    assert gen.as_int("0 * 2") == 0
    assert gen.as_int(" 3 * 2 ") == 6
    assert gen.as_int("16") == 16


def test_as_int_rejects_non_arithmetic(gen):
    with pytest.raises(ValueError):
        gen.as_int("open('/etc/passwd')")


def test_particle_short_form(gen):
    # particle("critical_hit", 1, 4) -> 8px cell at column 1, row 4,
    # restated against a 128x128 reference (see spec: 1.13 grew the canvas
    # but kept the 8px cell, so a 1.8.9 atlas is 128x128 at the same coords).
    rec = gen.parse_helper_output(
        'particle("critical_hit", 1, 4)',
        "assets/minecraft/textures/particle/particles.png")
    assert rec == {
        "input": "assets/minecraft/textures/particle/particles.png",
        "output": "assets/minecraft/textures/particle/critical_hit.png",
        "box": [8, 32, 8, 8, 256, 256], "op": "crop"}


def test_particle_with_width_and_height(gen):
    rec = gen.parse_helper_output(
        'particle("flash", 4, 2, 4, 4)',
        "assets/minecraft/textures/particle/particles.png")
    assert rec["box"] == [32, 16, 32, 32, 256, 256]
    assert rec["output"] == "assets/minecraft/textures/particle/flash.png"


def test_particle_with_offsets(gen):
    # particle("bubble_pop_1", 1 * 2, 16, 0, 3, 2, 2)
    rec = gen.parse_helper_output(
        'particle("bubble_pop_1", 1 * 2, 16, 0, 3, 2, 2)',
        "assets/minecraft/textures/particle/particles.png")
    assert rec["box"] == [16, 131, 16, 16, 256, 256]


def test_painting_uses_16px_cells_on_256_reference(gen):
    rec = gen.parse_helper_output(
        'painting("donkey_kong", 12, 7, 4, 3)',
        "assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png")
    assert rec == {
        "input": "assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png",
        "output": "assets/minecraft/textures/painting/donkey_kong.png",
        "box": [192, 112, 64, 48, 256, 256], "op": "crop"}


def test_explosion_uses_32px_cells_on_128_reference(gen):
    rec = gen.parse_helper_output(
        'explosion("explosion_9", 1, 2)',
        "assets/minecraft/textures/entity/explosion.png")
    assert rec == {
        "input": "assets/minecraft/textures/entity/explosion.png",
        "output": "assets/minecraft/textures/particle/explosion_9.png",
        "box": [32, 64, 32, 32, 128, 128], "op": "crop"}


def test_effect_and_sweep_are_not_ported(gen):
    # effect(): the 18px grid inside inventory.png was rearranged in 1.9, so
    # the slicer's coordinates would mis-map a 1.8.9 pack. sweep(): needs the
    # slicer's SQUARE post-op and the texture is 1.9+. Both out of scope.
    assert gen.parse_helper_output(
        'effect("speed", 0, 0)',
        "assets/minecraft/textures/gui/container/inventory.png") is None
    assert gen.parse_helper_output(
        "sweep(3, 3, 0)", "assets/minecraft/textures/entity/sweep.png") is None
    assert gen.SKIPPED_HELPERS["effect"] >= 1
    assert gen.SKIPPED_HELPERS["sweep"] >= 1


def test_parse_box_resolves_b256_and_b128(gen):
    assert gen.parse_box("b256(8 * 1, 8 * 2, 8, 8)") == [8, 16, 8, 8, 256, 256]
    assert gen.parse_box("b128(32 * 3, 32 * 1, 32, 32)") == [96, 32, 32, 32, 128, 128]
    assert gen.parse_box("new Box(0, 0, 182, 22, 256, 256)") == [0, 0, 182, 22, 256, 256]


def test_particles_input_is_rebased_to_128(gen):
    # Whole-input pass: every record cut from particles.png ends up on a
    # 128x128 reference, including the bare fishing_hook SimpleOutputFile.
    entry = '''input("assets/minecraft/textures/particle/particles.png",
        particle("critical_hit", 1, 4),
        new SimpleOutputFile("assets/minecraft/textures/entity/fishing_hook.png", b256(8 * 1, 8 * 2, 8, 8))
    )'''
    recs = gen.parse_entry(entry)
    assert len(recs) == 2
    assert all(r["box"][4:] == [128, 128] for r in recs)
    by_out = {r["output"]: r for r in recs}
    assert by_out["assets/minecraft/textures/particle/critical_hit.png"]["box"] == \
        [8, 32, 8, 8, 128, 128]
    assert by_out["assets/minecraft/textures/entity/fishing_hook.png"]["box"] == \
        [8, 16, 8, 8, 128, 128]


def test_painting_input_is_not_rebased(gen):
    entry = '''input("assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png",
        painting("kebab", 0, 0, 1, 1)
    )'''
    recs = gen.parse_entry(entry)
    assert recs[0]["box"] == [0, 0, 16, 16, 256, 256]


def test_full_1_14_source_record_counts(gen):
    recs = gen.parse_file(GEN.parent / "slicer_src" / "slicer_1.14.java")
    outs = [r["output"] for r in recs]
    assert len(recs) == 134           # 27 painting + 90 particle + 16 explosion + 1 hook
    assert sum(1 for o in outs if "/textures/painting/" in o) == 27
    assert sum(1 for o in outs if "/textures/particle/" in o) == 106  # 90 + 16
    assert "assets/minecraft/textures/entity/fishing_hook.png" in outs
    assert not any("/textures/mob_effect/" in o for o in outs)
    assert not any("sweep_" in o for o in outs)
    # every particles.png record sits on the 128 reference
    assert all(r["box"][4:] == [128, 128] for r in recs
               if r["input"].endswith("particle/particles.png"))


def test_shipped_slices_table_contains_1_14_records():
    """Guard against regenerating slices.json without the 1.14 records."""
    import json
    from pathlib import Path
    table = json.loads(
        (Path(__file__).parent.parent / "mc_pack_converter" / "data"
         / "slices.json").read_text())
    assert len(table) == 543
    by_out = {r["output"]: r for r in table}
    assert by_out["assets/minecraft/textures/particle/critical_hit.png"]["box"] == \
        [8, 32, 8, 8, 128, 128]
    assert by_out["assets/minecraft/textures/painting/kebab.png"]["box"] == \
        [0, 0, 16, 16, 256, 256]
    assert by_out["assets/minecraft/textures/particle/explosion_0.png"]["box"] == \
        [0, 0, 32, 32, 128, 128]
    assert "assets/minecraft/textures/entity/fishing_hook.png" in by_out
    assert not any("/textures/mob_effect/" in o for o in by_out)
