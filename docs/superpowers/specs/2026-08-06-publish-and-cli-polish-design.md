# Publish to GitHub + CLI polish — design

Date: 2026-08-06
Status: approved

## Problem

The converter is complete as an engine — 208 tests, 173/173 corpus packs
convert with zero crashes, every known defect either fixed or recorded as a
deliberate decision in `docs/known-issues.md`. It is not a product. There is no
README, no LICENSE, no git remote, and the CLI has no help text on any
argument, dumps two full markdown reports to stdout on every run, and always
writes to `converted.zip`.

The audience is Minecraft resource-pack makers, who are mostly not developers.

## Scope

This spec covers repo publication and CLI UX only.

A Windows `.exe` that converts a pack when you drag a zip onto it is the agreed
end goal for non-developers, but it is **out of scope here** and gets its own
spec once the CLI is stable. Nothing in this design may foreclose it: the CLI
must keep a callable `convert()` that reports progress through a hook rather
than by printing, so a future GUI can drive the same code path.

## A. Repo publication

### README.md

Sections, in order:

1. One-sentence description: converts Minecraft Java 1.8.9 resource packs to
   modern versions (26.1, 26.1.2, 26.2).
2. Install — `pip install .`, Python 3.11+, Pillow.
3. Quickstart — a single `mc-pack-converter convert MyPack.zip` invocation and
   what it produces.
4. What it does — the 20 pipeline stages as a short list, one clause each.
5. Limitations — honest, and links `docs/known-issues.md` rather than
   duplicating it. Names the two accepted limitations recorded there.
6. Credits — Mojang's slicer (`github.com/Mojang/slicer`) and
   agentdid127/ResourcePackConverter, the two authoritative references the
   pipeline was validated against.

### LICENSE

MIT, copyright Mason Misch.

### tools/slicer_src/README.md

`tools/slicer_src/` holds three Mojang `.java` files. They are the only
third-party code in the repo. This README states their origin, that
`tools/gen_slices.py` parses them at build time to regenerate
`mc_pack_converter/data/slices.json`, and that no Mojang code is shipped in the
converter or in any converted pack. They stay in the repo because without them
`slices.json` cannot be regenerated.

### GitHub

Public repo `M8SON/mc-pack-converter`, created with `gh` (already authenticated
with `repo` and `workflow` scopes). Push `master`. Description and topics set at
creation.

### CI

`.github/workflows/tests.yml` — pytest on push and PR, Python 3.11, Ubuntu.
`test_golden_conversion` is `skipif`-guarded on a local pack path and will skip
on CI; the other 207 tests run. A green badge goes in the README.

## B. CLI UX

Current interface:

```
mc-pack-converter convert SOURCE [-o OUT] [--target 26.2] [--report-only]
```

The interface shape does not change. What changes:

### Help

Every argument gets `help=`. The parser gets a description and an epilog with
one worked example.

### Target validation

`--target` uses `choices=` populated from the keys of
`mc_pack_converter/data/pack_format.json` (`1.8.9`, `26.1`, `26.1.2`, `26.2`),
so `-h` lists the valid versions and a typo produces argparse's own error
instead of a confusing conversion. No separate `--list-targets` flag; `-h`
covers it.

### Output naming

Default output is derived from the source stem and target: `MyPack.zip` →
`MyPack-26.2.zip`, written to the current directory. A source directory uses its
directory name. Explicit `-o` always wins. This replaces the fixed
`converted.zip` default, which silently overwrote the previous run.

### Output volume

Quiet by default:

- While running, one progress line per stage.
- On completion, a summary: counts by severity, the output path, and the report
  path.
- The two markdown reports are written **beside** the output zip
  (`MyPack-26.2-report.md`, `MyPack-26.2-null-textures.md`) in addition to
  inside it, where they already go today. Nobody unzips a pack to read a report.
- `-v/--verbose` additionally prints both reports to the terminal, which is
  exactly today's behavior, so nothing is lost.

The contact sheet already derives its name from the output path, so it follows
the new naming automatically (`MyPack-26.2-slices.png`). No change needed there.

With `--report-only` no zip is written, so the reports are written beside where
the zip *would* have gone, using the same derived stem. The summary names them.

Progress is emitted through a callback on the conversion call, not by `print()`
inside the pipeline. The CLI passes a callback that writes lines; a future GUI
passes one that updates a progress bar.

### Errors

A missing or unreadable source prints a single-line message and exits non-zero.
No traceback for a user error. Unexpected exceptions still propagate — this is
not a blanket `except`.

### Exit codes

Unchanged: 1 if any finding has severity ERROR, else 0.

## C. Testing

Extend `tests/test_cli_e2e.py`:

- default output name is derived from the source stem and target
- explicit `-o` overrides the derived name
- an invalid `--target` exits non-zero without running the pipeline
- the summary line is printed on a successful run
- both reports are written beside the output zip
- `-v` prints the full reports; the default run does not
- a missing source prints one line and exits non-zero, with no traceback

`test_golden_conversion` keeps its hardcoded local pack path and its `skipif`
guard. It degrades to a skip anywhere the pack is absent, including CI.

## Success criteria

1. `pip install .` in a clean venv, then `mc-pack-converter convert <pack>`
   produces a correctly named zip, two reports beside it, and a summary — with
   no other output. → verify by running it.
2. `mc-pack-converter convert --help` explains every flag and lists the four
   valid targets. → verify by reading the output.
3. Full suite green, including the new CLI tests. → `pytest`.
4. The repo is public at `github.com/M8SON/mc-pack-converter` with README,
   LICENSE, and a passing CI run. → verify the Actions run is green.

## Out of scope

- The Windows `.exe` and any GUI. Separate spec.
- Any change to conversion behavior. This phase must not alter a single
  converted byte; the corpus results and the golden test are the guard.
- Refactoring the stages or the pipeline.
- Publishing to PyPI.
