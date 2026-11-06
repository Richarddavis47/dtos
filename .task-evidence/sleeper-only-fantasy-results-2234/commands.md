# Exact-source commands

Full mandatory validator: `python -m tools.validation.validate_release` in the established non-root Python3.14.3 2GiB/no-swap/twoCPU/offline Docker harness.

Focused source/rendered controls are run through `python /workspace/2234-release/run-constrained.py -m unittest -v ...`; no admission override or source acquisition.

See invocation.json and exact original console, test events, canonical trace, resource counters, manifest and checksums for the complete final run. Prior failed controls are separately retained.
