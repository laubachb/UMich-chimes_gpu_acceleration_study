# Scaling Test — Graphite & Diamond

Part of the **ChIMES GPU Acceleration Test Suite**. This test uses Carbon-2.0
graphite and diamond unit cells as starting structures, then tiles them with
LAMMPS `replicate` to measure how CPU vs GPU **consistency** and **speedup**
scale with system size.

See the [repository README](../README.md) for overall scope, setup, and planned
future tests (CNP, SMD).


## Base systems (from Carbon-2.0 testbed)

| Phase | Source condition | Base atoms | Replicates | Max atoms |
|-------|------------------|----------:|------------|----------:|
| Graphite | `1500K_graph` | 384 | 1×1×1, 2×2×2, 3×3×3 | 10,368 |
| Diamond | `3000K_diam` | 216 | 1×1×1, 2×2×2, 3×3×3, 4×4×4 | 13,824 |

Each case uses the same GPU validation protocol as other suite tests:
- Step-0 per-atom force dump (consistency check)
- 200 NVE steps at INCAR `TEBEG` temperature, timestep 0.5 fs
- Compare CPU vs GPU within tolerance 1×10⁻³


## Prerequisites

Run `../setup.sh` from the repository root first (or ensure `config.env` exists).

```bash
ls -la ../vendor/chimes_calculator/etc/lmp/exe/lmp_mpi_chimes \
         ../vendor/chimes_calculator/etc/lmp/exe/lmp_mpi_chimes_gpu
```


## Quick start (Stampede3)

```bash
cd scaling
sbatch submit_stampede3.slurm
```

Or interactively on a GPU node:

```bash
idev -p rtx-small -N 1 -n 1 -t 06:00:00 -A <YOUR_ALLOCATION>
module purge
module load intel/24.0 impi/21.11 gcc/13.2.0 cuda/12.8 python/3.12.11
./prepare.sh
./run_scaling.sh
```


## Workflow

```
prepare.sh
  └─ scripts/prepare_scaling_runs.py
       reads 1500K_graph and 3000K_diam POSCAR/INCAR (read-only)
       writes statepoints/<phase>_<nx>x<ny>x<nz>/

run_scaling.sh
  for each case (smallest to largest):
    CPU run -> results/<case>/cpu/
    GPU run -> results/<case>/gpu/
    compare -> results/<case>/summary.json
  summarize -> results/SCALING.md
```


## Expected output (`results/SCALING.md`)

Tables per phase showing Natoms, force/thermo PASS/FAIL, CPU time, GPU time,
speedup, and max |Δf|. Speedup should generally **increase** with replication
factor as GPU work grows relative to fixed overhead.


## Manual use

```bash
python3 scripts/prepare_scaling_runs.py \
    --carbon-setup ../../carbon_2.0_simulation_setup \
    --out-dir statepoints

python3 scripts/summarize_scaling.py --results-dir results
```


## Notes

- Largest graphite case (3×3×3, 10,368 atoms) is the slowest CPU case; SLURM
  requests 6 hours wall time.
- To add replication factors, edit `BASE_SYSTEMS` in `scripts/prepare_scaling_runs.py`.
