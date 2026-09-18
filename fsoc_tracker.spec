# PyInstaller spec for the offline standalone FSOC Tracker desktop application.
from PyInstaller.utils.hooks import collect_submodules


hiddenimports = collect_submodules("fsoc_tracker")

a = Analysis(
    ["src/fsoc_tracker/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("configs", "configs"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["torch", "ultralytics", "matplotlib", "scipy"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FSOC-Tracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
