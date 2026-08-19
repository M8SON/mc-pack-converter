"""The page's boot sequence, exercised in node against the real app.js.

Python cannot see this bug: it lives entirely in the order pywebview installs
its JavaScript bridge. It shipped to the user once already -- a live window
with a dirt background and no version list, wired to nothing.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

CHECK = Path(__file__).parent / "boot_check.mjs"
APP = Path(__file__).parents[2] / "mc_pack_converter" / "webui" / "assets" / "app.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_page_boots_once_and_only_when_the_bridge_is_callable():
    r = subprocess.run(["node", str(CHECK), str(APP)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr + r.stdout
