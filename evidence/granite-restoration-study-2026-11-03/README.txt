Granite restoration study: independent-review handoff

Status: HANDOFF COMPLETE when remote readback is verified. Study remains PARTIAL; no production change or Granite recovery is claimed.

Start with handoff.json, then original report.json and focused-controls.log. The original archive is byte-for-byte preserved at SHA256 df5c88eda13a0671104c76a943b05032d7adfa089d11e738785b11e35a932439. It contains72manifest payloads and their original checksums. Plain files here are exact extracted copies except handoff.json, test-inventory.json and browser-measurements.json, which are newly labeled indexes/extractions. No study tests have been rerun.

79.6MiB is a fixture result. Fixture22,974,328bytes is close to supplied Granite23,048,708bytes; byte-size similarity does not establish equivalent allocation. The real cache was not obtained. The newer operator observation indicates insufficient headroom under existing policy but does not prove why the earlier503occurred. The cap remains min(actual_limit,2GiB).

36aggregate tests and12cleanupcycles are supported by original logs/records, not independently reproduced here. Original focused log is nonverbose. Static inventory lists36defined source methods but cannot provide original per-test attribution. Twelve original structured browser measurements are in log line467; keyboard/touch/no-overflow at four sizes. No screenshots/traces or physicalSafari evidence exist. Twelve cleanupcycles do not establish long-term leak freedom.

Runtime is pinned Python3.14.3image/configuration and source commit150339f/treee466. Original harness flags and cgroup assertions are preserved. This is not a self-contained image/environment bundle; missing captures are listed in handoff.json. Original README contains missing argument spaces; corrected instructions in handoff.json are new metadata, not reconstructed original logs.

Scout: verify published SHA256SUMS and originalZIPmanifest; recompute kernelpeak minus pre-restore usage; inspect fixture construction/durable projection attach, pressure/FOIS/recovery records and cleanupJSONL; compare static inventory with nonverbose36-test summary; retain all limitations. No production profiling, league entry or Trade search is requested by this handoff.
