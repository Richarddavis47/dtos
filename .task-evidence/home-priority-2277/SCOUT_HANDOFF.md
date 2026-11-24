# Scout acceptance for Home priority and phone layout

[PR #366](https://github.com/Richarddavis47/dtos/pull/366) · [Source](source.json)

Candidate `052800524d53736fe998c4f608cc2eddc7d1f051`, validated tree `ecf99970f0f3e2a59a8c850fe55fbae630cd1536`. The immutable baseline is v1.22.61 / build 2276.

1. Open Home for the verified disposable fixture containing a conditional RB fallback (backup starts first) and a later confirmed QB move. Read the payload to confirm both deadlines and the prepared evidence. The confirmed move should be the sole Home priority and lead to the original My Team lineup review. The before capture shows the reproduced error. The after capture shows the confirmed move.
2. With the confirmed improvement removed, the same earlier backup remains visible on Home. Its label must say the move depends on the named starter’s availability. Check an expired plan and confirm it cannot remain actionable. The existing asynchronous expiry fixture covers keyboard focus retention.
3. Compare a successful brief with no qualifying action, missing usable team evidence, and a failed team-brief request. The three headlines must be distinct. Confirm no background Trade search. Changing league must preserve the existing account boundary and avoid offering another league’s advice.
4. Compare the 390px missing-data fixture against the baseline. Look for a single shared explanation for unavailable record, rank and points per week, while preserving any supported figure. A supported zero remains numeric. Use the season-results disclosure for exact coverage.
5. At 320×432, scroll the long-name backup card into view. The whole primary link should be above the fixed bottom navigation, at least 44px tall, and tappable. The test checks its top, center and bottom against the rendered hit target and opens the actual destination in an emulated touch context.
6. Spot-check the existing completed-trade bar and its disclosure, and access to trade tools without automatic discovery. The five main destinations and the public demos stay available.

Before and after images and original consoles use sanitized disposable fixtures. Responsive Chromium evidence does not verify signed-in production owner acceptance or physical iPhone/Safari. To check production independently, sign in to an already prepared owner league, avoid initiating sync or discover actions, and record the actual viewport and source clocks.


## Release and verification

- [Immutable v1.22.62 / build 2277](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.62) is deployed at `72fbb0bf16d1c48f0d8883c8ac71a096c30a07da`. The validated application tree is `ecf99970f0f3e2a59a8c850fe55fbae630cd1536`.
- All 4,675 local and hosted regressions, ten canonical gates per run, 13 required hosted jobs and 182 publisher controls passed. Both full runs used an enforced 2 GiB maximum. See the [original logs](originals/).
- The [guarded prepare](https://github.com/Richarddavis47/dtos/actions/runs/45321416404) and [guarded publish](https://github.com/Richarddavis47/dtos/actions/runs/45322241861) verified 23 immutable attachments. [Production checks](release/) prove readiness and identity through public read-only requests.
- [The first publish attempt](originals/prior-attempts/guarded-publish-45321780420/) stopped after tag creation when the immediate lookup returned 404. Once GitHub showed the annotated tag pointing to the exact merge, the unchanged guarded publisher verified the existing draft and completed publication.
- [Before](before/) and [after](after/) show disposable Chromium fixtures. Signed-in production owner and physical iPhone/Safari acceptance remain open.
- Run `sha256sum -c SHA256SUMS` in this directory to independently verify these files.
