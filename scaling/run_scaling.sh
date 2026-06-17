#!/bin/bash
# Run CPU vs GPU scaling study for replicated graphite and diamond systems.

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

COMPARE_PY="${PARENT_ROOT}/scripts/compare_statepoint.py"

run_case() {
    local name="$1"
    local sp_dir="${SCALING_ROOT}/statepoints/${name}"
    local cpu_dir="${SCALING_ROOT}/results/${name}/cpu"
    local gpu_dir="${SCALING_ROOT}/results/${name}/gpu"

    if [[ ! -d "${sp_dir}" ]]; then
        echo "ERROR: missing ${sp_dir}; run ./prepare.sh first"
        exit 1
    fi

    mkdir -p "${cpu_dir}" "${gpu_dir}"
    for d in "${cpu_dir}" "${gpu_dir}"; do
        cp "${sp_dir}/in.lammps" "${sp_dir}/system.data" "${sp_dir}/params.txt" "${d}/"
    done

    echo ""
    echo "=== ${name}: CPU ==="
    (cd "${cpu_dir}" && srun -n 1 "${LMP_CPU}" -i in.lammps -log log.lammps > out.lammps 2>&1)

    echo "=== ${name}: GPU ==="
    (cd "${gpu_dir}" && srun -n 1 "${LMP_GPU}" -i in.lammps -log log.lammps > out.lammps 2>&1)

    echo "=== ${name}: compare ==="
    python3 "${COMPARE_PY}" \
        --name "${name}" \
        --cpu-dir "${cpu_dir}" \
        --gpu-dir "${gpu_dir}" \
        --tol "${TOLERANCE}" \
        --json-out "${SCALING_ROOT}/results/${name}/summary.json"
}

if [[ ! -x "${LMP_CPU}" || ! -x "${LMP_GPU}" ]]; then
    echo "ERROR: build both LAMMPS binaries first (see ../README.md)"
    exit 1
fi

if [[ ! -d "${SCALING_ROOT}/statepoints/graphite_1x1x1" ]]; then
    echo "Scaling cases not prepared; running prepare.sh..."
    "${SCALING_ROOT}/prepare.sh"
fi

mkdir -p "${SCALING_ROOT}/results"

mapfile -t CASES < <(find "${SCALING_ROOT}/statepoints" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)

for name in "${CASES[@]}"; do
    run_case "${name}"
done

python3 "${SCALING_ROOT}/scripts/summarize_scaling.py" \
    --results-dir "${SCALING_ROOT}/results" \
    --markdown-out "${SCALING_ROOT}/results/SCALING.md"

echo ""
echo "Done. See ${SCALING_ROOT}/results/SCALING.md"
