from __future__ import annotations
import shutil, tempfile, zipfile
from dataclasses import dataclass
from pathlib import Path

from .pipeline import ConversionContext, Severity, run_pipeline
from .stages import STAGES
from .stages.ingest import prepare_working_copy
from .stages.package import write_output
from .report import render_conversion_report, render_null_texture_report
from .contact_sheet import ATLAS_1_14, build_contact_sheet

# The CLI's default target, shared so the GUI cannot drift from it. NOT
# derived from TARGETS: that list is string-sorted, so sorted(...)[-1] picks
# by lexical order, not version order — with a future 26.9 and 26.10 both
# present it returns 26.9, the older one. Bump this by hand whenever a newer
# target is added to data/pack_format.json.
DEFAULT_TARGET = "26.2"


def validate_source(source: Path) -> str | None:
    """The one-line reason this pack cannot be read, or None if it is fine.

    Shared so the GUI refuses exactly what the CLI refuses, in the same words.
    A file that is not a zip is the realistic first-run failure: a renamed
    .rar or a truncated download otherwise reaches zipfile.ZipFile and dumps
    a BadZipFile traceback at a non-developer.
    """
    if not source.exists():
        return f"no such pack: {source}"
    if source.is_file() and not zipfile.is_zipfile(source):
        return f"not a readable zip: {source}"
    return None


def out_path_beside_source(source: Path, target: str) -> Path:
    """Name the output after the source, in the SOURCE's folder.

    The GUI's rule, not the CLI's: an exe launched from Explorer has no
    meaningful working directory, and the folder the user is looking at is
    the only predictable place to put the result.
    """
    stem = source.stem if source.suffix.lower() == ".zip" else source.name
    return source.parent / f"{stem}-{target}.zip"


def _announce(stages, on_stage):
    """Wrap each stage so the caller is told before it runs."""
    total = len(stages)
    return [
        (name, lambda ctx, fn=fn, name=name, i=i: (on_stage(name, i, total), fn(ctx))[1])
        for i, (name, fn) in enumerate(stages, start=1)
    ]


def convert(source: Path, out_path: Path, target: str,
            report_only: bool, on_stage=None, on_sheet=None) -> ConversionContext:
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
        reports = {
            "conversion-report.md": render_conversion_report(ctx.findings),
            "null-texture-report.md": render_null_texture_report(ctx.findings),
        }
        if not report_only:
            write_output(ctx, out_path, reports)
            sheet = out_path.with_name(out_path.stem + "-slices.png")
            rels = [out for src, out in ctx.sliced if src in ATLAS_1_14]
            try:
                n = build_contact_sheet(ctx.root, rels, sheet)
                if n and on_sheet is not None:
                    on_sheet(sheet, n)
            except Exception as exc:  # fail-soft: a review artifact, not the product
                ctx.add("contact_sheet", Severity.WARNING,
                        f"contact sheet failed: {exc!r}")
        return ctx
    finally:
        shutil.rmtree(workroot, ignore_errors=True)


@dataclass(frozen=True)
class JobResult:
    """Everything a front end needs to report on one conversion."""
    ctx: ConversionContext
    out_path: Path
    reports: dict[str, Path]
    report_texts: dict[str, str]
    sheet: Path | None
    wrote_zip: bool

    @property
    def counts(self) -> dict[Severity, int]:
        counts = {s: 0 for s in Severity}
        for f in self.ctx.findings:
            counts[f.severity] += 1
        return counts

    @property
    def has_errors(self) -> bool:
        return any(f.severity is Severity.ERROR for f in self.ctx.findings)


def run_job(source: Path, out_path: Path, target: str,
            report_only: bool = False, *, on_stage=None, on_sheet=None) -> JobResult:
    """Convert one pack and write its reports beside the output.

    The whole job, shared by the CLI and the GUI: everything main() used to do
    between validating the source and printing. Callers differ only in how
    they render the JobResult.
    """
    captured: list[Path] = []

    def _sheet(path: Path, n: int) -> None:
        captured.append(path)
        if on_sheet is not None:
            on_sheet(path, n)

    ctx = convert(source, out_path, target, report_only,
                  on_stage=on_stage, on_sheet=_sheet)

    texts = {
        "report": render_conversion_report(ctx.findings),
        "null-textures": render_null_texture_report(ctx.findings),
    }
    written = {}
    for label, text in texts.items():
        p = out_path.with_name(f"{out_path.stem}-{label}.md")
        p.write_text(text)
        written[label] = p

    return JobResult(
        ctx=ctx,
        out_path=out_path,
        reports=written,
        report_texts=texts,
        sheet=captured[0] if captured else None,
        # Whether THIS run produced the zip, not whether a file of that name is
        # on disk: a leftover zip from a previous run made --report-only claim
        # it had written one.
        wrote_zip=not report_only,
    )
