import zipfile
from pathlib import Path

from mc_pack_converter.job import (
    DEFAULT_TARGET, out_path_beside_source, validate_source,
)


def test_default_target_is_a_real_target():
    from mc_pack_converter.cli import TARGETS
    assert DEFAULT_TARGET in TARGETS


def test_validate_source_accepts_a_directory(mini_pack):
    assert validate_source(mini_pack()) is None


def test_validate_source_accepts_a_real_zip(tmp_path):
    p = tmp_path / "ok.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("pack.mcmeta", "{}")
    assert validate_source(p) is None


def test_validate_source_reports_a_missing_pack(tmp_path):
    p = tmp_path / "nope.zip"
    assert validate_source(p) == f"no such pack: {p}"


def test_validate_source_rejects_a_renamed_rar(tmp_path):
    p = tmp_path / "broken.zip"
    p.write_bytes(b"Rar!\x1a\x07\x00 not a zip at all")
    assert validate_source(p) == f"not a readable zip: {p}"


def test_out_path_beside_source_uses_the_source_folder(tmp_path):
    src = tmp_path / "Downloads" / "MyPack.zip"
    assert out_path_beside_source(src, "26.2") == tmp_path / "Downloads" / "MyPack-26.2.zip"


def test_out_path_beside_source_handles_a_folder_source(tmp_path):
    src = tmp_path / "packs" / "My Pack"
    assert out_path_beside_source(src, "26.1.2") == tmp_path / "packs" / "My Pack-26.1.2.zip"


def test_run_job_writes_reports_beside_the_zip(mini_pack, tmp_path):
    from mc_pack_converter.job import run_job
    root = mini_pack()
    out = tmp_path / "out" / "MyPack-26.2.zip"
    out.parent.mkdir()
    result = run_job(root, out, "26.2")
    assert result.out_path == out
    assert out.exists()
    assert result.wrote_zip is True
    assert result.reports["report"] == out.parent / "MyPack-26.2-report.md"
    assert result.reports["null-textures"] == out.parent / "MyPack-26.2-null-textures.md"
    assert result.reports["report"].read_text().startswith("# Conversion Report")


def test_run_job_report_only_writes_reports_but_no_zip(mini_pack, tmp_path):
    from mc_pack_converter.job import run_job
    root = mini_pack()
    out = tmp_path / "MyPack-26.2.zip"
    result = run_job(root, out, "26.2", report_only=True)
    assert result.wrote_zip is False
    assert not out.exists()
    assert result.reports["report"].exists()


def test_run_job_counts_findings_by_severity(mini_pack, tmp_path):
    from mc_pack_converter.pipeline import Severity
    from mc_pack_converter.job import run_job
    root = mini_pack()
    result = run_job(root, tmp_path / "o.zip", "26.2")
    assert set(result.counts) == set(Severity)
    assert sum(result.counts.values()) == len(result.ctx.findings)


def test_run_job_flags_errors(mini_pack, tmp_path):
    from mc_pack_converter.job import run_job
    bad = mini_pack({"assets/minecraft/textures/block/stone.png": b""})
    result = run_job(bad, tmp_path / "bad.zip", "26.2")
    assert result.has_errors is True


def test_run_job_reports_no_errors_on_a_clean_pack(mini_pack, tmp_path):
    from mc_pack_converter.job import run_job
    result = run_job(mini_pack(), tmp_path / "clean.zip", "26.2")
    assert result.has_errors is False


def test_run_job_forwards_every_stage_to_on_stage(mini_pack, tmp_path):
    from mc_pack_converter.stages import STAGES
    from mc_pack_converter.job import run_job
    seen = []
    run_job(mini_pack(), tmp_path / "o.zip", "26.2",
            on_stage=lambda name, i, total: seen.append((name, i, total)))
    assert [s[0] for s in seen] == [name for name, _ in STAGES]
    assert seen[-1][1] == len(STAGES)


def test_run_job_writes_reports_by_default(mini_pack, tmp_path):
    from mc_pack_converter.job import run_job
    out = tmp_path / "out" / "MyPack-26.2.zip"
    out.parent.mkdir()
    result = run_job(mini_pack(), out, "26.2")
    assert set(result.reports) == {"report", "null-textures"}
    for path in result.reports.values():
        assert path.exists()


def test_write_reports_false_writes_no_files_but_keeps_the_text(mini_pack, tmp_path):
    from mc_pack_converter.job import run_job
    out = tmp_path / "out" / "MyPack-26.2.zip"
    out.parent.mkdir()
    result = run_job(mini_pack(), out, "26.2", write_reports=False)
    assert result.reports == {}
    assert set(result.report_texts) == {"report", "null-textures"}
    assert result.report_texts["report"].strip()
    assert not list(out.parent.glob("*.md"))
