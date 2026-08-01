"""Read pack.mcmeta the way Minecraft does.

Minecraft parses this file with GSON, which tolerates malformations that
Python's strict json.loads rejects. A pack that loads perfectly well in-game
is therefore not necessarily parseable here — and rejecting it means refusing
to convert the pack at all.

Three malformations occur in the wild, all measured across a 173-pack corpus
in which 12 packs were unconvertible because of them:

  * a UTF-8 BOM, from Windows editors (5 packs)
  * a backslash before a character that is not a valid JSON escape, e.g.
    "\\Made by", "\\@cellsaver", "\\ [by Gosu]" (5 packs)
  * a raw control character inside a string — a literal CRLF, or the \\x15
    bytes Minecraft's old colour codes use (2 packs)

All three live inside the `description` string, which is decorative. The
sanitiser below is deliberately narrow: it only rewrites what appears INSIDE
string literals, so a genuine structural error still raises.
"""
from __future__ import annotations
import json
from pathlib import Path

_VALID_ESCAPES = '"\\/bfnrtu'
_CONTROL_MAP = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}


def strip_comments(text: str) -> str:
    """Remove // and /* */ comments that sit OUTSIDE string literals.

    Minecraft's parser tolerates them and pack authors use them — one corpus
    model annotates its cube elements with `// The inner block`. String
    awareness is essential rather than pedantic: the same file carries
    `http://www.planetminecraft.com/...` inside a string, which a naive
    stripper would truncate.
    """
    out: list[str] = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True; out.append(ch); i += 1; continue
        if ch == "/" and i + 1 < n:
            if text[i + 1] == "/":
                while i < n and text[i] != "\n":
                    i += 1
                continue
            if text[i + 1] == "*":
                end = text.find("*/", i + 2)
                i = n if end == -1 else end + 2
                continue
        out.append(ch); i += 1
    return "".join(out)


def loads_lenient(text: str) -> dict:
    """Parse JSON the way Minecraft does: comments and sloppy strings allowed.

    Strict first, so a well-formed file costs nothing.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(strip_comments(text))
    except json.JSONDecodeError:
        return json.loads(sanitize(strip_comments(text)))


def sanitize(text: str) -> str:
    """Repair GSON-tolerated malformations inside string literals."""
    out: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if not in_string:
            if ch == '"':
                in_string = True
            out.append(ch)
            continue
        if escaped:
            # keep a real escape; drop the backslash before anything else
            if ch in _VALID_ESCAPES:
                out.append("\\")
            out.append(ch)
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = False
            out.append(ch)
            continue
        if ord(ch) < 0x20:
            # a raw control character: escape the meaningful ones, drop the rest
            out.append(_CONTROL_MAP.get(ch, ""))
            continue
        out.append(ch)
    return "".join(out)


def read_mcmeta(path: Path) -> dict:
    """Parse a pack.mcmeta, tolerating what Minecraft tolerates.

    Raises json.JSONDecodeError if the file is structurally broken — leniency
    covers known in-the-wild sloppiness, not arbitrary garbage.
    """
    return loads_lenient(path.read_text(encoding="utf-8-sig"))  # utf-8-sig drops a BOM
