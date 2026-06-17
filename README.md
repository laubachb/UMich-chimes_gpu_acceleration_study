# Carbon-2.0 CPU vs GPU Benchmark

Standalone benchmark suite that runs ChIMES LAMMPS simulations for each
**Carbon-2.0 production state point** on both CPU and GPU, then reports:

1. **Correctness** — per-atom force consistency at step 0 and thermodynamic
   property agreement across 200 NVE steps (tolerance 1×10⁻³)
2. **Performance** — wall-time speedup (CPU loop time / GPU loop time) per
   condition

This directory is **independent** of `carbon_2.0_simulation_setup` and the
ChIMES calculator source. It reads structures and temperatures from the carbon
setup (read-only) and builds/runs against a cloned ChIMES branch under
`vendor/chimes_calculator/`.


## First-time setup

After cloning this repository, run `setup.sh` on a machine with git, Intel MPI,
and CUDA (e.g. Stampede3 login node):

```bash
git clone git@github.com:laubachb/UMich-chimes_gpu_acceleration.git
cd UMich-chimes_gpu_acceleration

# Place carbon_2.0_simulation_setup next to this repo, or set CARBON_SETUP
./setup.sh
```

`setup.sh` will:

1. Verify `carbon_2.0_simulation_setup` is available (POSCAR/INCAR + force field)
2. Clone `laubachb/chimes_calculator-myLLfork` branch `laubachb/gpu-acceleration`
   into `vendor/chimes_calculator/`
3. Build `lmp_mpi_chimes` (CPU) and `lmp_mpi_chimes_gpu` (GPU)
4. Write `config.env` with all paths for the benchmark scripts

Options:

```bash
./setup.sh --skip-clone     # ChIMES already cloned or using CHIMES_DIR
./setup.sh --skip-build     # only clone and write config.env
CUDA_ARCH=90 ./setup.sh     # H100 instead of default 120 (Blackwell)
CARBON_SETUP=/path/to/carbon_2.0_simulation_setup ./setup.sh
CHIMES_DIR=/path/to/existing/chimes ./setup.sh --skip-clone
```

On Stampede3, GPU builds use `hosttype=UT-TACC` inside `install_gpu.sh` to work
around the impi-vs-cuda module conflict (see ChIMES `etc/lmp/install_gpu.sh`).


## State points

| State point | Atoms | T (K) | Source |
|-------------|------:|------:|--------|
| `1500K_graph` | 384 | 1500 | `carbon_2.0_simulation_setup/conditions/1500K_graph/` |
| `2000K_1.0gcc` | 64 | 2000 | `.../2000K_1.0gcc/` |
| `3000K_diam` | 216 | 3000 | `.../3000K_diam/` |
| `6000K_3.6gcc` | 200 | 6000 | `.../6000K_3.6gcc/` |
| `8000K_3.0gcc` | 64 | 8000 | `.../8000K_3.0gcc/` |

Each run uses the POSCAR geometry, `TEBEG` temperature from INCAR, Carbon-2.0
(2+3+4B Tersoff) parameters, timestep 0.5 fs, and 200 NVE steps after a
step-0 force dump.


## Prerequisites

If you have not run `./setup.sh` yet, both LAMMPS binaries must be built manually
in a ChIMES checkout (see **First-time setup** above). After setup:

```bash
ls -la vendor/chimes_calculator/etc/lmp/exe/lmp_mpi_chimes \
         vendor/chimes_calculator/etc/lmp/exe/lmp_mpi_chimes_gpu
```


## Quick start (Stampede3)

```bash
cd carbon_2.0_cpu_gpu_benchmark   # or UMich-chimes_gpu_acceleration

# First time only:
./setup.sh

# Batch (recommended)
sbatch submit_stampede3.slurm

# Or interactive on a GPU node
idev -p rtx-small -N 1 -n 1 -t 02:00:00 -A <YOUR_ALLOCATION>
module purge
module load intel/24.0 impi/21.11 gcc/13.2.0 cuda/12.8 python/3.12.11
./prepare.sh
./run_benchmark.sh
```


## Workflow

```
prepare.sh
  └─ scripts/prepare_statepoints.py
       reads carbon_2.0_simulation_setup/conditions/*/POSCAR, INCAR
       writes statepoints/<name>/{system.data, in.lammps, params.txt}

run_benchmark.sh
  for each state point:
    CPU run  → results/<name>/cpu/
    GPU run  → results/<name>/gpu/
    compare  → results/<name>/summary.json
  summarize  → results/SUMMARY.md
```


## Directory layout

```
carbon_2.0_cpu_gpu_benchmark/
  README.md
  setup.sh                 # clone ChIMES + build CPU/GPU binaries + config.env
  config.env.example       # path template (setup.sh writes config.env)
  prepare.sh               # generate LAMMPS inputs from carbon setup
  run_benchmark.sh         # run all state points CPU + GPU
  submit_stampede3.slurm
  scripts/
    poscar_to_lammps.py    # POSCAR → LAMMPS data
    prepare_statepoints.py
    compare_statepoint.py  # single-state-point analysis
    summarize_results.py   # aggregate table across conditions
  statepoints/             # generated inputs (gitignored)
  results/                 # run outputs (gitignored)
    <statepoint>/
      cpu/  gpu/
      summary.json
    SUMMARY.md
```


## Output interpretation

### Per state point (`results/<name>/summary.json`)

- `force_pass` — max per-atom |Δf| for fx/fy/fz at step 0 ≤ tolerance
- `thermo_pass` — all thermo output steps agree within tolerance
- `cpu_loop_s`, `gpu_loop_s`, `speedup` — timing for the 200-step NVE phase
- `final_property_diffs` — |CPU − GPU| for Temp, Press, Density, PotEng, TotEng
  at the final output step

### Suite summary (`results/SUMMARY.md`)

Markdown table of consistency and speedup across all conditions.


## Scripts (manual use)

Prepare one or all state points:

```bash
python3 scripts/prepare_statepoints.py \
    --carbon-setup ../carbon_2.0_simulation_setup \
    --out-dir statepoints
```

Compare a single pair of runs:

```bash
python3 scripts/compare_statepoint.py \
    --name 2000K_1.0gcc \
    --cpu-dir results/2000K_1.0gcc/cpu \
    --gpu-dir results/2000K_1.0gcc/gpu \
    --tol 1e-3 \
    --json-out results/2000K_1.0gcc/summary.json
```

Aggregate:

```bash
python3 scripts/summarize_results.py --results-dir results
```


## Notes

- **Read-only upstream**: this suite never writes into `carbon_2.0_simulation_setup`
  or the cloned ChIMES tree under `vendor/chimes_calculator/`.
- **Module conflict on Stampede3**: see
  `chimes_calculator-myLLfork/etc/lmp/install_gpu.sh` — use `hosttype=UT-TACC`
  when building the GPU binary on login nodes.
- **Runtime modules**: sequential `module load intel impi gcc cuda` works on GPU
  compute nodes (as in `submit_stampede3.slurm`).
- Speedup varies with atom count and thermodynamic condition; larger systems
  generally show higher GPU benefit.


## Scaling study (graphite & diamond)

`scaling/` replicates the graphite (`1500K_graph`, 384 atoms) and diamond
(`3000K_diam`, 216 atoms) unit cells via LAMMPS `replicate` and measures
consistency and speedup vs. system size. See `scaling/README.md`.

```bash
cd scaling
sbatch submit_stampede3.slurm
```
