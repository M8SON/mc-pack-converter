"""The report: one self-contained HTML file, opened in whatever browser the
user already has.

This replaces the native window the program used to open. That window needed
a system WebKit that pip cannot install, which made the program Windows-only
in practice; the page it displayed was already self-contained, so writing it
to a file costs nothing and works everywhere.
"""
from __future__ import annotations
import base64
import json
import re
from pathlib import Path

from ..pipeline import Severity

_SEVERITY_RANK = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


def build_model(result, sheet: dict, update: str | None = None) -> dict:
    """Everything the page renders, as plain JSON-serialisable data.

    Sorted by severity because 408 of the reference pack's 413 findings are
    INFO: unsorted, the five that matter are five lines lost in four hundred.
    """
    counts = result.counts
    return {
        "headline": result.out_path.name,
        "findings": [
            {"severity": f.severity.value, "stage": f.stage,
             "message": f.message, "path": f.path}
            for f in sorted(result.ctx.findings,
                            key=lambda f: _SEVERITY_RANK[f.severity])
        ],
        "counts": {s.value: counts[s] for s in Severity},
        "out_path": str(result.out_path),
        "update": update,
        "sheet": sheet,
    }


ASSETS = Path(__file__).parent / "assets"


def _safe_json(model: dict) -> str:
    """JSON that cannot end the script block that contains it.

    Finding messages carry pack-controlled text, and a pack whose name or
    mcmeta description contains '</script>' would otherwise terminate the
    block early and spill the rest of the model onto the page as markup.
    Escaping the '<' is enough and leaves the string identical once parsed.
    U+2028/U+2029 are escaped too because they are line terminators in
    JavaScript and would otherwise break the object literal.
    """
    return (json.dumps(model)
            .replace("<", "\\u003c")
            .replace(" ", "\\u2028")
            .replace(" ", "\\u2029"))


_CSS_URL = re.compile(r'url\("([^"/]+\.png)"\)')


def _inline_css_images(css: str) -> str:
    """Every url("name.png") in app.css, resolved to a data: URI.

    The report is written beside the converted pack, not beside the assets
    it ships with (app.css:1), so a relative url() dangles the moment the
    report is opened -- the terrain background never loads. grass.png
    (481 bytes) and wall.png (8,356 bytes) total 8,837 bytes; base64 that is
    about 11.8KB, cheap against a multi-MB report.
    """
    def inline(m: re.Match) -> str:
        data = (ASSETS / m.group(1)).read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return f'url("data:image/png;base64,{b64}")'
    return _CSS_URL.sub(inline, css)


def render_html(model: dict) -> str:
    """The whole report as one string: no stylesheet link, no script src, no
    request of any kind once it is on disk."""
    css = _inline_css_images((ASSETS / "app.css").read_text(encoding="utf-8"))
    js = (ASSETS / "app.js").read_text(encoding="utf-8")
    body = (ASSETS / "index.html").read_text(encoding="utf-8")
    return body.format(css=css, js=js, model=_safe_json(model))
