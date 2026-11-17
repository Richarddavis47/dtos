# Harness setup recovery

The first stand-alone harness setup stopped before creating a test container. The copied build 2261 helper expected the Product workflow diff from the previous release. For build 2262, Product is byte-identical to the deployed baseline. The helper now checks that relationship directly and still verifies the embedded runner, observer, setup files and the four unchanged harness tests. The first setup console is preserved as start-harness-contract-controller-original.log.

The application candidate is unchanged. The complete local and hosted canonical passes, the 123 preservation controls and ten fixture-isolation controls were reused. A fresh stand-alone harness run checked only the four required harness tests.
