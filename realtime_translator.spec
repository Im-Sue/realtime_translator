# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_dir = Path(SPECPATH)
workspace_dir = project_dir.parent

hiddenimports = []
hiddenimports += collect_submodules("realtime_translator.pb2")
hiddenimports += collect_submodules("realtime_translator.core")
hiddenimports += collect_submodules("realtime_translator.gui")

datas = [
    (str(project_dir / "config.yaml.example"), "."),
    (str(project_dir / "README.md"), "."),
    (str(project_dir / "README_EN.md"), "."),
]


a = Analysis(
    [str(project_dir / "main.py")],
    pathex=[str(workspace_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="realtime_translator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="realtime_translator",
)
