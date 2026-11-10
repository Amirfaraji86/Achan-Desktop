"""Fail a frozen build when it does not contain the reviewed QML interface."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Tuple


REQUIRED_UI_MARKERS = (
    b"component BottomNavItem",
    b'LayoutMirroring.enabled: bridge.language === "fa"',
    b"id: powerGlow",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_packaged_ui(source_path: Path, app_dir: Path, relative_path: str) -> Tuple[Path, str]:
    """Check the exact QML file that the frozen app will load against source."""
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("The packaged UI path must stay inside the application bundle.")

    source = source_path.resolve(strict=True)
    application = app_dir.resolve(strict=True)
    if not (application / "Achan.exe").is_file():
        raise ValueError("Achan.exe is missing from the frozen application directory.")

    # PyInstaller 6 uses _internal as sys._MEIPASS; older versions use the
    # application directory itself. The runtime resolves QML from this root.
    contents = application / "_internal"
    resource_root = contents if contents.is_dir() else application
    packaged = resource_root / relative
    if not packaged.is_file():
        raise ValueError("Packaged QML is missing from the runtime resource directory: {}".format(packaged))

    source_bytes = source.read_bytes()
    for marker in REQUIRED_UI_MARKERS:
        if marker not in source_bytes:
            raise ValueError("Source QML is missing a required redesign marker: {}".format(marker.decode("ascii")))

    source_hash = _sha256(source)
    packaged_hash = _sha256(packaged)
    if source_hash != packaged_hash:
        raise ValueError(
            "Packaged QML does not match the reviewed source (source {}, package {}).".format(
                source_hash, packaged_hash
            )
        )

    glow_start = source_bytes.index(b"id: powerGlow")
    glow_block = source_bytes[glow_start:glow_start + 500]
    if b"visible: bridge.isConnected" not in glow_block:
        raise ValueError("The connection halo must only be visible after a successful connection.")

    return packaged, packaged_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Reviewed source QML file")
    parser.add_argument("--app-dir", required=True, type=Path, help="PyInstaller onedir output directory")
    parser.add_argument("--relative-path", required=True, help="QML path relative to PyInstaller's resource root")
    args = parser.parse_args()
    try:
        packaged, digest = validate_packaged_ui(args.source, args.app_dir, args.relative_path)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print("Packaged QML matches reviewed source: {} (SHA-256 {})".format(packaged, digest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
