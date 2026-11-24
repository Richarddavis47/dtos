# Superseded My Team validation originals

This archive contains the earlier failed hosted canonical ZIP and supporting supplemental browser capture originals. The final release evidence references this immutable commit and keeps the earlier validation outcomes separate from final checks.

Download the numbered archive parts. Verify them with `sha256sum -c PARTS.SHA256SUMS`, then join them in order.

```sh
cat prior-originals-*.zip.part > externalized-prior-originals.zip
sha256sum externalized-prior-originals.zip
```

Compare against the whole archive hash in [manifest.json](manifest.json). It also lists each original member and its checksum.
