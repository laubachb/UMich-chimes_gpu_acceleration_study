# Carbon-2.0 Graphite/Diamond Scaling Study

Replication benchmark: tile the graphite and diamond unit cells with LAMMPS
`replicate`, then measure CPU vs GPU **consistency** and **speedup** as a
function of system size.

This lives under `carbon_2.0_cpu_gpu_benchmark/scaling/` and does not modify
`carbon_2.0_simulation_setup` or `chimes_calculator-myLLfork`.


## Base systems

| Phase | Source condition | Base atoms | Replicates | Max atoms |
|-------|------------------|----------:|------------|----------:|
| Graphite | `1500K_graph` | 384 | 1×1×1, 2×2×2, 3×3×3 | 10,368 |
| Diamond | `3000K_diam` | 216 | 1×1×1, 2×2×2, 3×3×3, 4×4×4 | 13,824 |

Each case runs the same protocol as the state-point benchmark:
- Step-0 per-atom force dump (consistency check)
- 200 NVE steps at the INCAR `TEBEG` temperature, timestep 0.5 fs
- Compare CPU vs GPU within tolerance 1×10⁻³


## Prerequisites

Both LAMMPS binaries must already be built (see `../README.md`):

```bash
ls -la ../chimes_calculator-myLLfork/etc/lmp/exe/lmp_mpi_chimes \
         ../chimes_calculator-myLLfork/etc/lmp/exe/lmp_mpi_chimes_gpu
```


## Quick start (Stampede3)

```bash
cd /work2/09982/blaubach/stampede3/carbon_2.0_cpu_gpu_benchmark/scaling
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

Example interpretation:
- Small cells (64–384 atoms): modest speedup, overhead-dominated
- Medium cells (~2k–3k atoms): several× speedup
- Large cells (~10k+ atoms): highest speedup


## Manual use

Prepare only:

```bash
python3 scripts/prepare_scaling_runs.py \
    --carbon-setup ../../carbon_2.0_simulation_setup \
    --out-dir statepoints
```

Summarize after partial runs:

```bash
python3 scripts/summarize_scaling.py --results-dir results
```


## Notes

- Largest graphite case (3×3×3, 10,368 atoms) is the slowest CPU case; the
  SLURM script requests 6 hours wall time.
- `replicate` is applied in `in.lammps` after `read_data`, before velocity
  initialization and force evaluation.
- To add more replication factors, edit `BASE_SYSTEMS` in
  `scripts/prepare_scaling_runs.py`.
