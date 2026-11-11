# Preserved failed Recovery packaging evidence — staged, not published

These are **packaging failures, not application-test failures**. Candidate `4cf524c488efb36c77defd78bfd7acf84a3f6ddd`, tree `79fe9268fb3394604559bbcbe1119616a080b71b`, passed the complete local and hosted application suites on unchanged source:4,364tests/all10gates each,13requiredhostedjobs. This staging package claims no release, merge, deployment, live Granite recovery or Scout acceptance.

The original three failed operations were: a missing harness provenance index, an archive exceeding the unchanged100MiB cap, and a missing `focused-ready.json` inclusion. The original source evidence existed; late-authored indexes and packager corrections do not recreate tests or convert these packaging attempts into passing release inputs.

`original-logs/` contains the three exact original failures. `preserved-metadata/` contains original old-plan/archive receipts. `derived-indexes/` contains clearly labeled later reconciliation and audit records. `methods/` contains byte-original before/after packaging-method sources, derived readable diffs, and the bounded staging method; none is application code or an executed application test. No private production Granite payload was acquired. No provider, sync, FOIS, Trade search, account mutation, credentials, fullDockerConfig/environment dump or new access mechanism is included.

The oversized114,866,370-byte original remains unchanged at its retained source and is represented here by two contiguous ordered parts, each at most60MiB. These parts are not independent ZIP files. `archive-parts.json` gives whole/part hashes, offsets and sizes. Reassemble in a new local directory:

```sh
cat originals/recovery-size-114866370-original.zip.part-001 originals/recovery-size-114866370-original.zip.part-002 > recovery-size-114866370-original.zip
sha256sum recovery-size-114866370-original.zip
```

Expected wholeSHA256: `5548273f038280b792c9b392d480ba979ed8639e683f84b033ddfd88ba4c62a3`.

The second original ZIP is an exact103,289,480-byte copy, SHA256 `0e965c50af57d41e606cdf9c162ce249ec3f508fac875a75e538fa79b7be6b7f`. Do not use either failed archive as a release package. Their original bytes and all failure outcomes are preserved.

Verify the staged files with `sha256sum -c SHA256SUMS`; `publication-manifest.json` lists every payload's provenance, byte count and hash. The checksum file covers all payloads and that manifest; it excludes only itself. Root must independently review this staging selection, publish through the established existing evidence branch to `.task-evidence/front-office-decision-2246/packaging-failures`, and verify the published bytes. No network/commit/push/publication occurred while staging. No checksums or future links prove publication until that actual readback succeeds.
