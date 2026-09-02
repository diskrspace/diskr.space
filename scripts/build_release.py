#!/usr/bin/env python3
"""Build a self-contained ZIP release containing the backend and Vue dist."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_frontend_build(install: bool) -> None:
    frontend = ROOT / "frontend"
    if install:
        subprocess.run(["npm", "ci"], cwd=frontend, check=True)
    subprocess.run(["npm", "run", "build"], cwd=frontend, check=True)


def copy_release_tree(destination: Path, version: str) -> Path:
    release_root = destination / f"diskr.space-{version}"
    release_root.mkdir()
    files = (
        "__init__.py",
        "diskrspace.py",
        "setup.py",
        "requirements.txt",
        ".env.example",
        "README.md",
        "LICENSE",
        "ChangeLog.txt",
    )
    for name in files:
        shutil.copy2(ROOT / name, release_root / name)
    for directory in ("db", "web"):
        shutil.copytree(
            ROOT / directory,
            release_root / directory,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    dist = ROOT / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        raise RuntimeError("frontend/dist/index.html 不存在，请先构建前端")
    shutil.copytree(dist, release_root / "frontend" / "dist")
    return release_root


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-frontend-install",
        action="store_true",
        help="跳过 npm ci，仅执行 npm run build",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "release",
        help="ZIP 输出目录（默认：release）",
    )
    args = parser.parse_args()

    from web import __version__

    run_frontend_build(not args.skip_frontend_install)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="diskrspace-release-") as temp:
        release_root = copy_release_tree(Path(temp), __version__)
        archive = args.output_dir / f"diskr.space-{__version__}.zip"
        if archive.exists():
            archive.unlink()
        with ZipFile(archive, "w", ZIP_DEFLATED) as zip_file:
            for path in release_root.rglob("*"):
                if path.is_file():
                    zip_file.write(path, path.relative_to(Path(temp)))
    print(f"Release created: {archive}")


if __name__ == "__main__":
    main()
