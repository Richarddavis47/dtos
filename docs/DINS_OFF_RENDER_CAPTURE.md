# Off-Render DINS execution boundary

Status: focused memory and process-teardown proofs complete. This does not assert release or
production acceptance. Existing DINS serialization, reconciliation, screenshots,
accessibility, image decoding and fail-closed packaging remain authoritative.

## Resource boundary

The application and capture must be in **different memory cgroups**. A second
Python process inside Render does not accomplish this. Use only the existing
Linux validation runner; do not provision another Render service or ephemeral
paid shell. The production service retains its2GiB limit and500MiB reserve.
The capture container independently has the same limit and minimum reserve.
Measure both; never subtract another process's usage from its own cgroup.

The focused fixture uses the existing browser image, a production-shaped server
with the retained baseline padding, and prior-route warmup. Three Teams-mobile
captures run in an independent container. Each captures the full existing
viewport, DOM, screenshot and semantic contract. It requires550MiB capture
headroom, the unchanged500MiB server floor, zero OOM events, no surviving child
processes, and unchanged Market generation/construction counters. This proof is
explicitly not full61-page acceptance. Fixture-only player images stay confined
to the existing synthetic fixture; production image behavior is unchanged.

## Temporary authenticated transport

`tools.inspection.loopback_relay` is an operator tool, not a product route.

- Bind only Render127.0.0.1 and forward through authenticated, host-key-verified
  SSH to the runner's127.0.0.1. Never publish a port or disable TLS/browser checks.
- The existing inspection token is read inside Render only. Never transfer it
  to the runner, source, arguments, GitHub secrets, artifacts, or logs.
- Use a reviewed exact URL inventory, including exact query strings. No wildcard
  API access or arbitrary destinations. All account mutations remain forbidden;
  read-only account form views are part of canonical DINS coverage.
- Only GET/HEAD are accepted. Incoming auth, cookies, forwarding and host headers
  are not copied. Authentication is injected into the fixed local app connection.
- Responses are bounded to16MiB and inspected before any outward bytes. Credential
  echoes, incomplete bodies, unexpected compression and unsafe redirects fail
  closed. Security headers and successful response bodies are preserved.
- Redirects may only target another relative URL in the exact inventory. Public
  artifact URLs remain public, while interaction requests for that same DTOS
  origin resolve through the private capture transport. External attribution
  URLs keep their original destination.
- Linux wall-clock expiry interrupts stalled connections, not merely idle time.
  Only fixed status messages and numeric counts are logged.

The relay is not a sanitizer replacing the DINS packaging validator. No
authenticated capture or staging material may be published until all existing
privacy, sanitization and reconciliation checks pass.

## Teardown and evidence

On any outcome, close the SSH session/tunnel and relay; verify process and listener
absence. Revoke the temporary Render public key, verify the dashboard reports it
absent and the old key cannot authenticate, then remove usable private/public
key material, temporary SSH state and any temporary runner secret. Remove remote
helpers/inventory and authenticated capture/staging files after their authorized
use. Keep only normal sanitized publication artifacts and bounded non-sensitive
evidence. Never remove user-owned files or previously released artifacts.

Record exact source/deployment identity, capture and server memory curves, peak
effective memory/reserve, OOM/kill/restart counts, page/artifact counts, all failed
samples, relay outcome counts, token-export prohibition, and teardown results.
An aborted or failed focused run is not evidence of successful memory acceptance.
