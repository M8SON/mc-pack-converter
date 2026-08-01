"""Lenient pack.mcmeta reading.

Minecraft parses pack.mcmeta with GSON, which tolerates malformations that
json.loads rejects outright. Every case here is taken verbatim from the
173-pack test corpus, where 12 packs were unconvertible because of them.
"""
import json
import pytest
from mc_pack_converter.mcmeta import read_mcmeta

BOM = "﻿"


def _write(tmp_path, text, encoding="utf-8"):
    p = tmp_path / "pack.mcmeta"
    p.write_text(text, encoding=encoding)
    return p


def test_plain_file(tmp_path):
    p = _write(tmp_path, '{"pack":{"pack_format":1,"description":"hi"}}')
    assert read_mcmeta(p)["pack"]["pack_format"] == 1


def test_utf8_bom(tmp_path):
    p = _write(tmp_path, BOM + '{"pack":{"pack_format":1,"description":"hi"}}')
    assert read_mcmeta(p)["pack"]["pack_format"] == 1


def test_backslash_before_a_non_escape_character(tmp_path):
    # fZerocTwo6xf32.zip: "§f\Made by: §6§o\@cellsaver"
    p = _write(tmp_path,
               '{"pack":{"pack_format":1,'
               '"description":"\\u00A7f\\Made by: \\u00A76\\u00A7o\\@cellsaver"}}')
    d = read_mcmeta(p)
    assert d["pack"]["pack_format"] == 1
    # the stray backslashes go, the valid § escapes survive
    assert d["pack"]["description"] == "§fMade by: §6§o@cellsaver"


def test_backslash_before_a_space(tmp_path):
    # ! 6NoLimit FPS.zip: "§b\ [by Gosu]"
    p = _write(tmp_path,
               '{"pack":{"pack_format":1,"description":"\\u00A7b\\ [by Gosu]"}}')
    assert read_mcmeta(p)["pack"]["description"] == "§b [by Gosu]"


def test_literal_control_characters_inside_a_string(tmp_path):
    # !Satisfying Candy Pack.zip has a raw CRLF inside the description
    p = _write(tmp_path,
               '{"pack":{"pack_format":1,"description":"line1\r\nline2"}}')
    d = read_mcmeta(p)
    assert d["pack"]["pack_format"] == 1
    assert "line1" in d["pack"]["description"]
    assert "line2" in d["pack"]["description"]


def test_minecraft_formatting_bytes_inside_a_string(tmp_path):
    # \x15 formatting bytes appear in real pack names and descriptions
    p = _write(tmp_path,
               '{"pack":{"pack_format":1,"description":"a\x15b"}}')
    assert read_mcmeta(p)["pack"]["pack_format"] == 1


def test_valid_escapes_are_preserved(tmp_path):
    p = _write(tmp_path,
               '{"pack":{"pack_format":1,"description":"a\\"b\\\\c\\nd\\u00A7e"}}')
    assert read_mcmeta(p)["pack"]["description"] == 'a"b\\c\nd§e'


def test_whitespace_outside_strings_is_untouched(tmp_path):
    p = _write(tmp_path, '{\r\n  "pack": {\r\n    "pack_format": 1\r\n  }\r\n}\r\n')
    assert read_mcmeta(p)["pack"]["pack_format"] == 1


def test_genuinely_broken_file_still_raises(tmp_path):
    """Leniency must not become 'never fails' — a real syntax error still does."""
    p = _write(tmp_path, '{"pack": {"pack_format": ')
    with pytest.raises(json.JSONDecodeError):
        read_mcmeta(p)


# --- lenient JSON shared with model files -----------------------------------

def test_strip_comments_removes_line_comments(tmp_path):
    from mc_pack_converter.mcmeta import loads_lenient
    d = loads_lenient('{"a": 1, // trailing note\n "b": 2}')
    assert d == {"a": 1, "b": 2}


def test_strip_comments_removes_block_comments(tmp_path):
    from mc_pack_converter.mcmeta import loads_lenient
    assert loads_lenient('{"a": /* mid */ 1}') == {"a": 1}


def test_a_url_inside_a_string_survives(tmp_path):
    """'//' inside a string is not a comment.

    A real corpus model carries http://www.planetminecraft.com/... in its
    __comment field, next to genuine // comments elsewhere in the file.
    """
    from mc_pack_converter.mcmeta import loads_lenient
    d = loads_lenient('{"c": "see http://example.com/x", "a": 1 // note\n}')
    assert d["c"] == "see http://example.com/x"
    assert d["a"] == 1


def test_lenient_json_still_rejects_real_breakage(tmp_path):
    import json
    import pytest as _pytest
    from mc_pack_converter.mcmeta import loads_lenient
    with _pytest.raises(json.JSONDecodeError):
        loads_lenient('{"a": ')
