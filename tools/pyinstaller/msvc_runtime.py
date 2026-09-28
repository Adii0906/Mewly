"""
Build-time helper used by Mewly.spec.

Root cause of "DLL load failed while importing QtCore: The specified
procedure could not be found":

PyQt6-Qt6 ships its own, recent copies of the Microsoft C++ runtime
(msvcp140.dll, vcruntime140.dll, ...) next to Qt6Core.dll, because Qt is
built with a recent MSVC and needs functions that only exist in recent
runtimes.  PyInstaller's dependency analysis can instead pick up older copies
of the same DLL names (from the build PC's System32, the Python install, or
any folder on PATH) and put those in the bundle.  At run time Qt6Core.dll then
binds to the old runtime and the import fails with "procedure not found".

unify_msvc_runtime() collects every copy of each runtime DLL that the build
can see, keeps the one with the highest file version, and ships that single
copy at every location the app loads it from (bundle root and
PyQt6/Qt6/bin).  The runtime is backwards compatible, so the newest copy
serves both Python and Qt.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from typing import Dict, List, Optional, Set, Tuple

RUNTIME_DLLS = (
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "concrt140.dll",
)

Version = Tuple[int, int, int, int]
TocEntry = Tuple[str, str, str]


def file_version(path: str) -> Version:
    """Windows file version of *path* (0.0.0.0 if unknown / not on Windows)."""
    if sys.platform != "win32":
        return (0, 0, 0, 0)
    import ctypes
    from ctypes import wintypes

    class VS_FIXEDFILEINFO(ctypes.Structure):
        _fields_ = [(n, wintypes.DWORD) for n in (
            "dwSignature", "dwStrucVersion", "dwFileVersionMS", "dwFileVersionLS",
            "dwProductVersionMS", "dwProductVersionLS", "dwFileFlagsMask", "dwFileFlags",
            "dwFileOS", "dwFileType", "dwFileSubtype", "dwFileDateMS", "dwFileDateLS")]

    ver = ctypes.WinDLL("version")
    ver.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    ver.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    ver.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    ver.GetFileVersionInfoW.restype = wintypes.BOOL
    ver.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR,
                                   ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
    ver.VerQueryValueW.restype = wintypes.BOOL

    size = ver.GetFileVersionInfoSizeW(path, None)
    if not size:
        return (0, 0, 0, 0)
    buf = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(path, 0, size, buf):
        return (0, 0, 0, 0)
    ptr, length = ctypes.c_void_p(), wintypes.UINT()
    if not ver.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(length)) or not ptr.value:
        return (0, 0, 0, 0)
    info = ctypes.cast(ptr, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
    ms, ls = info.dwFileVersionMS, info.dwFileVersionLS
    return (ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF)


def qt_bin_dir() -> Optional[str]:
    spec = importlib.util.find_spec("PyQt6")
    if spec is None or not spec.submodule_search_locations:
        return None
    path = os.path.join(list(spec.submodule_search_locations)[0], "Qt6", "bin")
    return path if os.path.isdir(path) else None


def unify_msvc_runtime(binaries: List[TocEntry]) -> List[TocEntry]:
    qt_bin = qt_bin_dir()
    qt_dest = os.path.join("PyQt6", "Qt6", "bin")

    candidates: Dict[str, Set[str]] = {}
    dests: Dict[str, Set[str]] = {}
    kept: List[TocEntry] = []
    for dest, src, typ in binaries:
        name = os.path.basename(dest).lower()
        if name in RUNTIME_DLLS:
            candidates.setdefault(name, set()).add(os.path.normcase(os.path.abspath(src)))
            dests.setdefault(name, set()).add(dest)
        else:
            kept.append((dest, src, typ))

    extra_dirs = [d for d in (qt_bin, sys.base_prefix, os.path.dirname(sys.executable)) if d]
    for name in RUNTIME_DLLS:
        for d in extra_dirs:
            p = os.path.join(d, name)
            if os.path.isfile(p):
                candidates.setdefault(name, set()).add(os.path.normcase(os.path.abspath(p)))

    print("[msvc-runtime] choosing the newest copy of each MSVC runtime DLL:")
    for name in RUNTIME_DLLS:
        srcs = candidates.get(name)
        if not srcs:
            continue
        ranked = sorted(srcs, key=file_version, reverse=True)
        best = ranked[0]
        targets = set(dests.get(name, set())) | {name}
        if qt_bin and os.path.isfile(os.path.join(qt_bin, name)):
            targets.add(os.path.join(qt_dest, name))
        for dest in sorted(targets):
            kept.append((dest, best, "BINARY"))
        others = ", ".join(f"{'.'.join(map(str, file_version(s)))} {s}" for s in ranked[1:])
        print(f"  {name:28s} {'.'.join(map(str, file_version(best)))}  {best}"
              + (f"\n  {'':28s} (ignored older: {others})" if others else ""))
    return kept
