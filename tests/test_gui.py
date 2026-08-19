from pathlib import Path

import pytest

from mc_pack_converter.gui import GuiState, parse_drop


def test_parse_drop_with_no_arguments():
    assert parse_drop([]) == (None, [])


def test_parse_drop_takes_the_first_path():
    source, extras = parse_drop([r"C:\Downloads\MyPack.zip"])
    assert source == Path(r"C:\Downloads\MyPack.zip")
    assert extras == []


def test_parse_drop_reports_extra_files_rather_than_hiding_them():
    source, extras = parse_drop(["a.zip", "b.zip", "c.zip"])
    assert source == Path("a.zip")
    assert extras == [Path("b.zip"), Path("c.zip")]


def test_state_starts_on_the_progress_screen():
    state = GuiState(Path("MyPack.zip"), "26.2")
    assert state.screen == "progress"
    assert state.done == 0


def test_stage_messages_advance_the_counter():
    state = GuiState(Path("MyPack.zip"), "26.2")
    state.handle(("stage", "ingest", 1, 20))
    state.handle(("stage", "atlas_remap", 8, 20))
    assert state.screen == "progress"
    assert (state.stage, state.done, state.total) == ("atlas_remap", 8, 20)
    assert "8/20" in " ".join(state.detail_lines())


def test_progress_detail_omits_the_counter_before_the_first_stage_message():
    state = GuiState(Path("MyPack.zip"), "26.2")
    assert state.total == 0
    text = " ".join(state.detail_lines())
    assert "0/0" not in text


def test_done_switches_to_the_result_screen():
    state = GuiState(Path("MyPack.zip"), "26.2")
    state.handle(("stage", "ingest", 1, 20))
    sentinel = object()
    state.handle(("done", sentinel))
    assert state.screen == "result"
    assert state.result is sentinel


def test_failure_switches_to_the_error_screen():
    state = GuiState(Path("MyPack.zip"), "26.2")
    boom = RuntimeError("disk full")
    state.handle(("failed", boom))
    assert state.screen == "error"
    assert state.error is boom


def test_headline_names_the_pack_and_target_while_running():
    state = GuiState(Path(r"C:\Downloads\MyPack.zip"), "26.2")
    assert "MyPack.zip" in state.headline()
    assert "26.2" in state.headline()


def test_error_headline_does_not_leak_a_traceback():
    state = GuiState(Path("MyPack.zip"), "26.2")
    state.handle(("failed", RuntimeError("disk full")))
    assert "Traceback" not in state.headline()
    assert "disk full" in " ".join(state.detail_lines())


def test_a_fatal_conversion_error_reads_as_a_bad_pack_not_a_crash():
    from mc_pack_converter.pipeline import FatalConversionError
    state = GuiState(Path("MyPack.zip"), "26.2")
    state.handle(("failed", FatalConversionError("output dir not writable: /nope")))
    assert state.headline() == "This pack could not be converted"
    detail = " ".join(state.detail_lines())
    assert "output dir not writable" in detail
    assert "FatalConversionError" not in detail


def test_an_unexpected_crash_is_named_as_one():
    state = GuiState(Path("MyPack.zip"), "26.2")
    state.handle(("failed", RuntimeError("disk full")))
    assert state.headline() == "Something went wrong"
    assert "RuntimeError" in " ".join(state.detail_lines())


def test_error_details_carry_the_full_traceback():
    state = GuiState(Path("MyPack.zip"), "26.2")
    try:
        raise RuntimeError("disk full")
    except RuntimeError as exc:
        state.handle(("failed", exc))
    details = state.error_details()
    assert "Traceback" in details
    assert "RuntimeError: disk full" in details


def test_extras_are_surfaced_not_silently_dropped():
    state = GuiState(Path("a.zip"), "26.2", extras=[Path("b.zip")])
    state.handle(("failed", RuntimeError("x")))
    assert any("b.zip" in line for line in state.detail_lines())


class _FakeResult:
    """Stands in for JobResult; GuiState must not reach past these fields."""
    def __init__(self, tmp):
        from mc_pack_converter.pipeline import Severity
        self.out_path = tmp / "MyPack-26.2.zip"
        self.reports = {"report": tmp / "MyPack-26.2-report.md"}
        self.wrote_zip = True
        self.counts = {Severity.ERROR: 0, Severity.WARNING: 3, Severity.INFO: 9}
        self.has_errors = False


def test_result_detail_reports_counts_and_the_written_zip(tmp_path):
    state = GuiState(Path("MyPack.zip"), "26.2")
    state.handle(("done", _FakeResult(tmp_path)))
    text = " ".join(state.detail_lines())
    assert "3 warnings" in text
    assert "MyPack-26.2.zip" in text


def test_result_headline_says_done_when_clean(tmp_path):
    state = GuiState(Path("MyPack.zip"), "26.2")
    state.handle(("done", _FakeResult(tmp_path)))
    assert "Done" in state.headline()


def test_result_headline_flags_errors(tmp_path):
    result = _FakeResult(tmp_path)
    from mc_pack_converter.pipeline import Severity
    result.counts[Severity.ERROR] = 2
    result.has_errors = True
    state = GuiState(Path("MyPack.zip"), "26.2")
    state.handle(("done", result))
    assert "2 errors" in state.headline()


@pytest.mark.parametrize("msg", [
    ("something-else", 1),      # unknown kind, well-formed
    (),                         # empty
    ("stage",),                 # known kind, no payload
    ("stage", "ingest"),        # known kind, too few values
    ("stage", "ingest", 1, 20, "extra"),  # known kind, too many values
    ("done",),                  # known kind, missing result
    ("failed",),                # known kind, missing exception
    None,                       # not a sequence at all
    42,                         # not a sequence at all
])
def test_malformed_messages_are_ignored_rather_than_crashing(msg):
    """A bad message must never kill the window.

    handle() runs inside the Tk event loop of a windowed exe with no console,
    so an exception raised here is invisible to the user and fatal to the UI.
    """
    state = GuiState(Path("MyPack.zip"), "26.2")
    state.handle(msg)
    assert state.screen == "progress"
    assert state.result is None
    assert state.error is None


def test_wrong_arity_stage_message_does_not_half_mutate_state():
    state = GuiState(Path("MyPack.zip"), "26.2")
    state.handle(("stage", "ingest"))
    assert state.stage == ""
    assert state.done == 0
    assert state.total == 0


class _FakeResultWithFindings:
    """A JobResult with real findings, for the to_dict() tests."""
    def __init__(self, tmp, findings):
        from types import SimpleNamespace
        from mc_pack_converter.pipeline import Severity
        self.ctx = SimpleNamespace(findings=findings)
        self.out_path = tmp / "MyPack-26.2.zip"
        self.reports = {}
        self.wrote_zip = True
        counts = {s: 0 for s in Severity}
        for f in findings:
            counts[f.severity] += 1
        self.counts = counts
        self.has_errors = counts[Severity.ERROR] > 0


def _finding(sev, stage="conformance", message="m", path=None):
    from mc_pack_converter.pipeline import Finding
    return Finding(stage, sev, message, path)


def test_to_dict_on_progress_carries_the_counter():
    state = GuiState(Path("MyPack.zip"), "26.2")
    state.handle(("stage", "atlas_remap", 8, 20))
    d = state.to_dict()
    assert d["screen"] == "progress"
    assert (d["done"], d["total"], d["stage"]) == (8, 20, "atlas_remap")
    assert "findings" not in d


def test_to_dict_orders_findings_by_severity_not_by_stage(tmp_path):
    from mc_pack_converter.pipeline import Severity
    findings = [
        _finding(Severity.INFO, "ingest", "first note"),
        _finding(Severity.ERROR, "validate", "an error"),
        _finding(Severity.WARNING, "conformance", "a warning"),
        _finding(Severity.INFO, "clean", "second note"),
    ]
    state = GuiState(Path("MyPack.zip"), "26.2")
    state.handle(("done", _FakeResultWithFindings(tmp_path, findings)))
    d = state.to_dict()
    assert [f["severity"] for f in d["findings"]] == \
        ["error", "warning", "info", "info"]
    # stable within a severity: pipeline order is preserved
    assert [f["message"] for f in d["findings"][2:]] == ["first note", "second note"]
    assert d["counts"] == {"error": 1, "warning": 1, "info": 2}


def test_to_dict_keeps_a_findings_path_and_tolerates_its_absence(tmp_path):
    from mc_pack_converter.pipeline import Severity
    findings = [
        _finding(Severity.WARNING, path="textures/gui/container/enchanting_table.png"),
        _finding(Severity.WARNING),
    ]
    state = GuiState(Path("MyPack.zip"), "26.2")
    state.handle(("done", _FakeResultWithFindings(tmp_path, findings)))
    paths = [f["path"] for f in state.to_dict()["findings"]]
    assert paths == ["textures/gui/container/enchanting_table.png", None]


def test_to_dict_on_error_carries_the_traceback():
    state = GuiState(Path("MyPack.zip"), "26.2")
    try:
        raise RuntimeError("disk full")
    except RuntimeError as exc:
        state.handle(("failed", exc))
    d = state.to_dict()
    assert d["screen"] == "error"
    assert "Traceback" in d["error_details"]


def test_to_dict_is_json_serialisable(tmp_path):
    import json
    from mc_pack_converter.pipeline import Severity
    state = GuiState(Path("MyPack.zip"), "26.2")
    state.handle(("done", _FakeResultWithFindings(
        tmp_path, [_finding(Severity.INFO, path="a/b.png")])))
    json.dumps(state.to_dict())  # must not raise


def test_state_with_no_pack_waits_on_the_drop_screen():
    """The window must open and wait, not demand a pack before it appears."""
    state = GuiState(None, "26.2")
    assert state.screen == "idle"
    assert state.headline() == "MC Pack Converter"
    assert "26.2" in " ".join(state.detail_lines())
    d = state.to_dict()
    assert d["screen"] == "idle"
    assert d["source"] == ""
    assert "findings" not in d


def test_a_dropped_pack_starts_the_run():
    state = GuiState(None, "26.2")
    state.start(Path(r"C:\Downloads\MyPack.zip"))
    assert state.screen == "progress"
    assert state.source == Path(r"C:\Downloads\MyPack.zip")
    assert "MyPack.zip" in state.headline()


def test_starting_again_forgets_the_previous_run(tmp_path):
    """Otherwise the second conversion is shown wearing the first one's
    result and sheet -- 'it was loading up old versions of the pack'."""
    from mc_pack_converter.gui import GuiState
    state = GuiState(None, "26.2")
    state.result = object()
    state.sheet = {"sections": []}
    state.done, state.total, state.stage = 7, 9, "slicing"
    state.error = RuntimeError("old")

    state.start(tmp_path / "next.zip")

    assert state.screen == "progress"
    assert state.result is None
    assert state.sheet is None
    assert state.error is None
    assert (state.done, state.total, state.stage) == (0, 0, "")


def test_the_launch_log_records_startup_and_starts_empty_each_launch(tmp_path, monkeypatch):
    """A windowed exe has no console. When the window comes up dead this file
    is the only evidence of how far startup got, so it must survive a crash
    and must not accumulate across launches."""
    import mc_pack_converter.gui as gui
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(gui, "_diag_file", None)

    gui._diag("launch: first")
    gui._diag("window created")
    log = tmp_path / "MCPackConverter" / "last-run.log"
    assert "launch: first" in log.read_text()
    assert "window created" in log.read_text()

    monkeypatch.setattr(gui, "_diag_file", None)      # a fresh launch
    gui._diag("launch: second")
    assert "first" not in log.read_text()


def test_a_broken_log_never_breaks_a_launch(tmp_path, monkeypatch):
    """An unwritable profile must not stop the window opening."""
    import mc_pack_converter.gui as gui
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    monkeypatch.setenv("LOCALAPPDATA", str(blocker))
    monkeypatch.setattr(gui, "_diag_file", None)
    gui._diag("should not raise")          # no exception is the assertion
