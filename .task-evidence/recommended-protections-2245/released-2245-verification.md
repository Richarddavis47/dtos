# Verified release handoff

DTOS v1.22.30 / build 2245, PR #334, immutable release:
https://github.com/Richarddavis47/dtos/releases/tag/v1.22.30

Deployed application commit: `abbe723a0566cf84a8fff947cf7320cb66567a77`.
Validated candidate: `238dfc108b904eb499a73a06c938cc2d704cea51`.
Identical application tree: `cf649ee06ec3228d51d251ce7afbdbb15866f398`.

This branch is the existing evidence handoff, not the deployed application branch. Review application code at the deployed commit or release tag, or apply the exact candidate.patch against baseline `a17f9113868c3b9dcc3dd68d0b02613a2ad1de98`.

All 2,029 delivered payload files and their manifest/checksum list were retrieved from fixed evidence commit `0c96c0bba37e9462db4510ca11a2354e64023133` and matched. The manifest SHA256 is `620b4d6c6a7d8ee4b95b001d732db14f590e361f53e23f47d3d63aa792c0ae69`. Readback is author verification, not independent Scout acceptance. Original logs and prior failures remain unchanged.

[Final report and readable originals](https://github.com/Richarddavis47/dtos/tree/0c96c0bba37e9462db4510ca11a2354e64023133/.task-evidence/recommended-protections-2245/released-2245)

[Complete Scout prompt](https://github.com/Richarddavis47/dtos/blob/0c96c0bba37e9462db4510ca11a2354e64023133/.task-evidence/recommended-protections-2245/released-2245/SCOUT_DEPLOYED.md)

Local and hosted: 4,346 tests and ten gates each; all thirteen required hosted jobs; Product 847, separate Welcome/security 412; focused 16, preserved browser 15, separate Win Now 1, publisher integrity 79. These are execution counts. Native Actions verified all 23 immutable attachment bytes. Exact production identity, static file hashes and 15 bounded public/auth-boundary checks passed. No production recommendation search or saved-user-data mutation occurred. Authenticated owner acceptance and physical Safari remain unverified; stop on capacity deferral.
