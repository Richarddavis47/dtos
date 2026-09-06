"""Full-fidelity PNG capture with viewport-bounded raster and encoding buffers."""
from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import struct
import tempfile
import zlib

from PIL import Image


_SIZE_SCRIPT = """() => ({
width: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth,
document.body.offsetWidth, document.documentElement.offsetWidth,
document.body.clientWidth, document.documentElement.clientWidth),
height: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight,
document.body.offsetHeight, document.documentElement.offsetHeight,
document.body.clientHeight, document.documentElement.clientHeight)
})"""
_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(stream, kind: bytes, data: bytes) -> None:
    stream.write(struct.pack("!I", len(data)))
    stream.write(kind)
    stream.write(data)
    stream.write(struct.pack("!I", zlib.crc32(data, zlib.crc32(kind))))


def _color_chunks(encoded: bytes):
    offset = len(_SIGNATURE)
    while offset + 12 <= len(encoded):
        length = struct.unpack("!I", encoded[offset:offset + 4])[0]
        kind = encoded[offset + 4:offset + 8]
        if kind in {b"iCCP", b"sRGB", b"gAMA", b"cHRM", b"pHYs"}:
            yield kind, encoded[offset + 8:offset + 8 + length]
        offset += length + 12


def full_page_screenshot(page, path: Path, *, strip_height: int, device_scale_factor: int = 1) -> None:
    """Capture every original pixel, without scrolling or modifying the DOM.

    Chromium receives its normal full-page screenshot request with a bounded
    document clip. Each strip is decoded independently; PNG rows are compressed
    directly to a temporary file. No complete full-height image is allocated.
    Final publication is atomic, and color-profile chunks are preserved.
    """
    size = page.evaluate(_SIZE_SCRIPT)
    original_content = page.content()
    width, height = int(size["width"]), int(size["height"])
    if min(width, height, strip_height, device_scale_factor) <= 0:
        raise ValueError("Invalid full-page screenshot dimensions")
    pixel_width, pixel_height = width * device_scale_factor, height * device_scale_factor
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_SIGNATURE)
            _chunk(stream, b"IHDR", struct.pack("!IIBBBBB", pixel_width, pixel_height, 8, 6, 0, 0, 0))
            compressor = zlib.compressobj()
            for y in range(0, height, strip_height):
                band_height = min(strip_height, height - y)
                encoded = page.screenshot(full_page=True, clip={"x": 0, "y": y, "width": width, "height": band_height})
                if y == 0:
                    for kind, data in _color_chunks(encoded):
                        _chunk(stream, kind, data)
                with BytesIO(encoded) as buffer, Image.open(buffer) as image:
                    if image.size != (pixel_width, band_height * device_scale_factor):
                        raise ValueError("Full-page screenshot strip dimensions changed")
                    rgba = image.convert("RGBA")
                del encoded
                try:
                    rows = rgba.tobytes()
                finally:
                    rgba.close()
                del rgba, image, buffer
                stride = pixel_width * 4
                for start in range(0, len(rows), stride):
                    compressed = compressor.compress(b"\0" + rows[start:start + stride])
                    if compressed:
                        _chunk(stream, b"IDAT", compressed)
                del rows
            _chunk(stream, b"IDAT", compressor.flush())
            _chunk(stream, b"IEND", b"")
        if page.content() != original_content or page.evaluate(_SIZE_SCRIPT) != size:
            raise ValueError("Page changed during full-page screenshot capture")
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
