# HELD — original local failure and ongoing diagnosis

Source `f40bf83c1abcb3b9763182f0a23e16374a12b404` / tree `21b31e05f255834fd2946f4b4e412cfd17bbb45a` / PR339. Production remains v1.22.34/build2249; no merge/tag/draft/deploy. Focused88 and native3 pass, but the full local attempt failed an existing500msFOISliveness assertion at542.770149ms. Its remainder was interrupted, with1840recorded stop events(one actualfailure), seventhgatefailed andthreegatesunexecuted. Stop events are not passing-test counts.

The original sealed failed archive is25333473bytes, SHA256`0e8e6dc86b748bab5ea046df4ac697bb8dedeff17af57f8cf44ae047716aa560`. Original console/events/memory are directly readable in numbered parts; whole/part checksums are included. Private fixture databases/cache are not published. No logs were recreated.

The source-bound matched pre-failure prefix diagnostic is RUNNING, not release evidence. Two earlier prototypes are explicitly invalid/incomplete; their limitations are retained. No GC cause, source defect or correction is yet established.500ms/memory policies and app source remain unchanged. Follow current NEXT_ACTIONS; do not launch duplicate diagnostics or substitute isolated/hosted passes for the failed full-local gate.
