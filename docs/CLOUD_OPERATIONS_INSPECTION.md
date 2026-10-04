# Private DTOS Cloud operations inspection

DTOS exposes a small GET-only evidence interface at `/api/inspect/operations`.
It replaces routine Render Web Shell diagnostics with ordinary HTTPS requests.
It cannot execute commands, accept SQL, select filesystem paths, prepare data,
refresh projections/FOIS/Market, run migrations, or restart/deploy services.
Implementation and validation are local only; this change is not deployed.

## Existing architecture and authentication

The shared credential is the existing `DTOS_INSPECTION_AUTH_TOKEN`, sent only in
`X-DTOS-Inspection-Auth`. This reuses AccountContextMiddleware's inspection-token
architecture; it introduces no second credential. The comparison is constant
time for valid token shapes. Empty/unconfigured credentials fail closed. Tokens
must be opaque printable ASCII without spaces, and at most 4096 bytes. Duplicate,
malformed, Bearer-prefixed and wrong headers receive the same 401 as missing
authorization. Query strings, account cookies and Authorization Bearer headers
cannot authorize these operations. Account login alone is insufficient.
The shared validator also hardens the existing inspection fixture token check.

Existing `/api/inspect` semantic/live routes inspect cached league/product state,
and can call league services; the prefix is exempt from normal account auth.
`X-DTOS-Inspection: deterministic` controls cached product rendering and is not
an authentication credential. Automated DINS visual infrastructure was retired
in v1.13.6. Existing readiness/platform health routes and storage accounting do
not supply a privileged read-only operational interface. Existing storage helpers
can create maintenance fences or decode broad payloads, so these endpoints use
a dedicated read connection while reusing the existing fence and graph analyzer.

The outer operational boundary authenticates all methods and descendants before
resource discovery or operation validation. It runs before account, league and
Market middleware. Operations skip account-session reads and league runtime
resolution/touches entirely. No inspection league or roster configuration is
required for operational access. The router repeats authorization as a dependency.
Responses, including errors, use `Cache-Control: no-store, private`, vary on the
inspection header, and are omitted from public OpenAPI. CORS does not allow the
credential header. Render provides HTTPS termination; clients must verify TLS
and must not follow redirects with credentials.

## Fixed operations

All paths below follow `/api/inspect/operations/`. The base path lists the six
operations after authorization. No request body or action parameter is interpreted.
Unknown operations return 404 after authorization; non-GET methods return 405.
Unauthorized callers always receive 401 within this namespace.

| Operation | Evidence |
| --- | --- |
| `storage` | Disk capacity/used/free, available inode counters, file sizes for configured Projection, FOIS, event, history, metadata and global evidence stores. Missing stores have null size, not a healthy zero. No paths or account store information. |
| `projection-reachability` | Existing `tools/projection_reachability.py` logical classifications, publication-head/historical-root counts, unresolved references, graph validity, page/freelist bytes, digest and deletion prohibition. No physical-player detail export. |
| `projection-inventory?limit=50&offset=0` | Explicit paginated snapshot identity, league, season, week, scoring identity, classification, publication/rollback/historical/horizon relationships, source/provenance availability and compact source/envelope fingerprints. No player payloads. |
| `fois-storage` | Physical/file/freelist bytes, allowlisted table counts, read status, SQLite quick-check result and admitted retention policy. Semantic payload integrity is explicitly not evaluated. No GM, owner, account or assessment payloads. |
| `retention` | Admitted Projection/FOIS policy, eight-observation operational windows, cache budget/footprint, latest stored monitoring counters, bounded baseline growth and process-local storage counters. Never initiates collection or cleanup. |
| `identity` | Centralized application version/build, deployment commit if a valid commit identifier is configured, boolean readiness and inspection schema. Missing commit metadata is null. |

Inventory source/provenance availability refers to a matching retained source at
the snapshot's publication boundary, excluding superseded/explicitly expired
observations. Provenance-only rows have `source_available=false` and
`provenance_available=true`. These flags do not certify semantic source integrity.
Inventory envelope checksums cover retained graph metadata; they do not expose
or hash-export broad player records. Pagination uses snapshot identity ordering
within each read transaction. Publications between requests can change pages;
compare the report digest and restart pagination if it changes.

Valid healthy reachability reports match the CLI, including `report_sha256`.
Malformed-record errors are sanitized to approved reason codes and valid compact
hash identities/numeric observation IDs. Raw parse errors, unknown table names
and arbitrary payload strings are omitted; the digest is recomputed over that
sanitized report, excluding the digest field itself. Classification logic remains
the CLI logic, including conservative UNKNOWN/review behavior for unknown tables.
The provided production figures are compatibility evidence, never live constants.

## Read-only storage and resource limits

Each database operation uses `mode=ro`, `PRAGMA query_only=ON`, a bounded explicit
read transaction, `trusted_schema=OFF`, memory-only temporary storage and a 2 MiB
SQLite cache. A SQLite authorizer admits only SELECT/read operations on approved
tables, fixed aggregate functions, required read-only PRAGMAs and read transaction
boundaries. It denies writes, schema changes, ATTACH, extension loading and changes
to safety PRAGMAs. No normal service/repository constructor is used for inspection.

The existing `.storage-lock` fence must already exist. Inspection opens it `rb`
and takes a nonblocking shared lock; it never creates/updates a fence, directory
or database. Symlinked configured paths are rejected. SQLite files must use
rollback-journal mode, with no WAL/SHM/journal files present. WAL databases are
rejected before connection because even SQLite read-only opens can create shared
memory files. Hot journals are not recovered. Inspection never sets journal mode,
uses `immutable=1`, or changes storage to make a read succeed. Incompatible/busy
stores fail closed with 503 and sanitized details; no inspection write fallback.
Existing ordinary writers can run concurrently under SQLite's normal read locks;
maintenance cannot replace a database during its inspection transaction.

Limits are fixed in code, not caller-controlled:

- One diagnostic per application worker; concurrent requests receive 429.
- Graph operations have a five-second minimum interval between starts per worker.
- Ten-second graph deadline; three-second summary deadline; SQLite lock timeout
  100 ms and progress-handler cancellation every 1000 VM instructions. Python
  scans also check the deadline. These are cooperative execution limits, not
  hard real-time interruption of an OS read or an individual bounded JSON decode.
- Inventory defaults to 50 rows, accepts 1–100, and offsets 0–4096. Unknown,
  duplicate, oversized and operation-inappropriate query parameters return 400.
- At most 4096 snapshots, 18 horizon entries per snapshot, 250,000 pending player
  references, 128 unresolved-reference records, 100,000 rows per non-player query
  and five million total query rows per operation.
- At most 32 MiB per SQLite value/decompressed Projection payload and 512 MiB of
  cumulative decoding. The player-state scan measures lengths without decoding
  player payloads. Graph metadata is retained without legacy inline players.
- Responses at most 256 KiB; inventory strings at most 128 characters.
- Cache traversal examines at most 4096 entries in configured cache families;
  file contents are not read. Monitor input uses the existing 1 MiB budget and
  at most 24 monthly periods and three annual baselines. No league-growth payload
  or raw monitor errors are returned.

Exceeding a graph limit returns 503, never a partial graph marked valid. These
budgets may require a separately reviewed bounded offline operation for larger
future stores. There is no HTTP parameter that relaxes them. Scale concurrency
and cooldown multiply with application worker count; deploy with the established
worker count and evaluate larger inventories on sanitized retained fixtures.

## Exact Codex Cloud HTTPS request pattern

Provision the existing token through an approved Cloud secret binding; do not
paste it into a prompt, query string, shell argument, source file or logs.
Set the non-secret `DTOS_INSPECTION_BASE_URL` to the actual DTOS HTTPS origin.
This Python pattern reads the secret from the environment and sends it only in
the existing header. It uses normal HTTPS, verifies certificates, and disables
redirect following. It does not require SSH, raw TCP tools or browser automation.

```python
import os
from urllib.parse import urlsplit
import httpx

origin = os.environ['DTOS_INSPECTION_BASE_URL'].rstrip('/')
parsed = urlsplit(origin)
assert parsed.scheme == 'https' and parsed.hostname
assert not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
assert parsed.path in ('', '/')
with httpx.Client(timeout=15, follow_redirects=False) as client:
    response = client.get(
        origin + '/api/inspect/operations/projection-reachability',
        headers={'X-DTOS-Inspection-Auth': os.environ['DTOS_INSPECTION_AUTH_TOKEN']},
    )
    response.raise_for_status()
    report = response.json()
# Keep report in private task evidence; never log the request headers or token.
```

Replace only the final fixed operation to request another report. For inventory,
use `params={'limit': 50, 'offset': 0}` and wait at least five seconds between graph
requests; honor 429/Retry-After. Never disable TLS verification or enable verbose
header logging. Configure the Cloud environment's HTTPS host allowlist and secret
binding for the DTOS origin during release setup. No credential value is documented.

## Validation and release boundary

Focused tests use disposable local SQLite stores and in-process HTTP requests.
They check rejection/disclosure, middleware isolation, graph/CLI parity,
inventory bounds, sensitive fields, deadlines/decoding/concurrency limits,
query-only enforcement, denied SQL operations, imports without service creation,
WAL/journal refusal, and literal-byte/SHA-256/file-mtime/directory equality across all operations.
Production databases are never accessed for these tests.

Before release, review the implementation and resolve every release-validation
failure. Assign/update the centralized version/build and release documents in the
release PR. Rebase the local feature branch onto current main, run the canonical
`python -m tools.validation.validate_release` with its complete gates, and rerun
focused security tests. Obtain separate release authorization before merge/deploy.
Configure/reuse the token through secret-management tooling and grant the Cloud
HTTPS hostname/secret binding. Verify existing store fences and rollback-journal
compatibility using approved release evidence; never change journal mode as part
of an inspection request. Deploy the reviewed release through the normal pipeline,
then verify unauthorized 401, HTTPS identity and bounded read-only reports.
Do not create a public evidence page or publish production reports.


The recovered implementation is reconciled onto main `86bb3f2`, including the
merged cross-platform validation tooling and authoritative Ruff gate. Detailed
local validation results and disposable-store evidence are kept in ignored
private task artifacts, rather than public release notes or PR descriptions.
