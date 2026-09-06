"""Synthetic browser-test image transport; never imported by production."""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
import os
import random
import re
from urllib.parse import urlsplit

WIDTH, HEIGHT = 350, 254  # Measured public Sleeper headshot decoded dimensions.
PATTERN = re.compile(r"^https://sleepercdn\.com/content/nfl/players/(v\d{5}|10213)\.jpg$")


def fixture_id(url: str) -> str | None:
    match = PATTERN.fullmatch(url)
    if not match:
        return None
    identity = match.group(1)
    return identity if identity == "10213" or 2 <= int(identity[1:]) <= 12322 else None


def image_bytes(identity: str, *, format_name: str = "png") -> bytes:
    """Reference-shaped350x254 headshot, not an empty/one-pixel placeholder."""
    from PIL import Image, ImageDraw

    seed = int.from_bytes(hashlib.sha256(identity.encode()).digest(), "big")
    if format_name == "jpeg":  # Diagnostic control: original full-frame noise.
        with Image.frombytes("RGB", (WIDTH, HEIGHT), random.Random(seed).randbytes(WIDTH * HEIGHT * 3)) as image:
            with BytesIO() as output:
                image.save(output, format="JPEG", quality=85)
                return output.getvalue()
    if format_name != "png":
        raise ValueError("Unknown fixture image format")
    # Real reference: PNG/P,88900decodedpixels,37323nontransparent,26835bytes.
    # This silhouette has42262nontransparentpixels and ~44KiB encoded: a
    # conservative real headshot workload, without full-frame random RGB noise.
    with Image.new("L", (WIDTH, HEIGHT)) as mask:
        draw = ImageDraw.Draw(mask)
        draw.ellipse((105, 12, 245, 160), fill=1)
        draw.ellipse((25, 145, 325, 335), fill=1)
        pixels = bytes(value % 255 + 1 if flag else 0 for flag, value in
                       zip(mask.tobytes(), random.Random(seed).randbytes(WIDTH * HEIGHT)))
    with Image.frombytes("P", (WIDTH, HEIGHT), pixels) as image:
        image.putpalette([value for index in range(256) for value in (index, index * 3 % 256, index * 7 % 256)])
        with BytesIO() as output:
            image.save(output, format="PNG", transparency=0)
            return output.getvalue()


def prepared_ids() -> tuple[str, ...]:
    return ("10213", *(f"v{i:05d}" for i in range(2, 251)),
            *(f"v{i:05d}" for i in range(1000, 1250)))


def prepared_identity(identity: str) -> str:
    """Cover every canonical synthetic asset with existing decoded-image workload.

    Preserve the previously proven image bytes for the original 500 assets.
    Other synthetic players deterministically select a representative from that
    same bank, without encoding in the capture process or using an external CDN.
    This is fixture appearance only, never a source of player facts.
    """
    if fixture_id(f"https://sleepercdn.com/content/nfl/players/{identity}.jpg") != identity:
        raise ValueError("Unknown synthetic fixture player")
    bank = prepared_ids()
    if identity in bank:
        return identity
    slot = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:4], "big") % len(bank)
    return bank[slot]


def prepare(directory: Path, *, format_name: str = "png") -> None:
    """Prepare fixture transport bytes before the measured production baseline."""
    directory.mkdir(parents=True, exist_ok=True)
    for identity in prepared_ids():
        (directory / f"{identity}.jpg").write_bytes(image_bytes(identity, format_name=format_name))


def install(page, *, fixture_origin: str, evidence: dict | None = None,
            directory: Path | None = None) -> dict:
    if os.environ.get("RENDER") or os.environ.get("DTOS_PRODUCTION_SHAPED_FIXTURE") != "1":
        raise RuntimeError("Synthetic images require an isolated production-shaped fixture")
    if urlsplit(fixture_origin).hostname not in {"dtos.fixture", "127.0.0.1", "localhost"}:
        raise RuntimeError("Synthetic images cannot target a production origin")
    if evidence is None:
        evidence = {"responses": 0, "encoded_bytes": 0, "decoded_pixels": 0}

    def respond(route):
        identity = fixture_id(route.request.url)
        if identity is None or route.request.method != "GET":
            # This callback matches only the synthetic namespace (and the exact
            # controlled fixture player). Unknown IDs must fail, not hit a CDN.
            evidence["rejected_requests"] = evidence.get("rejected_requests", 0) + 1
            route.abort("blockedbyclient")
            return
        selected = prepared_identity(identity)
        requests = evidence.setdefault("requested_ids", {})
        requests[identity] = requests.get(identity, 0) + 1
        if selected != identity:
            evidence.setdefault("representative_mapping", {})[identity] = selected
        payload = (directory / f"{selected}.jpg").read_bytes() if directory is not None else image_bytes(selected)
        route.fulfill(status=200, content_type="image/png" if payload.startswith(b"\x89PNG") else "image/jpeg", body=payload,
                      headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        evidence["responses"] += 1
        evidence["encoded_bytes"] += len(payload)
        evidence["decoded_pixels"] += WIDTH * HEIGHT

    page.route(PATTERN, respond)
    return evidence
