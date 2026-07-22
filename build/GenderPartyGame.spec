from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


# SPEC is the complete path of this spec file. The project root is the
# parent of the directory that contains build/GenderPartyGame.spec.
SPEC_FILE = Path(SPEC).resolve()
ROOT = SPEC_FILE.parent.parent

LAUNCHER_PATH = ROOT / "launcher.py"
if not LAUNCHER_PATH.is_file():
    raise FileNotFoundError(
        f"Launcher script was not found: {LAUNCHER_PATH}. "
        f"Resolved spec file: {SPEC_FILE}"
    )
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
    [str(LAUNCHER_PATH)],
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
