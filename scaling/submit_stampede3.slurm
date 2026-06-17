#!/bin/bash
#SBATCH -J carbon20_scaling
#SBATCH -o slurm-%j.out
#SBATCH -e slurm-%j.err
#SBATCH -p rtx-small
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH -t 06:00:00
#SBATCH -A TG-CHM250118
#SBATCH -D /work2/09982/blaubach/stampede3/carbon_2.0_cpu_gpu_benchmark/scaling

set -euo pipefail

module purge
module load intel/24.0
module load impi/21.11
module load gcc/13.2.0
module load cuda/12.8
module load python/3.12.11

ROOT=/work2/09982/blaubach/stampede3/carbon_2.0_cpu_gpu_benchmark/scaling
cd "${ROOT}"

echo "=== GPU info ==="
nvidia-smi --query-gpu=name,compute_cap --format=csv,noheader
echo ""

./prepare.sh
./run_scaling.sh
