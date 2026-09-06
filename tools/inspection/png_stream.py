"""Full-fidelity PNG capture with viewport-bounded raster and encoding buffers."""
from __future__ import annotations

import os
from pathlib import Path
import struct
import tempfile
import zlib

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


def _parts(encoded: bytes):
    if not encoded.startswith(_SIGNATURE):
        raise ValueError("Invalid screenshot PNG signature")
    offset = len(_SIGNATURE)
    chunks = []
    while offset + 12 <= len(encoded):
        length = struct.unpack("!I", encoded[offset:offset + 4])[0]
        kind = encoded[offset + 4:offset + 8]
        if offset + 12 + length > len(encoded):
            raise ValueError("Truncated screenshot PNG chunk")
        data = memoryview(encoded)[offset + 8:offset + 8 + length]
        crc = struct.unpack("!I", encoded[offset + 8 + length:offset + 12 + length])[0]
        if crc != zlib.crc32(data, zlib.crc32(kind)):
            raise ValueError("Invalid screenshot PNG checksum")
        chunks.append((kind, data))
        offset += length + 12
    if offset != len(encoded) or not chunks or chunks[0][0] != b"IHDR" or chunks[-1] != (b"IEND", b""):
        raise ValueError("Incomplete screenshot PNG")
    return chunks


def _first_row(row: bytes, channels: int) -> bytes:
    # PNG section 9: the previous row of an independent image is all zeroes.
    # Normalize just this row to None so it cannot reference the preceding strip.
    # Every later row retains its original filter and exact original bytes.
    kind = row[0]
    if kind not in range(5):
        raise ValueError("Invalid PNG row filter")
    data = bytearray(row[1:])
    if kind in (1, 3, 4):
        for index in range(channels, len(data)):
            left = data[index - channels]
            data[index] = (data[index] + (left // 2 if kind == 3 else left)) & 255
    return b"\0" + data


def _scanlines(chunks, width: int, height: int, channels: int):
    """Inflate at most one filtered row; never decode an image-sized buffer."""
    inflater = zlib.decompressobj()
    row_size = width * channels + 1
    row = b""
    count = 0
    for kind, data in chunks:
        if kind != b"IDAT":
            continue
        while True:
            decoded = inflater.decompress(data, row_size - len(row))
            data = inflater.unconsumed_tail
            row += decoded
            if len(row) == row_size:
                if count >= height or row[0] not in range(5):
                    raise ValueError("Invalid screenshot PNG row count/filter")
                yield _first_row(row, channels) if count == 0 else row
                count += 1
                row = b""
            if not data and not decoded:
                break
        if inflater.unused_data:
            raise ValueError("Unexpected screenshot PNG compressed data")
    if not inflater.eof or row or count != height:
        raise ValueError("Incomplete screenshot PNG scanlines")


def full_page_screenshot(page, path: Path, *, strip_height: int, device_scale_factor: int = 1) -> None:
    """Capture every original pixel, without scrolling or modifying the DOM.

    Chromium receives its normal full-page screenshot request with a bounded
    document clip. Filtered PNG rows stream directly to a temporary file with
    one boundary row normalized per strip. No decoded image is allocated.
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
            compressor = zlib.compressobj()
            image_format = None
            color = None
            for y in range(0, height, strip_height):
                band_height = min(strip_height, height - y)
                encoded = page.screenshot(full_page=True, clip={"x": 0, "y": y, "width": width, "height": band_height})
                chunks = _parts(encoded)
                header = bytes(chunks[0][1])
                w, h, depth, mode, compression, filtering, interlace = struct.unpack("!IIBBBBB", header)
                if (w, h) != (pixel_width, band_height * device_scale_factor):
                    raise ValueError("Full-page screenshot strip dimensions changed")
                if depth != 8 or mode not in (2, 6) or any((compression, filtering, interlace)):
                    raise ValueError("Unsupported screenshot PNG encoding")
                current_color = [(kind, bytes(data)) for kind, data in chunks if kind not in (b"IHDR", b"IDAT", b"IEND")]
                if y == 0:
                    image_format, color = header[8:], current_color
                    _chunk(stream, b"IHDR", struct.pack("!II", pixel_width, pixel_height) + image_format)
                    for kind, data in color:
                        _chunk(stream, kind, data)
                elif header[8:] != image_format or current_color != color:
                    raise ValueError("Screenshot PNG color/format changed between strips")
                for row in _scanlines(chunks, w, h, 3 if mode == 2 else 4):
                    compressed = compressor.compress(row)
                    if compressed:
                        _chunk(stream, b"IDAT", compressed)
                del encoded, chunks
            _chunk(stream, b"IDAT", compressor.flush())
            _chunk(stream, b"IEND", b"")
        if page.content() != original_content or page.evaluate(_SIZE_SCRIPT) != size:
            raise ValueError("Page changed during full-page screenshot capture")
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
