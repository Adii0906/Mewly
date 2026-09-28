"""
Pre-flight checks for the Windows .exe build (run by build.bat inside the
isolated .build-venv).  Fails fast, with a clear reason, on every known cause
of broken PyQt6 builds instead of producing an .exe that crashes on start.
"""
from __future__ import annotations

import importlib.metadata as md
import os
import struct
import sys

errors: list[str] = []


def version(dist: str) -> str | None:
    try:
        return md.version(dist)
    except md.PackageNotFoundError:
        return None


def major_minor(v: str) -> tuple[int, int]:
    parts = (v.split(".") + ["0", "0"])[:2]
    return int(parts[0]), int("".join(ch for ch in parts[1] if ch.isdigit()) or 0)


print(f"[check] Python {sys.version.split()[0]} ({struct.calcsize('P') * 8}-bit) at {sys.executable}")

if sys.platform != "win32":
    errors.append("The .exe must be built on Windows.")
if struct.calcsize("P") != 8:
    errors.append("32-bit Python detected. Install 64-bit Python from python.org (PyQt6 is 64-bit only).")
if sys.version_info < (3, 10):
    errors.append("Python 3.10 or newer is required.")
if sys.prefix == sys.base_prefix:
    errors.append("Not running inside the isolated build venv (run build.bat instead of calling PyInstaller directly).")
if os.path.isdir(os.path.join(sys.base_prefix, "conda-meta")) and not os.getenv("MEWLY_ALLOW_CONDA"):
    errors.append(
        "The base Python is Anaconda/conda. Conda ships its own Qt and MSVC DLLs that "
        "conflict with PyQt6 from pip. Use a python.org Python for building "
        "(or set MEWLY_ALLOW_CONDA=1 to try anyway)."
    )

for other in ("PySide6", "PySide2", "PyQt5"):
    if version(other):
        errors.append(f"{other} is installed in the build environment; only PyQt6 may be present.")

pyqt, qt = version("PyQt6"), version("PyQt6-Qt6")
pyinstaller = version("pyinstaller")
print(f"[check] PyQt6 {pyqt}  PyQt6-Qt6 {qt}  PyQt6-sip {version('PyQt6-sip')}  "
      f"PyInstaller {pyinstaller}  hooks-contrib {version('pyinstaller-hooks-contrib')}")
if not pyqt or not qt:
    errors.append("PyQt6 / PyQt6-Qt6 are not installed.")
elif major_minor(qt) < major_minor(pyqt):
    errors.append(
        f"PyQt6 {pyqt} needs PyQt6-Qt6 >= {'.'.join(map(str, major_minor(pyqt)))} but {qt} is installed "
        "(this exact mismatch causes 'procedure could not be found')."
    )
if not pyinstaller or major_minor(pyinstaller) < (6, 10):
    errors.append("PyInstaller 6.10 or newer is required.")

if not errors:
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: F401
        runtime, built = QtCore.qVersion(), QtCore.QT_VERSION_STR
        print(f"[check] Qt runtime {runtime} (PyQt6 built against {built})")
        if major_minor(runtime) < major_minor(built):
            errors.append(f"Qt runtime {runtime} is older than the Qt PyQt6 was built for ({built}).")
        plugin = os.path.join(os.path.dirname(QtCore.__file__), "Qt6", "plugins", "platforms", "qwindows.dll")
        if not os.path.isfile(plugin):
            errors.append(f"Qt Windows platform plugin missing: {plugin}")
    except ImportError as exc:
        errors.append(
            f"PyQt6 cannot be imported even in the clean build environment: {exc}. "
            "Something outside Python is injecting DLLs (e.g. an old msvcp140.dll in the Python "
            "folder). Reinstall Python from python.org."
        )
    try:
        import psutil  # noqa: F401
        from pynput import keyboard  # noqa: F401
    except Exception as exc:
        errors.append(f"Runtime dependency failed to import: {exc}")

if errors:
    print("\n[check] BUILD ENVIRONMENT NOT OK:")
    for e in errors:
        print("  - " + e)
    sys.exit(1)
print("[check] Build environment OK")
