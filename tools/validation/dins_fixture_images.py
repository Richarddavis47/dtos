"""Explicitly isolated synthetic image transport; never imported by production."""
from __future__ import annotations

import hashlib
from io import BytesIO
import os
import random
import re
from urllib.parse import urlsplit

from PIL import Image

WIDTH, HEIGHT = 350, 254  # Measured public Sleeper headshot decoded dimensions.
PATTERN = re.compile(r"^https://sleepercdn\.com/content/nfl/players/(v\d{5}|10213)\.jpg$")


def fixture_id(url: str) -> str | None:
    match = PATTERN.fullmatch(url)
    if not match:
        return None
    identity = match.group(1)
    return identity if identity == "10213" or 2 <= int(identity[1:]) <= 12322 else None


def jpeg(identity: str) -> bytes:
    """Real RGB JPEG decoding, unique deterministic pixels; no cached rasters."""
    seed = int.from_bytes(hashlib.sha256(identity.encode()).digest(), "big")
    with Image.frombytes("RGB", (WIDTH, HEIGHT), random.Random(seed).randbytes(WIDTH * HEIGHT * 3)) as image:
        with BytesIO() as output:
            image.save(output, format="JPEG", quality=85)
            return output.getvalue()


def install(page, *, fixture_origin: str, evidence: dict | None = None) -> dict:
    if os.environ.get("RENDER") or os.environ.get("DTOS_PRODUCTION_SHAPED_FIXTURE") != "1":
        raise RuntimeError("Synthetic images require an isolated production-shaped fixture")
    if urlsplit(fixture_origin).hostname not in {"dtos.fixture", "127.0.0.1", "localhost"}:
        raise RuntimeError("Synthetic images cannot target a production origin")
    if evidence is None:
        evidence = {"responses": 0, "encoded_bytes": 0, "decoded_pixels": 0}

    def respond(route):
        identity = fixture_id(route.request.url)
        if identity is None or route.request.method != "GET":
            route.fallback()
            return
        payload = jpeg(identity)
        route.fulfill(status=200, content_type="image/jpeg", body=payload,
                      headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        evidence["responses"] += 1
        evidence["encoded_bytes"] += len(payload)
        evidence["decoded_pixels"] += WIDTH * HEIGHT

    page.route(PATTERN, respond)
    return evidence
