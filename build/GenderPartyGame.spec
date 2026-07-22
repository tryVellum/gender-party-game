from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


ROOT = Path(SPECPATH).resolve().parent.parent
ICON_PATH = ROOT / "assets" / "gender-party.ico"
VERSION_FILE = ROOT / "build" / "version_info.txt"

hidden_imports = sorted(
    set(
        collect_submodules("engineio.async_drivers")
        + collect_submodules("socketio")
        + collect_submodules("pystray")
        + [
            "pystray._win32",
            "simple_websocket",
        ]
    )
)

datas = [
    (str(ROOT / "templates"), "templates"),
    (str(ROOT / "static"), "static"),
    (str(ROOT / "data"), "data"),
    (str(ROOT / "assets"), "assets"),
]

analysis = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "ruff"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="GenderPartyGame",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH),
    version=str(VERSION_FILE),
)

collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GenderPartyGame",
)
