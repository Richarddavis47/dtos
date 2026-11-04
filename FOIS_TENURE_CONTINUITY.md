# FOIS active-tenure continuity diagnosis

The v1.13.4 real-account audit found every current secondary-league GM profile
showing insufficient evidence. Read-only production inspection established:

- Four completed cached seasons, 40 standings, 40 franchise identities, 220 trades,
  and 390 draft selections existed independently of the current primary league.
- The canonical persisted input had no explicit empty FOIS-history override.
- Background generation published an evidence-backed evaluation covering four
  seasons, with nonzero confidence, while the selected current profile remained
  the earlier empty evaluation.
- The newer score's tenure ID had no matching tenure row. The older score's tenure
  remained active. No archive, account, or credential data was exported.

The unique active-tenure index rejects a new inferred start-date tenure for the
same owner. `INSERT OR IGNORE` hid that rejection; generation ignored the returned
identity and wrote a score referencing the unpersisted ID. A deterministic empty
history -> completed history regression failed before correction with different
published/current score keys.

The correction reuses the established active tenure for the same GM and makes
generation consume that canonical return value. This does not reinterpret a
takeover snapshot, fabricate an ownership transition, or change intelligence
scoring. Existing historical evidence and snapshots remain intact. A normal
background evaluation repairs the current publication by referencing the active
identity; no manual production write or destructive migration is needed.

The earlier v1.13.2 restart remains unclassified for lack of retained exact inputs.
The v1.13.4 bounded collector completed for 1,009 assets after three stable
observations; no restart was performed while this independent FOIS issue was
being classified. No DINS or mirror publication was attempted.
