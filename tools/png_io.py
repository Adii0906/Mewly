"""Minimal dependency-free PNG reader/writer (8-bit RGB/RGBA, non-interlaced).

Used only by the offline sprite build script so it can run anywhere
without Pillow/Qt.
"""
from __future__ import annotations

import struct
import zlib
from typing import List, Tuple

Pixel = Tuple[int, int, int, int]


class Image:
    """Row-major RGBA image stored as one flat bytearray."""

    def __init__(self, width: int, height: int, data: bytearray | None = None) -> None:
        self.width = width
        self.height = height
        self.data = data if data is not None else bytearray(width * height * 4)

    def get(self, x: int, y: int) -> Pixel:
        i = (y * self.width + x) * 4
        d = self.data
        return d[i], d[i + 1], d[i + 2], d[i + 3]

    def put(self, x: int, y: int, px: Pixel) -> None:
        i = (y * self.width + x) * 4
        self.data[i:i + 4] = bytes(px)

    def alpha(self, x: int, y: int) -> int:
        return self.data[(y * self.width + x) * 4 + 3]

    def crop(self, x0: int, y0: int, x1: int, y1: int) -> "Image":
        out = Image(x1 - x0, y1 - y0)
        for y in range(y0, y1):
            s = (y * self.width + x0) * 4
            d = (y - y0) * out.width * 4
            out.data[d:d + out.width * 4] = self.data[s:s + out.width * 4]
        return out

    def paste(self, src: "Image", x0: int, y0: int) -> None:
        for y in range(src.height):
            s = y * src.width * 4
            d = ((y + y0) * self.width + x0) * 4
            self.data[d:d + src.width * 4] = src.data[s:s + src.width * 4]


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def read_png(path: str) -> Image:
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    pos, idat = 8, bytearray()
    width = height = bit_depth = color_type = interlace = 0
    palette: List[Tuple[int, int, int]] = []
    trns = b""
    while pos < len(raw):
        length, ctype = struct.unpack(">I4s", raw[pos:pos + 8])
        chunk = raw[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
        elif ctype == b"PLTE":
            palette = [tuple(chunk[i:i + 3]) for i in range(0, len(chunk), 3)]
        elif ctype == b"tRNS":
            trns = chunk
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
    if bit_depth != 8 or interlace:
        raise ValueError(f"{path}: unsupported PNG (depth={bit_depth}, interlace={interlace})")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    stride = width * channels
    buf = zlib.decompress(bytes(idat))
    rows: List[bytearray] = []
    prev = bytearray(stride)
    i = 0
    for _ in range(height):
        ftype = buf[i]
        line = bytearray(buf[i + 1:i + 1 + stride])
        i += 1 + stride
        if ftype == 1:
            for x in range(channels, stride):
                line[x] = (line[x] + line[x - channels]) & 0xFF
        elif ftype == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif ftype == 3:
            for x in range(stride):
                left = line[x - channels] if x >= channels else 0
                line[x] = (line[x] + ((left + prev[x]) >> 1)) & 0xFF
        elif ftype == 4:
            for x in range(stride):
                left = line[x - channels] if x >= channels else 0
                ul = prev[x - channels] if x >= channels else 0
                line[x] = (line[x] + _paeth(left, prev[x], ul)) & 0xFF
        rows.append(line)
        prev = line
    img = Image(width, height)
    out = img.data
    o = 0
    for line in rows:
        for x in range(width):
            if color_type == 6:
                out[o:o + 4] = line[x * 4:x * 4 + 4]
            elif color_type == 2:
                out[o:o + 3] = line[x * 3:x * 3 + 3]
                out[o + 3] = 255
            elif color_type == 0:
                v = line[x]
                out[o:o + 4] = bytes((v, v, v, 255))
            elif color_type == 4:
                v = line[x * 2]
                out[o:o + 4] = bytes((v, v, v, line[x * 2 + 1]))
            else:  # palette
                idx = line[x]
                r, g, b = palette[idx]
                a = trns[idx] if idx < len(trns) else 255
                out[o:o + 4] = bytes((r, g, b, a))
            o += 4
    return img


def write_png(path: str, img: Image) -> None:
    stride = img.width * 4
    raw = bytearray()
    for y in range(img.height):
        line = img.data[y * stride:(y + 1) * stride]
        # "Sub" filter: store each byte as the delta to the pixel on its left.
        raw.append(1)
        raw += line[:4]
        raw += bytes((line[x] - line[x - 4]) & 0xFF for x in range(4, stride))

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", img.width, img.height, 8, 6, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))
