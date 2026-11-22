#!/usr/bin/env bash
set -euo pipefail
cd /workspace/2274-bye-pickup-ir
for scope in previous isolated; do
  root=/workspace/dtos-draft-capital-2247
  if [[ $scope == isolated ]]; then root=/workspace/dtos-ir-2274-isolation-control; fi
  dest=prior-attempts/trade-viewport-isolation-control/$scope
  mkdir -p "$dest"
  set +e
  docker run --rm --init --name "dtos-trade-pressure-$scope-2274" --memory=2g --memory-swap=2g --cpus=2 --network=none --user "$(id -u):$(id -g)" \
    -v "$root:/app:ro" -v "$PWD/trade-pressure-control.py:/evidence/trade-pressure-control.py:ro" -e HOME=/tmp \
    -e NODE_OPTIONS=--max-old-space-size=128 -w /app "$(cat validation-image.txt)" python /evidence/trade-pressure-control.py > "$dest/console-original.log" 2>&1
  rc=$?
  set -e
  printf '%s\n' "$rc" > "$dest/exit-code"
  printf '%s ' "$scope"
  tail -1 "$dest/console-original.log"
done
