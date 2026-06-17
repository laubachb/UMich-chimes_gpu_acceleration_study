#!/bin/bash
set -euo pipefail

SCALING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_ROOT="$(cd "${SCALING_ROOT}/.." && pwd)"

if [[ -f "${PARENT_ROOT}/config.env" ]]; then
    # shellcheck source=/dev/null
    source "${PARENT_ROOT}/config.env"
else
    # shellcheck source=/dev/null
    source "${PARENT_ROOT}/config.env.example"
fi

python3 "${SCALING_ROOT}/scripts/prepare_scaling_runs.py" \
    --carbon-setup "${CARBON_SETUP}" \
    --out-dir "${SCALING_ROOT}/statepoints" \
    --param-file "${PARAM_FILE}"

echo "Prepared scaling cases under ${SCALING_ROOT}/statepoints/"
