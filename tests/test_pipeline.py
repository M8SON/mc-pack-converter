# tests/test_pipeline.py
from mc_pack_converter.pipeline import (
    ConversionContext, Finding, Severity, run_pipeline, FatalConversionError,
)

def test_run_pipeline_runs_stages_in_order(tmp_path):
    ctx = ConversionContext(root=tmp_path, findings=[])
    order = []
    stages = [("a", lambda c: order.append("a")),
              ("b", lambda c: order.append("b"))]
    run_pipeline(ctx, stages)
    assert order == ["a", "b"]

def test_stage_exception_recorded_and_continues(tmp_path):
    ctx = ConversionContext(root=tmp_path, findings=[])
    def boom(c): raise ValueError("nope")
    ran_after = []
    run_pipeline(ctx, [("boom", boom), ("after", lambda c: ran_after.append(1))])
    assert ran_after == [1]
    assert any(f.severity is Severity.ERROR and f.stage == "boom" for f in ctx.findings)

def test_fatal_error_aborts(tmp_path):
    ctx = ConversionContext(root=tmp_path, findings=[])
    def fatal(c): raise FatalConversionError("bad pack")
    import pytest
    with pytest.raises(FatalConversionError):
        run_pipeline(ctx, [("fatal", fatal)])
