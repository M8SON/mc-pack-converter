# PyInstaller build definition.  Build with:  pyinstaller packaging/mcpc.spec
#
# onefile, because a single .exe is the only shape a pack zip can be dragged
# onto; onedir would hand the user a folder of DLLs. The cost is a 2-5s cold
# start while the binary unpacks to a temp directory.
#
# collect_data_files picks up the 14 JSON tables under mc_pack_converter/data.
# They must be bundled: load_table resolves them via Path(__file__).parent
# (data/__init__.py:7), which works under PyInstaller only if they are present
# in the extracted tree. Using collect_data_files rather than --add-data also
# sidesteps the ';' vs ':' path-separator difference between platforms.
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("mc_pack_converter", includes=["data/*.json"])

a = Analysis(
    ["mcpc_entry.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "tkinter", "tkinter.filedialog", "tkinter.messagebox", "tkinter.ttk",
        "PIL", "PIL.Image",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MCPackConverter",
    debug=False,
    strip=False,
    upx=False,
    console=False,          # no console window; every error must reach a dialog
    disable_windowed_traceback=False,
)
