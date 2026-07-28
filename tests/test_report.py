from mc_pack_converter.pipeline import Finding, Severity
from mc_pack_converter.report import render_conversion_report, render_null_texture_report

def test_conversion_report_groups_by_stage():
    fs = [Finding("clean", Severity.INFO, "removed 5 junk files"),
          Finding("validate", Severity.WARNING, "bad mcmeta", "block/fire_0.png")]
    out = render_conversion_report(fs)
    assert "## clean" in out and "removed 5 junk files" in out
    assert "block/fire_0.png" in out

def test_null_texture_report_zero_when_clean():
    assert "0 null-texture risks" in render_null_texture_report([])

def test_null_texture_report_lists_validate_issues():
    fs = [Finding("validate", Severity.ERROR, "corrupt png", "item/apple.png"),
          Finding("clean", Severity.INFO, "ignore me")]
    out = render_null_texture_report(fs)
    assert "corrupt png" in out and "item/apple.png" in out
    assert "ignore me" not in out
