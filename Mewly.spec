# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Mewly (Windows, 64-bit, single-file, no console).

Build with build.bat (it creates a clean build environment first), or:
    python -m PyInstaller --noconfirm --clean Mewly.spec

Output: dist/Mewly.exe — self-contained: Python, PyQt6 + Qt (incl. the
Windows platform plugin), the MSVC C++ runtime and all assets are bundled.
"""
import os
import sys

ROOT = os.path.abspath(SPECPATH)  # noqa: F821  (injected by PyInstaller)
sys.path.insert(0, os.path.join(ROOT, "tools", "pyinstaller"))
from msvc_runtime import unify_msvc_runtime  # noqa: E402

a = Analysis(  # noqa: F821
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "assets", "sprites"), os.path.join("assets", "sprites")),
        (os.path.join(ROOT, "assets", "icon.ico"), "assets"),
    ],
    # pynput chooses its OS backend with a dynamic import.
    hiddenimports=[
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "pynput._util.win32",
        "pynput._util.win32_vks",
    ],
    hookspath=[],
    runtime_hooks=[os.path.join(ROOT, "tools", "pyinstaller", "rthook_mewly.py")],
    # Never bundle a second Qt binding (conflicting Qt DLLs) or unused libs.
    excludes=["PySide6", "PySide2", "PyQt5", "tkinter", "PIL", "numpy"],
    noarchive=False,
)

# One consistent (newest) MSVC runtime for Python and Qt — see msvc_runtime.py.
a.binaries = unify_msvc_runtime(a.binaries)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Mewly",
    icon=os.path.join(ROOT, "assets", "icon.ico"),
    console=False,
    debug=False,
    strip=False,
    upx=False,            # UPX-compressed Qt DLLs are a common source of load failures
    runtime_tmpdir=None,
    bootloader_ignore_signals=False,
    disable_windowed_traceback=False,
)
