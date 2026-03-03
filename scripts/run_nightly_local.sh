#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
publish_dir="/home/aliemen/opalx/nightly-results/"

# Prefer the local OPALX checkout that lives next to NightlyBuildX/ (as in your layout):
# /home/aliemen/opalx/nightly-build-opalx/opalx
export OPALX_SRC_DIR="${OPALX_SRC_DIR:-"$(cd "${script_dir}/../.." && pwd)/opalx"}"

cd "${script_dir}"

# Default publish dir + regression-tests-x branch are handled by run_tests now.
# Pass extra args through if needed (e.g., --config=..., --compile, specific test names).
bash "./run_tests" --reg-tests --unit-tests --publish-dir="${publish_dir}" "$@"

