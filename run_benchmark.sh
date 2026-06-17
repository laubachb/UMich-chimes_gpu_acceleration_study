#!/bin/bash
# Run CPU and GPU ChIMES simulations for all Carbon-2.0 state points.
# Requires a GPU compute node and both LAMMPS binaries built.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${ROOT}/config.env" ]]; then
    # shellcheck source=/dev/null
    source "${ROOT}/config.env"
else
    # shellcheck source=/dev/null
    source "${ROOT}/config.env.example"
fi

run_statepoint() {
    local name="$1"
    local sp_dir="${ROOT}/statepoints/${name}"
    local cpu_dir="${ROOT}/results/${name}/cpu"
    local gpu_dir="${ROOT}/results/${name}/gpu"

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
    python3 "${ROOT}/scripts/compare_statepoint.py" \
        --name "${name}" \
        --cpu-dir "${cpu_dir}" \
        --gpu-dir "${gpu_dir}" \
        --tol "${TOLERANCE}" \
        --json-out "${ROOT}/results/${name}/summary.json"
}

if [[ ! -x "${LMP_CPU}" ]]; then
    echo "ERROR: CPU binary not found: ${LMP_CPU}"
    exit 1
fi
if [[ ! -x "${LMP_GPU}" ]]; then
    echo "ERROR: GPU binary not found: ${LMP_GPU}"
    exit 1
fi

if [[ ! -d "${ROOT}/statepoints/1500K_graph" ]]; then
    echo "State points not prepared; running prepare.sh..."
    "${ROOT}/prepare.sh"
fi

mkdir -p "${ROOT}/results"

for name in ${STATEPOINTS}; do
    run_statepoint "${name}"
done

python3 "${ROOT}/scripts/summarize_results.py" \
    --results-dir "${ROOT}/results" \
    --markdown-out "${ROOT}/results/SUMMARY.md"

echo ""
echo "Done. See ${ROOT}/results/SUMMARY.md"
