from __future__ import annotations

import argparse
import re
from pathlib import Path


VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[.-][A-Za-z0-9]+)?$")


def parse_version(version: str) -> tuple[int, int, int, int]:
    """Convert a semantic release version to a Windows four-part version."""
    match = VERSION_PATTERN.fullmatch(version.strip())
    if match is None:
        raise ValueError(f"Unsupported release version: {version}")

    major, minor, patch = (int(value) for value in match.groups())
    return major, minor, patch, 0


def render_version_info(version: str) -> str:
    """Render a PyInstaller Windows VERSIONINFO resource file."""
    numeric = parse_version(version)
    numeric_text = ", ".join(str(value) for value in numeric)

    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({numeric_text}),
    prodvers=({numeric_text}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [
          StringStruct(u'CompanyName', u'tryVellum'),
          StringStruct(u'FileDescription', u'Gender Party Game'),
          StringStruct(u'FileVersion', u'{version}'),
          StringStruct(u'InternalName', u'GenderPartyGame'),
          StringStruct(u'LegalCopyright', u'MIT License'),
          StringStruct(u'OriginalFilename', u'GenderPartyGame.exe'),
          StringStruct(u'ProductName', u'Gender Party Game'),
          StringStruct(u'ProductVersion', u'{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""


def main() -> None:
    """Generate the Windows version resource used by PyInstaller."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        render_version_info(arguments.version),
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
