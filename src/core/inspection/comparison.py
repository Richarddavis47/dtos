"""Tolerant image comparison for retained DINS release artifacts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops


@dataclass(frozen=True)
class ImageComparison:
    changed_pixel_percentage: float
    status: str
    baseline: str
    current: str
    diff: str | None


def compare_images(
    baseline: Path,
    current: Path,
    diff: Path,
    *,
    tolerance: int = 8,
    warning_percentage: float = 0.5,
    failure_percentage: float = 15.0,
) -> ImageComparison:
    before = Image.open(baseline).convert("RGBA")
    after = Image.open(current).convert("RGBA")
    if before.size != after.size:
        return ImageComparison(100.0, "warn", str(baseline), str(current), None)
    delta = ImageChops.difference(before, after)
    pixels = tuple(delta.getdata())
    changed = sum(max(pixel) > tolerance for pixel in pixels)
    percentage = round(changed * 100 / max(1, len(pixels)), 4)
    status = "fail" if percentage > failure_percentage else "warn" if percentage > warning_percentage else "pass"
    if changed:
        diff.parent.mkdir(parents=True, exist_ok=True)
        delta.save(diff)
        diff_path: str | None = str(diff)
    else:
        diff_path = None
    return ImageComparison(percentage, status, str(baseline), str(current), diff_path)
