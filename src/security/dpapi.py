from __future__ import annotations

import ctypes
from ctypes import wintypes


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


_crypt32 = ctypes.windll.crypt32
_kernel32 = ctypes.windll.kernel32


def _bytes_to_blob(data: bytes) -> _DATA_BLOB:
    buf = (ctypes.c_byte * len(data)).from_buffer_copy(data)
    return _DATA_BLOB(cbData=len(data), pbData=ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))


def _blob_to_bytes(blob: _DATA_BLOB) -> bytes:
    return ctypes.string_at(blob.pbData, blob.cbData)


def protect(data: bytes, *, entropy: bytes | None = None) -> bytes:
    """Encrypt bytes using Windows DPAPI (CurrentUser)."""
    if data is None:
        raise ValueError("data is None")

    in_blob = _bytes_to_blob(data)
    out_blob = _DATA_BLOB()
    ent_blob = _bytes_to_blob(entropy) if entropy else None

    ok = _crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(ent_blob) if ent_blob else None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError("CryptProtectData failed")

    try:
        return _blob_to_bytes(out_blob)
    finally:
        _kernel32.LocalFree(out_blob.pbData)


def unprotect(data: bytes, *, entropy: bytes | None = None) -> bytes:
    """Decrypt bytes using Windows DPAPI (CurrentUser)."""
    if data is None:
        raise ValueError("data is None")

    in_blob = _bytes_to_blob(data)
    out_blob = _DATA_BLOB()
    ent_blob = _bytes_to_blob(entropy) if entropy else None

    ok = _crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(ent_blob) if ent_blob else None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError("CryptUnprotectData failed")

    try:
        return _blob_to_bytes(out_blob)
    finally:
        _kernel32.LocalFree(out_blob.pbData)
