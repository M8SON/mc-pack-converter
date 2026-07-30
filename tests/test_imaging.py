from pathlib import Path
from PIL import Image
from mc_pack_converter.imaging import png_size, is_valid_png, crop_paste

def _make(path: Path, size, color=(255,0,0,255)):
    Image.new("RGBA", size, color).save(path)

def test_png_size(tmp_path):
    p = tmp_path/"a.png"; _make(p,(16,32))
    assert png_size(p) == (16,32)

def test_is_valid_png_false_on_empty(tmp_path):
    p = tmp_path/"z.png"; p.write_bytes(b"")
    assert is_valid_png(p) is False

def test_crop_paste_produces_out_size(tmp_path):
    src = tmp_path/"chest.png"; _make(src,(64,64))
    dst = tmp_path/"out.png"
    crop_paste(src, dst, [{"src":[0,0,14,14],"dst":[0,0,14,14]}], out_size=(64,64))
    assert png_size(dst) == (64,64)
