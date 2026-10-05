"""Report installed vs latest versions for Python and JavaScript dependencies.

Python packages are read from ``requirements.txt`` and compared against PyPI.
JavaScript libraries vendored in ``front-end/lib`` are compared against the
npm registry.

Usage:
    python check_versions.py
"""

import json
import re
import urllib.request
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = Path(__file__).with_name("requirements.txt")
JS_LIBS = {
    "marked": ROOT / "front-end" / "lib" / "marked.min.js",
    "dompurify": ROOT / "front-end" / "lib" / "purify.min.js",
}

PYPI_JSON = "https://pypi.org/pypi/{name}/json"
NPM_JSON = "https://registry.npmjs.org/{name}/latest"
TIMEOUT = 10


def parse_requirements(path: Path) -> list[str]:
    """Return the distribution names listed in a requirements file."""
    names: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "-")):
            continue
        line = line.split(";")[0].strip()
        name = re.split(r"[<>=!~\[ ]", line, maxsplit=1)[0].strip()
        if name:
            names.append(name)
    return names


def installed_version(name: str) -> str | None:
    """Return the installed Python version, or None if missing."""
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def js_installed_version(path: Path) -> str | None:
    """Return the version declared in a vendored JS library's header."""
    if not path.exists():
        return None
    head = path.read_text(encoding="utf-8", errors="ignore")[:1000]
    match = re.search(r"\bv(\d+\.\d+\.\d+)\b", head)
    return match.group(1) if match else None


def latest_version(name: str) -> str | None:
    """Return the latest Python version on PyPI, or None on failure."""
    try:
        with urllib.request.urlopen(PYPI_JSON.format(name=name), timeout=TIMEOUT) as resp:
            return json.load(resp)["info"]["version"]
    except Exception:
        return None


def npm_latest_version(name: str) -> str | None:
    """Return the latest JS version on npm, or None on failure."""
    try:
        with urllib.request.urlopen(NPM_JSON.format(name=name), timeout=TIMEOUT) as resp:
            return json.load(resp)["version"]
    except Exception:
        return None


def _version_key(version: str):
    return [int(part) if part.isdigit() else part for part in re.split(r"[.\-+]", version)]


def is_outdated(current: str, latest: str) -> bool:
    try:
        return _version_key(current) < _version_key(latest)
    except TypeError:
        return current != latest


def _status(current: str | None, latest: str | None) -> tuple[str, bool]:
    if current is None:
        return "NOT INSTALLED", True
    if latest is None:
        return "? (registry unreachable)", False
    if is_outdated(current, latest):
        return "OUTDATED", True
    return "up to date", False


def _print_row(name: str, current: str | None, latest: str | None) -> bool:
    status, flagged = _status(current, latest)
    print(f"{name:<38}{(current or '-'):<16}{(latest or '-'):<16}{status}")
    return flagged


def main() -> int:
    if not REQUIREMENTS.exists():
        print(f"requirements.txt not found at {REQUIREMENTS}")
        return 1

    outdated = 0

    names = parse_requirements(REQUIREMENTS)
    print(f"Python packages ({len(names)}) — installed vs PyPI latest\n")
    print(f"{'Package':<38}{'Installed':<16}{'Latest':<16}Status")
    print("-" * 84)
    for name in names:
        outdated += _print_row(name, installed_version(name), latest_version(name))

    print(f"\nJavaScript libraries ({len(JS_LIBS)}) — vendored vs npm latest\n")
    print(f"{'Library':<38}{'Installed':<16}{'Latest':<16}Status")
    print("-" * 84)
    for name, path in JS_LIBS.items():
        outdated += _print_row(name, js_installed_version(path), npm_latest_version(name))

    print()
    if outdated:
        print(f"{outdated} dependenc{'y' if outdated == 1 else 'ies'} need attention.")
    else:
        print("All dependencies are up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
