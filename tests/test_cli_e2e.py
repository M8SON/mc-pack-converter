from pathlib import Path
import zipfile

import pytest

from mc_pack_converter.cli import convert, main

PACK = Path("/home/daedalus/linux/M8SON 1.8 PVP PACK")


@pytest.mark.skipif(not PACK.exists(), reason="golden pack absent")
def test_golden_conversion(tmp_path):
    out = tmp_path / "converted.zip"
    ctx = convert(PACK, out, target="26.2", report_only=False)

    assert out.exists()

    from mc_pack_converter.pipeline import Severity

    errors = [f for f in ctx.findings if f.severity is Severity.ERROR]
    assert errors == [], f"unexpected errors: {errors}"

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        assert "assets/minecraft/textures/block/fire_0.png" in names
        assert any(n.startswith("assets/minecraft/optifine/sky/world0/") for n in names)
        assert "conversion-report.md" in names

        import json

        meta = json.loads(zf.read("pack.mcmeta"))
        assert meta["pack"]["min_format"] == 88  # 26.2, modern min/max schema
        assert meta["pack"]["max_format"] == 88


def test_convert_cleans_temp_dir(mini_pack, tmp_path):
    root = mini_pack()
    out = tmp_path / "converted.zip"
    ctx = convert(root, out, target="26.2", report_only=False)
    assert not ctx.root.exists()


def test_main_returns_1_on_error(mini_pack, tmp_path):
    bad_root = mini_pack({"assets/minecraft/textures/block/stone.png": b""})
    bad_out = tmp_path / "bad.zip"
    assert main(["convert", str(bad_root), "-o", str(bad_out)]) == 1


def test_main_returns_0_on_clean_pack(mini_pack, tmp_path):
    clean_root = mini_pack()
    clean_out = tmp_path / "clean.zip"
    assert main(["convert", str(clean_root), "-o", str(clean_out)]) == 0


def test_contact_sheet_written_beside_archive(tmp_path, mini_pack):
    from PIL import Image
    root = mini_pack()
    atlas = root / "assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png"
    atlas.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (256, 256), (10, 120, 200, 255)).save(atlas)
    out = tmp_path / "converted.zip"
    convert(root, out, target="26.1.2", report_only=False)
    sheet = tmp_path / "converted-slices.png"
    assert sheet.exists(), "contact sheet not written next to the archive"
    with zipfile.ZipFile(out) as zf:
        assert "converted-slices.png" not in zf.namelist()
        assert not any(n.endswith("-slices.png") for n in zf.namelist())


def test_no_contact_sheet_when_nothing_sliced(tmp_path, mini_pack):
    root = mini_pack()
    out = tmp_path / "plain.zip"
    convert(root, out, target="26.1.2", report_only=False)
    assert not (tmp_path / "plain-slices.png").exists()


def test_contact_sheet_failure_does_not_abort_conversion(tmp_path, mini_pack, monkeypatch):
    # The archive is already written by the time the sheet is rendered; a
    # cosmetic review artifact must never fail an otherwise-successful
    # conversion (fail-soft).
    from mc_pack_converter import cli as cli_mod
    from mc_pack_converter.pipeline import Severity

    def _boom(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(cli_mod, "build_contact_sheet", _boom)
    root = mini_pack()
    out = tmp_path / "converted.zip"
    ctx = convert(root, out, target="26.1.2", report_only=False)
    assert out.exists()
    assert any(f.severity is Severity.WARNING and "contact sheet" in f.message
               for f in ctx.findings)


def test_default_out_path_from_zip_source():
    from mc_pack_converter.cli import default_out_path
    assert default_out_path(Path("/packs/MyPack.zip"), "26.2") == Path("MyPack-26.2.zip")


def test_default_out_path_from_directory_source():
    from mc_pack_converter.cli import default_out_path
    assert default_out_path(Path("/packs/My Pack"), "26.1.2") == Path("My Pack-26.1.2.zip")


def test_default_out_path_ignores_source_directory(tmp_path):
    # The output belongs in the cwd, not next to the source.
    from mc_pack_converter.cli import default_out_path
    assert default_out_path(Path("/somewhere/else/P.zip"), "26.2").parent == Path(".")


def test_main_uses_derived_name_when_no_dash_o(mini_pack, monkeypatch, tmp_path):
    root = mini_pack()
    monkeypatch.chdir(tmp_path)
    assert main(["convert", str(root)]) == 0
    assert (tmp_path / "pack-26.2.zip").exists()


def test_main_explicit_out_wins(mini_pack, tmp_path):
    root = mini_pack()
    out = tmp_path / "chosen.zip"
    assert main(["convert", str(root), "-o", str(out)]) == 0
    assert out.exists()


def test_every_convert_argument_is_documented(capsys):
    # Read the help the user actually sees rather than argparse internals.
    from mc_pack_converter.cli import build_parser
    with pytest.raises(SystemExit):
        build_parser().parse_args(["convert", "--help"])
    out = capsys.readouterr().out
    for flag in ("source", "--out", "--target", "--report-only"):
        assert flag in out
    # every flag line carries prose, not just the flag name
    assert "current directory" in out          # --out
    assert "without producing" in out          # --report-only


def test_help_lists_the_valid_targets(capsys):
    from mc_pack_converter.cli import build_parser
    with pytest.raises(SystemExit):
        build_parser().parse_args(["convert", "--help"])
    out = capsys.readouterr().out
    for version in ("1.8.9", "26.1", "26.1.2", "26.2"):
        assert version in out


def test_invalid_target_exits_without_converting(mini_pack, tmp_path):
    root = mini_pack()
    out = tmp_path / "never.zip"
    with pytest.raises(SystemExit) as exc:
        main(["convert", str(root), "-o", str(out), "--target", "1.21"])
    assert exc.value.code != 0
    assert not out.exists()


def test_targets_come_from_the_data_table():
    # The list must not drift from pack_format.json.
    from mc_pack_converter.cli import TARGETS
    from mc_pack_converter.data import load_table
    assert set(TARGETS) == set(load_table("pack_format"))


def test_on_stage_called_once_per_stage(mini_pack, tmp_path):
    from mc_pack_converter.stages import STAGES
    seen = []
    root = mini_pack()
    convert(root, tmp_path / "o.zip", target="26.2", report_only=False,
            on_stage=lambda name, i, total: seen.append((name, i, total)))
    assert [s[0] for s in seen] == [name for name, _ in STAGES]
    assert seen[0][1] == 1
    assert seen[-1][1] == len(STAGES)
    assert all(s[2] == len(STAGES) for s in seen)


def test_convert_still_works_without_a_callback(mini_pack, tmp_path):
    root = mini_pack()
    out = tmp_path / "o.zip"
    convert(root, out, target="26.2", report_only=False)
    assert out.exists()


def test_default_run_prints_summary_not_reports(mini_pack, tmp_path, capsys, monkeypatch):
    root = mini_pack()
    monkeypatch.chdir(tmp_path)
    assert main(["convert", str(root)]) == 0
    out = capsys.readouterr().out
    assert "pack-26.2.zip" in out
    assert "# Conversion Report" not in out
    assert "# Null-Texture Safety Report" not in out


def test_verbose_prints_the_full_reports(mini_pack, tmp_path, capsys, monkeypatch):
    root = mini_pack()
    monkeypatch.chdir(tmp_path)
    assert main(["convert", str(root), "-v"]) == 0
    out = capsys.readouterr().out
    assert "# Conversion Report" in out
    assert "# Null-Texture Safety Report" in out


def test_report_only_summary_does_not_claim_zip_written(mini_pack, tmp_path, capsys, monkeypatch):
    root = mini_pack()
    monkeypatch.chdir(tmp_path)
    assert main(["convert", str(root), "--report-only"]) == 0
    out = capsys.readouterr().out
    assert "wrote" not in out
    assert not (tmp_path / "pack-26.2.zip").exists()
    assert (tmp_path / "pack-26.2-report.md").exists()
    assert (tmp_path / "pack-26.2-null-textures.md").exists()
