#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${ROOT}/config.env" ]]; then
    # shellcheck source=/dev/null
    source "${ROOT}/config.env"
else
    # shellcheck source=/dev/null
    source "${ROOT}/config.env.example"
fi

python3 "${ROOT}/scripts/prepare_statepoints.py" \
    --carbon-setup "${CARBON_SETUP}" \
    --out-dir "${ROOT}/statepoints" \
    --param-file "${PARAM_FILE}"

echo "Prepared state points under ${ROOT}/statepoints/"
