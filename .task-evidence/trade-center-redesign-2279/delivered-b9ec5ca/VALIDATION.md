# Scout evidence navigation

- [Pull request and exact source](https://github.com/Richarddavis47/dtos/pull/368)
- [Hosted canonical original](https://github.com/Richarddavis47/dtos/actions/runs/45509710142)
- [Product Browser original](https://github.com/Richarddavis47/dtos/actions/runs/45509710178)
- [Publisher prepare original](https://github.com/Richarddavis47/dtos/actions/runs/45521934698)
- [Publisher production original](https://github.com/Richarddavis47/dtos/actions/runs/45522364624)
- [Release and immutable evidence](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.64)

Open `before/` and `after/` for the original paired fixture captures. The data and browser interaction match at 320, 390 and 1280 px. `validation/semantic-parity.json` names the exact retained results compared.

The complete original local console and the readable chunks are in `Customer-Experience.zip` under `local-canonical/unittest-console.log` and `readable-console/`. The same attachment includes focused originals and the current browser captures. `canonical-original.zip` holds the original hosted canonical run. Earlier failed, canceled and superseded records are in `Prior-attempts.zip`. Check the release `SHA256SUMS` to confirm downloads, then each archive's own manifest for individual originals.

On the final tree, local and hosted canonical each ran 4,679 tests and passed ten gates under a real 2 GiB limit. The original containers recorded zero OOM kills. All 13 required hosted jobs passed. The Product Browser log reports 1,087 tests across three batches. The local and hosted publisher guards each ran 182 checks. The packaging attempt recorded separately in `validation/` failed when an original manifest member was omitted. The verified archive includes the original generated observer bytecode and every member of that manifest. The application source, original canonical result, and publisher acceptance checks remained intact.
