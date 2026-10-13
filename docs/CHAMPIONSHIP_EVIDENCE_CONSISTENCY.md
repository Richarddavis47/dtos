# Championship evidence consistency — v1.21.42 / build 2142

Baseline: v1.21.41 / build 2141, `c818819a637b26d1891b02e4b76ccc6dc6759777`.

The shared Home, League and My Team trophy helper consumes `season_archive_section(..., "playoffs")`. It no longer derives a champion from raw cached bracket rows. That bounded canonical section carries the admitted result, historical roster identities and canonical source-season metadata. The historical section reuses the existing playoff-result admission contract with its historical roster whitelist, including on retained reads. Missing historical membership cannot be supplied by today's roster IDs.

A defending champion requires the immediately preceding completed source season, matching source-season identity, source league matching the selected league's predecessor (or the same source league when explicitly season-scoped), two distinct supported historical finalists and coherent admitted winner/loser. Current roster membership only determines where an already admitted trophy is displayed. Current managers are not treated as historical decision-makers. Unsupported trophies are omitted; canonical history retains its conflict reasons and independent season facts.

The existing 96-entry generation-aware season-section cache is reused. Canonical dataset identity changes invalidate the section. Home evaluates the admitted champion before its presentation cache lookup and includes the trophy decision in that key, so historical corrections remove a previously warmed trophy. Unchanged reads reuse the bounded section and append no historical evidence. Original raw brackets, compact recovery evidence and retained FOIS assessments are not repaired or regenerated. A compact retained context without sufficient source-season identity cannot alone establish a trophy.

## Scout independent acceptance

1. Publish 2026 historical rosters 1–10 and final `p=1,t1=1,t2=999,w=1,l=999`, then select linked 2027. Canonical season API and season/franchise history must withhold champion/runner-up; Home, League and My Team must show no trophy. Independent regular-season facts remain HTTP 200. Raw evidence stays unchanged.
2. Replace with distinct valid finalists 1/2 and coherent outcomes. Expect canonical champion 1 and 2026 trophy. Repeat with duplicate finalists, winner/loser outside participants, identical outcomes, nested malformed IDs, pending or missing brackets. Do not infer a winner from standings.
3. Test real parent-match advancement, first-round byes and multi-week round configuration. Supported completed results retain their championship; missing dependencies are qualified independently.
4. Test a foreign historical league sharing roster 1, absent/mismatched predecessor linkage and league A→B→A. A matching current roster does not establish historical source identity. Historical manager changes do not transfer a championship to an unrelated league.
5. Warm Home under valid evidence, publish the roster-999 correction without changing current teams, then request Home again. The trophy disappears consistently with League, My Team and history. Unchanged repeated reads produce no durable growth.
6. Independently compare current Sleeper source for Day Traders' completed 2025 predecessor `1180090396074209280`: champion roster 1, runner-up 8. Verify supported trophy/year explanation remains on Day Home/League/My Team. Arkham has no admitted immediate-predecessor championship and must not gain a trophy.
7. Test actual rendered pages at 320/375/390px, short and tall portrait, and desktop. Keyboard-open the trophy explanation; preserve focus and no document overflow. Recheck production script HTTP 200, numeric historical production weeks, Boston/Love/exact picks, 100 FAAB once and FOIS RETAINED / NOT REVALIDATED.

Controlled publisher/router and responsive Chromium checks are not authenticated live product acceptance or physical iPhone/Safari testing. No new permanent store, duplicate bracket archive, provider backfill, migration, polling, scoring/projection model, FOIS regeneration or Sleeper write is authorized by this correction.
