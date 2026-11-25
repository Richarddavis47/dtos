#!/usr/bin/env bash
set -euo pipefail
run_mode=$1
container=$2
checkout=$3
output=$4
scratch=$5
shift 5
root=$(cat /workspace/2279-trade-center/toolchain-root.txt)
[[ "$root" =~ ^/var/lib/docker/vfs/dir/[a-z0-9]{20,80}$ ]]
assets=()
for folder in /usr/local /usr/bin /usr/lib /usr/share /etc/chromium.d /etc/fonts; do
  assets+=(--mount "type=bind,source=$root$folder,target=$folder,readonly")
done
common=$(git -C "$checkout" rev-parse --path-format=absolute --git-common-dir)
mkdir -p "$output" "$scratch/temp"
flags=()
if test "$run_mode" = run; then flags+=(--rm); fi
exec docker "$run_mode" "${flags[@]}" --name "$container" --init   --memory=2g --memory-swap=2g --cpus=2 --network=none --user 1000:1000   "${assets[@]}" -v "$checkout:/app" -v "$common:$common:ro" -v "$output:/output"   -v "$scratch:/fixture" -v "$scratch/temp:/tmp"   -e HOME=/tmp -e DTOS_CHROMIUM_EXECUTABLE=/usr/bin/chromium -e NODE_OPTIONS=--max-old-space-size=128   -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=/app   -e DTOS_EXPECTED_HEAD="$(git -C "$checkout" rev-parse HEAD)"   -e DTOS_EXPECTED_TREE="$(git -C "$checkout" rev-parse 'HEAD^{tree}')"   -e DTOS_EXPECTED_TEST_COUNT="${DTOS_EXPECTED_TEST_COUNT:-4683}"     -e DTOS_CACHE_FILE=/fixture/cache.json -e DTOS_HISTORY_STORAGE_ROOT=/fixture   -e DTOS_DURABLE_HISTORY_REQUIRED=0 -e SLEEPER_LEAGUE_ID=1804000000000000000   -e SLEEPER_BASE_URL=http://127.0.0.1:9/v1 -w /app python:3.14.3-slim-bookworm "$@"
