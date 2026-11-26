# Hosted Rebuild admission diagnosis

Exact candidate 168ed86d3328444ecef286f0d28bb9fa954cab10, tree 036fb9dc0083466d0d972d94440a08a51c7d59d6. Baseline 4a58ab3e83fb49de6e81518298691c99fdb8ff7d. The ten existing tests ran in a matched order on each tree with identical Chromium and Python, a true 2 GiB cap, two CPUs and no network. The pair was repeated in reverse revision order. No app state, admission behavior, test assertions or saved settings changed. All four tests runs passed, including the original Rebuild case across all four viewports.

| Revision order | Baseline narrowest Rebuild headroom | Candidate narrowest Rebuild headroom |
| --- | ---: | ---: |
| Baseline then candidate | 1,045,661,696 B | 1,206,927,360 B |
| Candidate then baseline | 1,186,455,552 B | 1,203,625,984 B |

The candidate had lower total peak in both matched comparisons. The first candidate had 22,347,776 more bytes of Python PSS at the Rebuild test stop. Reverse order had 7,589,888 fewer bytes. No browser or Playwright driver was still present at any focused Rebuild start or stop. The full hosted and local samples preceding the same case also showed only Python processes. Hosted had about 60 MB more Python PSS before starting, and a much larger driver footprint near the deferral. The focused comparison does not recreate the full process's retained footprint. These are measurements, not an attribution of the Python or driver differences to a particular source or fixture. No candidate memory defect was established.

The exact local canonical run passed all 4,689 tests with the same admission gate and all four Rebuild widths. The first exact hosted canonical attempt returned 503 and remains a real failure. The existing publisher explicitly records distinct run attempts. We authorized one same-source canonical retry of the failed job only, preserving that attempt and reusing the twelve exact-source hosted successes and the completed local run. A passing retry does not establish a cause.

[Original hosted workflow](https://github.com/Richarddavis47/dtos/actions/runs/45751057743/attempts/1)
