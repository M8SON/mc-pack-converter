# Publish to GitHub + CLI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a working conversion engine into a public tool a stranger can install, run, and understand — without changing a single converted byte.

**Architecture:** Three independent slices. Tasks 1–4 rework `cli.py` only, behind
its existing `convert()` entry point, adding a progress callback so a future GUI
can drive the same code path. Tasks 5–7 add the repo's public face (README,
LICENSE, attribution) and CI. Task 8 pushes to GitHub. Conversion stages,
`pipeline.py`, and all data tables are untouched throughout.

**Tech Stack:** Python 3.11+, argparse, pytest, Pillow (already a dependency),
GitHub Actions, `gh` CLI.

## Global Constraints

- Python floor is `>=3.11` — do not raise or lower it in `pyproject.toml`.
- **No conversion behavior may change.** No edits to `mc_pack_converter/stages/`,
  `pipeline.py`, `report.py`, `imaging.py`, `contact_sheet.py`, or anything in
  `mc_pack_converter/data/`. The 173-pack corpus results and
  `test_golden_conversion` are the guard. If a task seems to require such an
  edit, stop and ask.
- All 208 existing tests must stay green after every task. Run the full suite,
  not just the new test.
- Valid `--target` values come from the keys of
  `mc_pack_converter/data/pack_format.json`: `1.8.9`, `26.1`, `26.1.2`, `26.2`.
  Read them at runtime via `load_table("pack_format")`. Never hardcode the list.
- Exit codes are unchanged: `1` if any finding has `Severity.ERROR`, else `0`.
- The repo is `M8SON/mc-pack-converter`, public. License is MIT, copyright
  Mason Misch.
- Run pytest as `.venv/bin/python -m pytest` from
  `/home/daedalus/linux/mc-pack-converter`.
- Work happens on branch `feature/publish-and-cli-polish`, which already exists
  and already holds the design commit.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `mc_pack_converter/cli.py` | Argument parsing, output naming, progress and summary rendering, error presentation | Modify — the only Python file that changes |
| `tests/test_cli_e2e.py` | End-to-end CLI behavior | Modify — new tests appended |
| `README.md` | Public front door | Create |
| `LICENSE` | MIT | Create |
| `tools/slicer_src/README.md` | Third-party attribution | Create |
| `.github/workflows/tests.yml` | CI | Create |

`cli.py` is currently 57 lines and gains roughly 60 more. That is still one
focused file — argument handling and presentation — so it does not need
splitting.

---

### Task 1: Derived output name

Replaces the fixed `converted.zip` default, which silently overwrote the
previous run. `MyPack.zip` with `--target 26.2` becomes `MyPack-26.2.zip` in the
current working directory. A source *directory* uses its directory name.

**Files:**
- Modify: `mc_pack_converter/cli.py` (the `main` function, lines 40–54)
- Test: `tests/test_cli_e2e.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `default_out_path(source: Path, target: str) -> Path`, a
  module-level function in `mc_pack_converter/cli.py`. Later tasks call it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_e2e.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli_e2e.py -v -k "default_out_path or derived_name or explicit_out"`

Expected: FAIL with `ImportError: cannot import name 'default_out_path'` on the
first three, and the `derived_name` test failing because `pack-26.2.zip` does
not exist (it wrote `converted.zip`).

- [ ] **Step 3: Implement**

In `mc_pack_converter/cli.py`, add above `main`:

```python
def default_out_path(source: Path, target: str) -> Path:
    """Name the output after the source and target, in the cwd.

    A fixed default overwrites the previous run without saying so.
    """
    stem = source.stem if source.suffix.lower() == ".zip" else source.name
    return Path(f"{stem}-{target}.zip")
```

Then in `main`, change the `-o` default from `Path("converted.zip")` to `None`:

```python
    c.add_argument("-o", "--out", type=Path, default=None)
```

and resolve it after parsing, before the `convert` call:

```python
    args = ap.parse_args(argv)
    out = args.out or default_out_path(args.source, args.target)
    ctx = convert(args.source, out, args.target, args.report_only)
```

Do not reorder `convert`'s parameters — existing tests call it by keyword and by
position.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, 213 tests.

- [ ] **Step 5: Commit**

```bash
git add mc_pack_converter/cli.py tests/test_cli_e2e.py
git commit -m "feat: name the output after the pack, not converted.zip"
```

---

### Task 2: Help text and target validation

Today `--help` lists bare argument names and a typo in `--target` produces a
confusing conversion rather than an error.

**Files:**
- Modify: `mc_pack_converter/cli.py` (the `main` function)
- Test: `tests/test_cli_e2e.py`

**Interfaces:**
- Consumes: `default_out_path` from Task 1.
- Produces: `build_parser() -> argparse.ArgumentParser`, a module-level function
  in `mc_pack_converter/cli.py`. `main` calls it. Tests call it directly to
  inspect help text.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_e2e.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli_e2e.py -v -k "help or invalid_target or data_table"`

Expected: FAIL with `ImportError: cannot import name 'build_parser'`.

- [ ] **Step 3: Implement**

In `mc_pack_converter/cli.py`, add the import at the top:

```python
from .data import load_table
```

Add above `main`:

```python
TARGETS = sorted(load_table("pack_format"))

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="mc-pack-converter",
        description="Convert a Minecraft Java 1.8.9 resource pack to a modern version.",
        epilog="example:  mc-pack-converter convert MyPack.zip --target 26.2",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert", help="convert a pack")
    c.add_argument("source", type=Path,
                   help="the 1.8.9 pack to convert: a .zip or an unpacked folder")
    c.add_argument("-o", "--out", type=Path, default=None,
                   help="output zip (default: <pack>-<target>.zip in the current directory)")
    c.add_argument("--target", default="26.2", choices=TARGETS,
                   help="Minecraft version to convert to (default: %(default)s)")
    c.add_argument("--report-only", action="store_true",
                   help="analyse the pack and write reports without producing a converted pack")
    return ap
```

Replace the parser construction inside `main` with `ap = build_parser()`, keeping
the rest of `main` as it is.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, 217 tests.

- [ ] **Step 5: Commit**

```bash
git add mc_pack_converter/cli.py tests/test_cli_e2e.py
git commit -m "feat: document every flag and reject an unknown target"
```

---

### Task 3: Progress callback and quiet summary

Today every run prints two full markdown reports. Most runs should print a
progress line per stage and a short summary. Progress goes through a callback
rather than `print()` so a future GUI can render a progress bar from the same
`convert()` call.

**Files:**
- Modify: `mc_pack_converter/cli.py` (`convert` and `main`)
- Test: `tests/test_cli_e2e.py`

**Interfaces:**
- Consumes: `build_parser`, `TARGETS`, `default_out_path` from Tasks 1–2.
- Produces:
  - `convert(source, out_path, target, report_only, on_stage=None)` — the
    existing signature plus a trailing keyword-only-in-practice fifth parameter
    `on_stage: Callable[[str, int, int], None] | None`. It is called once
    *before* each stage runs, with `(stage_name, index_1_based, total_stages)`.
    All four existing positional parameters keep their order and meaning, so
    every current caller and test keeps working.
  - `summary_lines(ctx: ConversionContext, out_path: Path, reports: dict[str, Path]) -> list[str]`
    — renders the closing summary. `reports` maps a human label to the written
    path.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_e2e.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli_e2e.py -v -k "on_stage or without_a_callback or summary_not_reports or verbose"`

Expected: FAIL — `convert() got an unexpected keyword argument 'on_stage'`, and
the summary tests failing because the reports are still printed.

- [ ] **Step 3: Implement**

`run_pipeline` in `pipeline.py` must not change (Global Constraints). Instead,
wrap each stage function in `convert` before handing the list to `run_pipeline`.

In `mc_pack_converter/cli.py`, change `convert`:

```python
def convert(source: Path, out_path: Path, target: str,
            report_only: bool, on_stage=None) -> ConversionContext:
    workroot = Path(tempfile.mkdtemp(prefix="mcpc_"))
    try:
        root = prepare_working_copy(source, workroot)
        ctx = ConversionContext(root=root, target=target)
        stages = STAGES if not report_only else [
            s for s in STAGES if s[0] in ("ingest", "clean", "restructure",
            "flatten_rename", "atlas_remap", "optifine", "validate")]
        if on_stage is not None:
            stages = _announce(stages, on_stage)
        run_pipeline(ctx, stages)
```

Leave the rest of `convert`'s body exactly as it is. Add above `convert`:

```python
def _announce(stages, on_stage):
    """Wrap each stage so the caller is told before it runs."""
    total = len(stages)
    return [
        (name, lambda ctx, fn=fn, name=name, i=i: (on_stage(name, i, total), fn(ctx))[1])
        for i, (name, fn) in enumerate(stages, start=1)
    ]
```

The `fn=fn, name=name, i=i` defaults are load-bearing — without them every
closure captures the last loop value.

Add `summary_lines` above `main`:

```python
def summary_lines(ctx: ConversionContext, out_path: Path,
                  reports: dict[str, Path]) -> list[str]:
    counts = {s: 0 for s in Severity}
    for f in ctx.findings:
        counts[f.severity] += 1
    lines = [
        "",
        f"{counts[Severity.ERROR]} errors, {counts[Severity.WARNING]} warnings, "
        f"{counts[Severity.INFO]} notes",
        f"wrote {out_path}",
    ]
    lines += [f"{label}: {path}" for label, path in reports.items()]
    return lines
```

Rewrite `main`'s tail. Replace everything from `args = ap.parse_args(argv)` to
the end of the function with:

```python
    args = ap.parse_args(argv)
    out = args.out or default_out_path(args.source, args.target)

    def on_stage(name, i, total):
        print(f"[{i}/{total}] {name}")

    ctx = convert(args.source, out, args.target, args.report_only,
                  on_stage=on_stage)

    texts = {
        "report": render_conversion_report(ctx.findings),
        "null-textures": render_null_texture_report(ctx.findings),
    }
    written = {}
    for label, text in texts.items():
        p = out.with_name(f"{out.stem}-{label}.md")
        p.write_text(text)
        written[label] = p

    if args.verbose:
        for text in texts.values():
            print(text)
    for line in summary_lines(ctx, out, written):
        print(line)

    if any(f.severity is Severity.ERROR for f in ctx.findings):
        return 1
    return 0
```

Add the `-v` flag to `build_parser`'s `convert` subparser, after `--report-only`:

```python
    c.add_argument("-v", "--verbose", action="store_true",
                   help="also print the full reports to the terminal")
```

Add `Severity` to the existing pipeline import at the top of `cli.py` — it is
already imported, so no change is needed there; confirm the line reads
`from .pipeline import ConversionContext, Severity, run_pipeline`.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, 221 tests.

- [ ] **Step 5: Commit**

```bash
git add mc_pack_converter/cli.py tests/test_cli_e2e.py
git commit -m "feat: show progress and a summary instead of two raw reports"
```

---

### Task 4: Reports beside the zip, and a clean error for a bad source

Task 3 already writes the reports beside the output. This task pins that down
with explicit tests, covers the `--report-only` case (no zip, reports still
written under the derived stem), and stops a missing source from printing a
traceback at a user.

**Files:**
- Modify: `mc_pack_converter/cli.py` (`main`)
- Test: `tests/test_cli_e2e.py`

**Interfaces:**
- Consumes: everything from Tasks 1–3.
- Produces: nothing new.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_e2e.py`:

```python
def test_reports_written_beside_the_zip(mini_pack, tmp_path, monkeypatch):
    root = mini_pack()
    monkeypatch.chdir(tmp_path)
    assert main(["convert", str(root)]) == 0
    assert (tmp_path / "pack-26.2-report.md").read_text().startswith("# Conversion Report")
    assert (tmp_path / "pack-26.2-null-textures.md").read_text().startswith(
        "# Null-Texture Safety Report")


def test_report_only_writes_reports_but_no_zip(mini_pack, tmp_path, monkeypatch):
    root = mini_pack()
    monkeypatch.chdir(tmp_path)
    assert main(["convert", str(root), "--report-only"]) == 0
    assert (tmp_path / "pack-26.2-report.md").exists()
    assert not (tmp_path / "pack-26.2.zip").exists()


def test_missing_source_is_one_line_not_a_traceback(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = main(["convert", str(tmp_path / "nope.zip")])
    assert code != 0
    captured = capsys.readouterr()
    message = captured.out + captured.err
    assert "nope.zip" in message
    assert "Traceback" not in message
    assert len(message.strip().splitlines()) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli_e2e.py -v -k "beside_the_zip or report_only_writes or missing_source"`

Expected: the first two PASS already (Task 3 delivered them — that is fine and
worth confirming); `test_missing_source_is_one_line_not_a_traceback` FAILs with
an uncaught exception from `prepare_working_copy`.

- [ ] **Step 3: Implement**

In `main`, guard the source before doing any work. Insert immediately after the
`out = ...` line:

```python
    if not args.source.exists():
        print(f"no such pack: {args.source}", file=sys.stderr)
        return 1
```

Add `import sys` to the imports at the top of `cli.py`.

Do not add a blanket `try/except` around `convert`. An unexpected exception
should still surface with its traceback — only this one predictable user error
is handled.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, 224 tests.

- [ ] **Step 5: Commit**

```bash
git add mc_pack_converter/cli.py tests/test_cli_e2e.py
git commit -m "feat: report a missing pack in one line, not a traceback"
```

---

### Task 5: Manual verification of the finished CLI

The tests prove behavior; this proves the experience. No code changes — if
something here reads badly, fix it and re-run the suite before committing.

**Files:** none changed unless a problem is found.

- [ ] **Step 1: Read the help output**

Run: `.venv/bin/python -m mc_pack_converter.cli convert --help`

Confirm: every flag has a description, the four targets are listed, the example
appears at the bottom.

- [ ] **Step 2: Convert the golden pack into a scratch directory**

```bash
cd /tmp/claude-1000/-home-daedalus-linux/*/scratchpad \
  && /home/daedalus/linux/mc-pack-converter/.venv/bin/python \
     -m mc_pack_converter.cli convert "/home/daedalus/linux/M8SON 1.8 PVP PACK"
```

Confirm: 20 progress lines, then a summary; `M8SON 1.8 PVP PACK-26.2.zip` plus
its two `.md` reports are in the scratch directory; no markdown was printed.

- [ ] **Step 3: Confirm the output is unchanged from before this work**

The converted pack must be byte-for-byte equivalent in content to what `master`
produces. Run the golden test, which asserts the structural invariants:

Run: `.venv/bin/python -m pytest tests/test_cli_e2e.py::test_golden_conversion -v`

Expected: PASS (not skipped — the local pack exists).

- [ ] **Step 4: Check the error path**

Run: `.venv/bin/python -m mc_pack_converter.cli convert /tmp/does-not-exist.zip`

Expected: one line, exit status 1, no traceback.

---

### Task 6: README, LICENSE, and third-party attribution

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Create: `tools/slicer_src/README.md`

**Interfaces:**
- Consumes: the finished CLI from Tasks 1–4, so the quickstart in the README
  matches reality.
- Produces: nothing code depends on.

- [ ] **Step 1: Write `LICENSE`**

The standard MIT license text, `Copyright (c) 2026 Mason Misch`.

- [ ] **Step 2: Write `tools/slicer_src/README.md`**

```markdown
# Vendored Mojang slicer sources

`slicer_1.14.java`, `slicer_1.20.2.java` and `slicer262.java` are Mojang's,
from [github.com/Mojang/slicer](https://github.com/Mojang/slicer). They are
kept here because `tools/gen_slices.py` parses them to regenerate
`mc_pack_converter/data/slices.json` — the table of every GUI sprite crop the
1.20.2 atlas migration performs.

They are build-time inputs only. No Mojang code is imported, executed, or
shipped in the converter or in any pack it produces.
```

- [ ] **Step 3: Write `README.md`**

Follow the spec's section order exactly: description, install, quickstart, what
it does, limitations, credits. Requirements for the content:

- **Description:** one sentence — converts Minecraft Java 1.8.9 resource packs
  to modern versions (26.1, 26.1.2, 26.2).
- **Install:** Python 3.11+, `pip install .`. Mention Pillow is the only runtime
  dependency.
- **Quickstart:** show the real command and its real output shape:
  ```
  mc-pack-converter convert MyPack.zip
  ```
  followed by what appears (progress lines, summary, the three files produced).
  Copy the actual output from Task 5 Step 2 rather than inventing it.
- **What it does:** the 20 stages as a list, one clause each, in `STAGES` order:
  ingest, clean, repair_mcmeta, lowercase_paths, restructure, flatten_rename,
  model_refs, atlas_remap, chest, gui_remap, legacy, drop, conformance,
  optifine, slice, derive_sprites, prune_atlases, sounds, pack_meta, validate.
  Read each stage module's docstring or top comment for an accurate clause.
- **Limitations:** honest and short. State that 1.8.9-era input is the only
  supported input (`docs/known-issues.md` §0), and name the two accepted
  limitations recorded there — read §2 (custom mob-effect icons) and §5 (the
  villager GUI) and summarise each in one sentence. Link
  `docs/known-issues.md` for the full record; do not duplicate it.
- **Credits:** Mojang's slicer and
  [agentdid127/ResourcePackConverter](https://github.com/agentdid127/ResourcePackConverter),
  described as the two authoritative references the pipeline was validated
  against.

Do not add a CI badge yet — the workflow does not exist until Task 7.

- [ ] **Step 4: Verify the quickstart is accurate**

Re-run the Task 5 Step 2 command and diff its real output against what the
README claims. Fix the README, not the code.

- [ ] **Step 5: Commit**

```bash
git add README.md LICENSE tools/slicer_src/README.md
git commit -m "docs: README, MIT license, and Mojang slicer attribution"
```

---

### Task 7: CI

**Files:**
- Create: `.github/workflows/tests.yml`
- Modify: `README.md` (badge)

**Interfaces:**
- Consumes: nothing.
- Produces: a workflow named `tests` — the README badge URL depends on that name.

- [ ] **Step 1: Write the workflow**

```yaml
name: tests

on:
  push:
  pull_request:

jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: pytest -q
```

`test_golden_conversion` is `skipif`-guarded on a local pack path absent from
CI, so it skips there. Every other test runs.

- [ ] **Step 2: Verify the workflow the way CI will run it**

CI installs from `pyproject.toml`, not from the existing `.venv`. Confirm that
works in a throwaway environment:

```bash
python3 -m venv /tmp/mcpc-ci-check \
  && /tmp/mcpc-ci-check/bin/pip install -q -e ".[dev]" \
  && /tmp/mcpc-ci-check/bin/pytest -q
```

Expected: PASS with exactly one skip (`test_golden_conversion` still finds the
local pack, so it will *not* skip here — that is fine; the point is that a clean
install can run the suite at all).

- [ ] **Step 3: Add the badge to the README**

At the top of `README.md`, under the title:

```markdown
[![tests](https://github.com/M8SON/mc-pack-converter/actions/workflows/tests.yml/badge.svg)](https://github.com/M8SON/mc-pack-converter/actions/workflows/tests.yml)
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/tests.yml README.md
git commit -m "ci: run the suite on push and pull request"
```

---

### Task 8: Publish

The only irreversible task. Creating a public repo puts this code on the
internet. **Confirm with Mason before running Step 2.**

**Files:** none.

- [ ] **Step 1: Merge to master**

```bash
git checkout master
git merge --no-ff feature/publish-and-cli-polish \
  -m "Merge feature/publish-and-cli-polish: a tool other people can use"
.venv/bin/python -m pytest -q
```

Expected: PASS, 224 tests.

- [ ] **Step 2: Create the public repo and push**

Ask Mason to confirm, then:

```bash
gh repo create M8SON/mc-pack-converter --public --source=. --remote=origin \
  --description "Convert Minecraft Java 1.8.9 resource packs to modern versions" \
  --push
```

- [ ] **Step 3: Set the topics**

```bash
gh repo edit M8SON/mc-pack-converter \
  --add-topic minecraft --add-topic resource-pack --add-topic converter \
  --add-topic optifine --add-topic python
```

- [ ] **Step 4: Confirm CI is green**

```bash
gh run watch
```

Expected: the `tests` workflow passes, with `test_golden_conversion` skipped.
If it fails, fix it on a branch and merge — do not force-push master.

- [ ] **Step 5: Read the rendered README**

Run: `gh repo view --web`

Confirm the badge renders green, the links to `docs/known-issues.md` resolve,
and the quickstart reads correctly to someone who has never seen the project.

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| README.md, six sections | 6 |
| LICENSE (MIT) | 6 |
| tools/slicer_src/README.md | 6 |
| Public repo, push master, description, topics | 8 |
| CI workflow + badge | 7 |
| Help text on every argument, description, epilog | 2 |
| `--target` validated from `pack_format.json` | 2 |
| Derived output name, `-o` wins | 1 |
| Quiet default, progress lines, summary | 3 |
| Reports written beside the zip | 3, pinned in 4 |
| `-v` restores today's output | 3 |
| Progress via callback, not `print()` in the pipeline | 3 |
| Contact sheet follows the new naming automatically | 5 (verified, no code) |
| `--report-only` writes reports beside the would-be zip | 4 |
| Missing source → one line, no traceback | 4 |
| Exit codes unchanged | 1–4 (untouched), asserted by existing tests |
| `test_golden_conversion` keeps its path and guard | 5, 7 |

**Placeholder scan:** none — every step has its command or its code.

**Type consistency:** `default_out_path(Path, str) -> Path` (Task 1) is called
in Task 3's `main`. `build_parser() -> ArgumentParser` (Task 2) is called in
Task 3. `convert(..., on_stage=None)` (Task 3) keeps the four original
positional parameters, so Task 1's call site and every existing test stay valid.
`summary_lines(ctx, out_path, reports)` (Task 3) takes `dict[str, Path]`, which
is what Task 3's `written` builds.

**Test counts:** 208 baseline, +5 (Task 1) = 213, +4 (Task 2) = 217, +4
(Task 3) = 221, +3 (Task 4) = 224. Each task's expected count must match, and a
mismatch means a test was lost — investigate before proceeding.
