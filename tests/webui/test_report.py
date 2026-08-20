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


def test_the_report_reaches_out_to_nothing(tmp_path):
    """The single-file property, asserted directly rather than assumed. A
    stylesheet link or a script src would make the report break the moment it
    is moved or emailed."""
    from mc_pack_converter.webui.report import build_model, render_html
    html = render_html(build_model(_result(tmp_path),
                                   sheet={"sections": [], "total": 0}))
    assert "http://" not in html
    assert "https://" not in html
    assert 'href="app.css"' not in html
    assert 'src="app.js"' not in html


def test_the_stylesheet_and_script_are_inlined(tmp_path):
    from mc_pack_converter.webui.report import (ASSETS, build_model,
                                                render_html)
    html = render_html(build_model(_result(tmp_path),
                                   sheet={"sections": [], "total": 0}))
    css = (ASSETS / "app.css").read_text()
    assert css.strip().splitlines()[0] in html


def test_the_model_is_embedded_and_readable(tmp_path):
    import json, re
    from mc_pack_converter.webui.report import build_model, render_html
    model = build_model(_result(tmp_path), sheet={"sections": [], "total": 7})
    html = render_html(model)
    blob = re.search(r"window\.MODEL\s*=\s*(\{.*?\});", html, re.S).group(1)
    assert json.loads(blob)["sheet"]["total"] == 7


def _asset(name):
    from mc_pack_converter.webui.report import ASSETS
    return (ASSETS / name).read_text()


def test_the_page_reads_the_embedded_model():
    assert "window.MODEL" in _asset("app.js")


def test_the_page_no_longer_speaks_to_a_bridge():
    """The bridge is gone. Any surviving call is a page that is live and
    wired to nothing -- which this app shipped twice."""
    js = _asset("app.js")
    for gone in ("pywebview", "api.poll", "api.sheet", "api.texture",
                 "setTimeout(tick", "pywebviewready"):
        assert gone not in js, gone


def test_the_lightbox_uses_the_inlined_original():
    """`full` when there is one, `thumb` when the thumbnail already is the
    original -- 893 of 1019 tiles on the reference pack."""
    js = _asset("app.js")
    assert "t.full" in js or ".full ||" in js


def test_no_trace_of_the_old_bridge_survives(tmp_path):
    """Renamed from the pywebview-derived name Task 3 used: pytest derives
    tmp_path's directory name from the test function's own name, so a test
    with "pywebview" in its name puts "pywebview" into out_path via tmp_path
    and fails this assertion on its own name rather than on real leftovers."""
    from mc_pack_converter.webui.report import build_model, render_html
    html = render_html(build_model(_result(tmp_path),
                                   sheet={"sections": [], "total": 0}))
    assert "pywebview" not in html


def test_a_closing_script_tag_in_the_data_cannot_escape(tmp_path):
    """A finding's message is pack-controlled text. '</script>' inside the
    JSON would end the block early and put the rest of the model on the page
    as markup."""
    import json, re
    from mc_pack_converter.webui.report import build_model, render_html
    r = _result(tmp_path, [("validate", Severity.WARNING, "</script><b>hi")])
    html = render_html(build_model(r, sheet={"sections": [], "total": 0}))
    assert "</script><b>hi" not in html
    blob = re.search(r"window\.MODEL\s*=\s*(\{.*?\});", html, re.S).group(1)
    assert json.loads(blob)["findings"][0]["message"] == "</script><b>hi"
