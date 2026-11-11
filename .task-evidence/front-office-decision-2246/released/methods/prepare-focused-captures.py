"""Reuse only fresh final-source verified native capture bytes, with explicit member prefixes."""
import json
from pathlib import PurePosixPath
import zipfile

from common import BASE, digest, load_source, write_json

source = load_source()
verified = json.loads((BASE / "hosted-artifacts-verified.json").read_text())
assert verified["passed"] and verified["candidate"] == source["candidate"] and verified["tree"] == source["tree"]
mapping = [
    ("public-welcome-security.zip", "trade-partner-history/", "partner-history"),
    ("trade-resource-original.zip", "browser/team-need/", "team-need"),
    ("trade-resource-original.zip", "browser/protections/", "protections"),
    ("trade-resource-original.zip", "browser/offer-comparison/", "offer-comparison"),
    ("trade-resource-original.zip", "browser/activation/", "activation"),
    ("trade-resource-original.zip", "browser/front-office-workflow/", "front-office-workflow"),
    ("history-followthrough-original.zip", "completed-trade-observations/", "history-browser"),
]
assert all(not (BASE / destination).exists() for _, _, destination in mapping), "Existing capture attempt must be preserved"
originals = {row["file"]: row for row in verified["originals"]}
receipts = []
for filename, prefix, destination in mapping:
    path = BASE / "hosted-originals" / filename
    assert path.stat().st_size == originals[filename]["bytes"] and digest(path) == originals[filename]["sha256"]
    output = BASE / destination
    output.mkdir()
    members = []
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        names = [name for name in archive.namelist() if name.startswith(prefix) and not name.endswith("/")]
        assert names, (filename, prefix)
        for name in names:
            relative = PurePosixPath(name.removeprefix(prefix))
            assert not relative.is_absolute() and ".." not in relative.parts
            target = output / str(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
            members.append(dict(name=str(relative), sha256=digest(target), bytes=target.stat().st_size))
    receipts.append(dict(original=filename, original_sha256=originals[filename]["sha256"], prefix=prefix, destination=destination, members=members))
write_json(BASE / "capture-extraction.json", dict(candidate=source["candidate"], tree=source["tree"], source_bound_native_originals=True, captures=receipts))
print("Copied exact final-source native capture members only.")

