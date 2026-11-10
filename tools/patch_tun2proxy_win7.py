"""Apply Achan's narrowly-scoped Windows 7 fix to tun2proxy's pinned dependency."""
from __future__ import annotations

import argparse
from pathlib import Path

PACKAGE_VERSION = "7.0.9"
OLD_SNIPPET = r'let tun_name = format!("\"{iface}\"");'
NEW_SNIPPET = "let tun_name = iface.to_owned();"


def patch_windows_source(source_path: Path) -> bool:
    """Remove shell-style quote characters from a netsh argv element.

    Rust's Command API already quotes arguments containing spaces. Passing
    quote characters inside the value makes netsh search for an adapter name
    that includes literal quotes, which produces 'Element not found' on Win7.
    """
    content = source_path.read_text(encoding="utf-8")
    old_count = content.count(OLD_SNIPPET)
    if old_count == 0:
        if NEW_SNIPPET in content:
            return False
        raise RuntimeError("Expected tproxy-config 7.0.9 netsh DNS code was not found.")
    if old_count != 1:
        raise RuntimeError("Expected exactly one unpatched netsh DNS argument.")
    source_path.write_text(content.replace(OLD_SNIPPET, NEW_SNIPPET), encoding="utf-8")
    return True


def locate_source(cargo_home: Path) -> Path:
    matches = list((cargo_home / "registry" / "src").glob(
        "*/tproxy-config-%s/src/windows.rs" % PACKAGE_VERSION
    ))
    if len(matches) != 1:
        raise RuntimeError(
            "Expected one cached tproxy-config %s source, found %d."
            % (PACKAGE_VERSION, len(matches))
        )
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cargo-home", required=True, type=Path)
    args = parser.parse_args()
    source = locate_source(args.cargo_home)
    changed = patch_windows_source(source)
    print("%s: %s" % ("Patched" if changed else "Already patched", source))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
