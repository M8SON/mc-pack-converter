import zipfile
from pathlib import Path
import pytest
from mc_pack_converter.pipeline import ConversionContext, Severity


def _result(tmp_path, findings=()):
    from mc_pack_converter.job import JobResult
    ctx = ConversionContext(root=tmp_path)
    for finding in findings:
        if len(finding) == 3:
            stage, sev, msg = finding
            ctx.add(stage, sev, msg)
        else:
            stage, sev, msg, path = finding
            ctx.add(stage, sev, msg, path)
    out = tmp_path / "MyPack-26.1.2.zip"
    out.write_bytes(b"")
    return JobResult(ctx=ctx, out_path=out, reports={}, report_texts={},
                     wrote_zip=True)


def test_the_model_names_the_output(tmp_path):
    from mc_pack_converter.webui.report import build_model
    m = build_model(_result(tmp_path), sheet={"sections": [], "total": 0})
    assert m["out_name"] == "MyPack-26.1.2.zip"
    assert m["out_path"] == str(tmp_path / "MyPack-26.1.2.zip")


def test_findings_lead_with_the_loud_ones(tmp_path):
    """408 of 413 findings on the reference pack are INFO. Sorting by
    severity is what makes the 5 that matter findable."""
    from mc_pack_converter.webui.report import build_model
    r = _result(tmp_path, [("validate", Severity.INFO, "fine"),
                           ("conformance", Severity.WARNING, "look at me")])
    m = build_model(r, sheet={"sections": [], "total": 0})
    assert [f["severity"] for f in m["findings"]] == ["warning", "info"]
    assert m["counts"]["info"] == 1


def test_the_update_notice_is_absent_by_default(tmp_path):
    from mc_pack_converter.webui.report import build_model
    m = build_model(_result(tmp_path), sheet={"sections": [], "total": 0})
    assert m["update"] is None


def test_the_update_notice_is_carried_when_given(tmp_path):
    from mc_pack_converter.webui.report import build_model
    m = build_model(_result(tmp_path), sheet={"sections": [], "total": 0},
                    update="An update is available")
    assert m["update"] == "An update is available"


def test_the_sheet_is_carried_verbatim(tmp_path):
    from mc_pack_converter.webui.report import build_model
    sheet = {"sections": [{"label": "Blocks", "tiles": []}], "total": 1}
    m = build_model(_result(tmp_path), sheet=sheet)
    assert m["sheet"] is sheet


def test_the_model_is_json_serialisable(tmp_path):
    """It is about to be embedded in a script tag. A Path or a Severity
    reaching json.dumps is a crash at the last possible moment."""
    import json
    from mc_pack_converter.webui.report import build_model
    r = _result(tmp_path, [("validate", Severity.ERROR, "boom", "textures/block/stone.png")])
    m = build_model(r, sheet={"sections": [], "total": 0})
    serialised = json.dumps(m)
    roundtripped = json.loads(serialised)
    assert roundtripped["findings"][0]["path"] == "textures/block/stone.png"
