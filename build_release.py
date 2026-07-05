#!/usr/bin/env python3
"""Build packaged Ignitron Preset Tools release artifacts."""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "Ignitron Preset Tools v1.1.1"
ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
OUTPUT = ROOT / "output"


def run(command):
    print(">", " ".join(str(part) for part in command), flush=True)
    subprocess.check_call([str(part) for part in command], cwd=ROOT)


def add_data(source, target):
    return f"{source}{os.pathsep}{target}"


def clean():
    for path in (ROOT / "dist", ROOT / "build", OUTPUT):
        if path.exists():
            shutil.rmtree(path)
    OUTPUT.mkdir(parents=True, exist_ok=True)


def build():
    clean()
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--hidden-import",
        "serial",
        "--hidden-import",
        "serial.tools.list_ports",
        "--hidden-import",
        "reportlab",
        "--collect-submodules",
        "reportlab",
        "--add-data",
        add_data(SOURCE / "reference", "reference"),
        "--add-data",
        add_data(SOURCE / "preset_chart.py", "."),
        "--add-data",
        add_data(SOURCE / "preset_puller.py", "."),
        "--add-data",
        add_data(SOURCE / "preset_converter.py", "."),
        SOURCE / "ignitron_preset_tools_v1.1.1.py",
    ]
    run(command)
    package()


def package():
    system = platform.system()
    if system == "Windows":
        package_root = ROOT / "dist" / APP_NAME
        shutil.copy2(ROOT / "README.md", package_root / "README.txt")
        archive_base = OUTPUT / f"{APP_NAME}-windows"
        shutil.make_archive(str(archive_base), "zip", root_dir=package_root.parent, base_dir=package_root.name)
    elif system == "Darwin":
        app_bundle = ROOT / "dist" / f"{APP_NAME}.app"
        archive_base = OUTPUT / f"{APP_NAME}-macos"
        shutil.make_archive(str(archive_base), "zip", root_dir=app_bundle.parent, base_dir=app_bundle.name)
    else:
        package_root = ROOT / "dist" / APP_NAME
        archive_base = OUTPUT / f"{APP_NAME}-linux"
        shutil.make_archive(str(archive_base), "zip", root_dir=package_root.parent, base_dir=package_root.name)

    for artifact in sorted(OUTPUT.glob("*.zip")):
        print(f"Built {artifact} ({artifact.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    build()
