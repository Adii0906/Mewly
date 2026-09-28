"""
PyInstaller runtime hook for Mewly (runs inside the .exe before main.py).

Makes the frozen app independent of whatever is installed on the user's PC:

1. Preloads the bundled MSVC runtime DLLs by full path.  Once a DLL is
   loaded, Windows reuses it for every later import of that name, so
   Qt6Core.dll binds to the bundled (new) runtime and never to an older copy
   that happens to sit in System32, next to the .exe (e.g. a Downloads
   folder), or on PATH.
2. Puts the bundle's own DLL folders first in the DLL search path.
3. Drops Qt environment variables that point at some *other* Qt install
   (a global QT_PLUGIN_PATH from another app makes Qt load incompatible
   plugins).  Values that point inside the bundle are kept.
"""
import os
import sys

if sys.platform == "win32" and getattr(sys, "frozen", False):
    _base = os.path.normcase(os.path.abspath(sys._MEIPASS))  # type: ignore[attr-defined]

    for _var in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH", "QML_IMPORT_PATH"):
        _val = os.environ.get(_var)
        if _val and not all(
            os.path.normcase(os.path.abspath(p)).startswith(_base)
            for p in _val.split(os.pathsep) if p
        ):
            del os.environ[_var]

    _qt_bin = os.path.join(sys._MEIPASS, "PyQt6", "Qt6", "bin")  # type: ignore[attr-defined]
    _MEWLY_DLL_DIRS = []   # keep the handles alive for the whole process
    for _d in (_qt_bin, sys._MEIPASS):  # type: ignore[attr-defined]
        if os.path.isdir(_d):
            try:
                _MEWLY_DLL_DIRS.append(os.add_dll_directory(_d))
            except OSError:
                pass

    import ctypes

    # Dependency order: vcruntime first, then the C++ library on top of it.
    for _name in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll",
                  "msvcp140_1.dll", "msvcp140_2.dll", "concrt140.dll"):
        for _d in (_qt_bin, sys._MEIPASS):  # type: ignore[attr-defined]
            _p = os.path.join(_d, _name)
            if os.path.isfile(_p):
                try:
                    ctypes.WinDLL(_p)
                except OSError:
                    pass
                break
