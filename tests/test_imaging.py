from pathlib import Path
from PIL import Image
from mc_pack_converter.imaging import png_size, is_valid_png, crop_paste, slice_sheet

def _make(path: Path, size, color=(255,0,0,255)):
    Image.new("RGBA", size, color).save(path)

def test_png_size(tmp_path):
    p = tmp_path/"a.png"; _make(p,(16,32))
    assert png_size(p) == (16,32)

def test_is_valid_png_false_on_empty(tmp_path):
    p = tmp_path/"z.png"; p.write_bytes(b"")
    assert is_valid_png(p) is False

def test_slice_sheet_writes_named_crops(tmp_path):
    sheet = tmp_path/"widgets.png"; _make(sheet,(256,256))
    out = tmp_path/"sprites"; out.mkdir()
    written = slice_sheet(sheet, out, [{"name":"hotbar","x":0,"y":0,"w":182,"h":22}])
    assert (out/"hotbar.png").exists()
    assert png_size(out/"hotbar.png") == (182,22)

def test_crop_paste_produces_out_size(tmp_path):
    src = tmp_path/"chest.png"; _make(src,(64,64))
    dst = tmp_path/"out.png"
    crop_paste(src, dst, [{"src":[0,0,14,14],"dst":[0,0,14,14]}], out_size=(64,64))
    assert png_size(dst) == (64,64)
