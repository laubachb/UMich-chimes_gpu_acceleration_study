#!/bin/bash
# ---------------------------------------------------------------------------
# setup.sh — clone ChIMES GPU branch and build CPU + GPU LAMMPS executables
#
# Intended for first-time setup after cloning this benchmark repository.
# Writes config.env with paths used by run_benchmark.sh and scaling/run_scaling.sh.
#
# Usage:
#   ./setup.sh                    # clone + build (Stampede3 defaults)
#   ./setup.sh --skip-clone       # build only (repo already present)
#   ./setup.sh --skip-build       # clone + write config.env only
#   CUDA_ARCH=90 ./setup.sh       # override GPU SM architecture
#
# Environment overrides:
#   CHIMES_REPO_URL   default: git@github.com:laubachb/chimes_calculator-myLLfork.git
#   CHIMES_BRANCH     default: laubachb/gpu-acceleration
#   CHIMES_DIR        default: <benchmark>/vendor/chimes_calculator
#   CARBON_SETUP      default: <benchmark>/../carbon_2.0_simulation_setup
#   CUDA_ARCH         default: 120 (Blackwell); use 90 for H100, 80 for A100
#   HOSTTYPE          default: UT-TACC (Stampede3 module loading for GPU build)
#   SLURM_ALLOC       written into config.env (default: TG-CHM250118)
# ---------------------------------------------------------------------------

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CHIMES_REPO_URL="${CHIMES_REPO_URL:-git@github.com:laubachb/chimes_calculator-myLLfork.git}"
CHIMES_BRANCH="${CHIMES_BRANCH:-laubachb/gpu-acceleration}"
CHIMES_DIR="${CHIMES_DIR:-${ROOT}/vendor/chimes_calculator}"
CARBON_SETUP="${CARBON_SETUP:-${ROOT}/../carbon_2.0_simulation_setup}"
CUDA_ARCH="${CUDA_ARCH:-120}"
HOSTTYPE="${HOSTTYPE:-UT-TACC}"
SLURM_ALLOC="${SLURM_ALLOC:-TG-CHM250118}"
SLURM_PARTITION="${SLURM_PARTITION:-rtx-small}"
TOLERANCE="${TOLERANCE:-1e-3}"

SKIP_CLONE=0
SKIP_BUILD=0

for arg in "$@"; do
    case "${arg}" in
        --skip-clone) SKIP_CLONE=1 ;;
        --skip-build) SKIP_BUILD=1 ;;
        -h|--help)
            sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown option: ${arg}  (try --help)"
            exit 1
            ;;
    esac
done

echo "=========================================================="
echo " Carbon-2.0 CPU/GPU benchmark — environment setup"
echo "=========================================================="
echo "Benchmark root : ${ROOT}"
echo "ChIMES dir     : ${CHIMES_DIR}"
echo "ChIMES branch  : ${CHIMES_BRANCH}"
echo "Carbon setup   : ${CARBON_SETUP}"
echo "CUDA_ARCH      : sm_${CUDA_ARCH}"
echo ""

# ------------------------------------------------------------------ #
# 1. Carbon-2.0 simulation inputs (read-only dependency)
# ------------------------------------------------------------------ #

PARAM_FILE="${CARBON_SETUP}/force_fields/published_params.Carbon-2.0.Small.2+3+4b.Tersoff.txt"
if [[ ! -f "${PARAM_FILE}" ]]; then
    echo "ERROR: Carbon-2.0 setup not found."
    echo "  Expected force field: ${PARAM_FILE}"
    echo ""
    echo "This benchmark reads POSCAR/INCAR from carbon_2.0_simulation_setup."
    echo "Place that directory next to this repo, or set CARBON_SETUP:"
    echo "  CARBON_SETUP=/path/to/carbon_2.0_simulation_setup ./setup.sh"
    exit 1
fi
echo "[1/4] Carbon-2.0 setup found."

# ------------------------------------------------------------------ #
# 2. Clone ChIMES calculator (GPU branch)
# ------------------------------------------------------------------ #

if [[ "${SKIP_CLONE}" -eq 0 ]]; then
    if [[ -d "${CHIMES_DIR}/.git" ]]; then
        echo "[2/4] ChIMES repo already present at ${CHIMES_DIR}"
        echo "      To re-clone, remove the directory or set CHIMES_DIR elsewhere."
    else
        echo "[2/4] Cloning ChIMES (${CHIMES_BRANCH})..."
        mkdir -p "$(dirname "${CHIMES_DIR}")"
        git clone --branch "${CHIMES_BRANCH}" --depth 1 "${CHIMES_REPO_URL}" "${CHIMES_DIR}"
    fi
else
    echo "[2/4] Skipping clone (--skip-clone)."
fi

if [[ ! -d "${CHIMES_DIR}/etc/lmp" ]]; then
    echo "ERROR: ChIMES LAMMPS install path not found: ${CHIMES_DIR}/etc/lmp"
    exit 1
fi

# ------------------------------------------------------------------ #
# 3. Build CPU and GPU LAMMPS binaries
# ------------------------------------------------------------------ #

LMP_DIR="${CHIMES_DIR}/etc/lmp"
LMP_CPU="${LMP_DIR}/exe/lmp_mpi_chimes"
LMP_GPU="${LMP_DIR}/exe/lmp_mpi_chimes_gpu"

if [[ "${SKIP_BUILD}" -eq 0 ]]; then
    echo "[3/4] Building CPU LAMMPS binary..."
    module purge 2>/dev/null || true
    if [[ -n "${HOSTTYPE}" ]]; then
        # UT-TACC.mod loads intel + impi + cmake
        # shellcheck source=/dev/null
        source "${LMP_DIR}/modfiles/${HOSTTYPE}.mod" 2>/dev/null || {
            module load intel/24.0 impi/21.11
        }
    else
        module load intel/24.0 impi/21.11
    fi
    (cd "${LMP_DIR}" && ./install.sh)

    echo "[3/4] Building GPU LAMMPS binary (sm_${CUDA_ARCH})..."
    # install_gpu.sh with hosttype handles Stampede3 impi/gcc/cuda module conflict
    (cd "${LMP_DIR}" && export hosttype="${HOSTTYPE}" && ./install_gpu.sh "${CUDA_ARCH}")
else
    echo "[3/4] Skipping build (--skip-build)."
fi

if [[ ! -x "${LMP_CPU}" ]]; then
    echo "ERROR: CPU binary missing: ${LMP_CPU}"
    exit 1
fi
if [[ ! -x "${LMP_GPU}" ]]; then
    echo "ERROR: GPU binary missing: ${LMP_GPU}"
    exit 1
fi
echo "      CPU binary: ${LMP_CPU}"
echo "      GPU binary: ${LMP_GPU}"

# ------------------------------------------------------------------ #
# 4. Write config.env
# ------------------------------------------------------------------ #

CONFIG="${ROOT}/config.env"
cat > "${CONFIG}" <<EOF
# Generated by setup.sh on $(date -Iseconds)
# Re-run ./setup.sh to refresh after rebuilding ChIMES.

ROOT=${ROOT}
CARBON_SETUP=${CARBON_SETUP}
CHIMES_REPO=${CHIMES_DIR}

LMP_CPU=${LMP_CPU}
LMP_GPU=${LMP_GPU}
PARAM_FILE=${PARAM_FILE}

TOLERANCE=${TOLERANCE}
SLURM_ALLOC=${SLURM_ALLOC}
SLURM_PARTITION=${SLURM_PARTITION}

STATEPOINTS="1500K_graph 2000K_1.0gcc 3000K_diam 6000K_3.6gcc 8000K_3.0gcc"
EOF

echo "[4/4] Wrote ${CONFIG}"
echo ""
echo "=========================================================="
echo " Setup complete."
echo ""
echo " Next steps (on a GPU node):"
echo "   ./prepare.sh && ./run_benchmark.sh          # state-point benchmark"
echo "   cd scaling && ./prepare.sh && ./run_scaling.sh   # scaling study"
echo "   sbatch submit_stampede3.slurm               # or submit batch jobs"
echo "=========================================================="
