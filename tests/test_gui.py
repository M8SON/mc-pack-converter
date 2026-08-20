from pathlib import Path

from mc_pack_converter.gui import parse_drop


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


# --- main(): converts, writes the report, opens it, prints its path -------
#
# LOCALAPPDATA is redirected to an empty tmp_path in every test that runs
# main(): the update check reads installed-sha from the real cache dir
# (~/.cache/MCPackConverter on this machine), and a machine that has one
# installed would otherwise make main() reach out to GitHub in a test run.

def test_the_report_path_is_printed_even_when_the_browser_fails(
        tmp_path, capsys, monkeypatch, mini_pack):
    """Unconditional, not a fallback. webbrowser.open returns True on some
    platforms with nothing appearing -- under WSL, headless, or with an odd
    default handler. The path on stdout is the guarantee."""
    import webbrowser
    from mc_pack_converter import gui

    def boom(*a, **k):
        raise OSError("no browser")

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "cache"))
    monkeypatch.setattr(webbrowser, "open", boom)
    pack = mini_pack()
    rc = gui.main([str(pack)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "-report.html" in out


def test_the_report_lands_beside_the_output_zip(tmp_path, monkeypatch, mini_pack):
    import webbrowser
    from mc_pack_converter import gui
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "cache"))
    monkeypatch.setattr(webbrowser, "open", lambda *a, **k: True)
    pack = mini_pack()
    gui.main([str(pack)])
    reports = list(pack.parent.glob("*-report.html"))
    assert len(reports) == 1
    assert reports[0].read_text().startswith("<!doctype html>")


def test_a_run_writes_no_markdown_litter_beside_the_report(tmp_path, monkeypatch, mini_pack):
    """The old windowed code passed write_reports=False so a run left only the
    zip and the window's own display behind -- "no .md litter". A drag-and-drop
    run must match that: the HTML report is the only write-up produced, even
    though (like the window before it) it carries no null-textures content."""
    import webbrowser
    from mc_pack_converter import gui
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "cache"))
    monkeypatch.setattr(webbrowser, "open", lambda *a, **k: True)
    pack = mini_pack()
    gui.main([str(pack)])
    assert list(pack.parent.glob("*-report.html"))
    assert not list(pack.parent.glob("*-report.md"))
    assert not list(pack.parent.glob("*-null-textures.md"))


def test_running_with_no_pack_explains_itself(capsys):
    """Double-clicking the .cmd with nothing to convert must say what to do,
    not open an empty page and not raise."""
    from mc_pack_converter import gui
    rc = gui.main([])
    assert rc != 0
    assert "drag" in capsys.readouterr().err.lower()
