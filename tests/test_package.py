import zipfile
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.package import write_output

def test_write_zip(mini_pack, tmp_path):
    root = mini_pack()
    ctx = ConversionContext(root=root)
    out = tmp_path/"converted.zip"
    write_output(ctx, out, {"conversion-report.md": "# hi"})
    assert out.exists()
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert any(n.endswith("pack.mcmeta") for n in names)
    assert any(n.endswith("conversion-report.md") for n in names)
