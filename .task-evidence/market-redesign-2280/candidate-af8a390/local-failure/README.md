# Original local validation outcome

The Docker run finished with exit 1 under the enforced 2 GiB cap. The original unittest console reports 4,681 tests with one failure and one error. Both errors occurred when the live admission path in the disposable Trade fixtures deferred requests at the desktop viewport. The captured admission samples show 387,907,584 and 392,632,320 bytes of headroom, below the required 402,653,184 bytes. The samples show zero OOM and OOM-kill events.

All 13 hosted checks passed on this source. Neither those passes nor the earlier tree's local pass qualifies this source for release.

This is a read-only original excerpt, exact invocation, Docker completion, and admission samples from disposable fixtures. Full original logs and the 917-file checksum inventory remain preserved for recovery. The subsequent correction addresses the lifespan of the separate browser and disposable fixture for each affected test viewport. Production limits and Market application bytes are identical on the subsequent source.
