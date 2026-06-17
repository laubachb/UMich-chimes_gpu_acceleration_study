# ChIMES GPU Acceleration Test Suite

Test cases for validating **CUDA GPU acceleration** in the ChIMES LAMMPS
`pair_style chimesFF`. Each test runs the same simulation on CPU and GPU, then
reports:

1. **Correctness** — per-atom force consistency and thermodynamic property
   agreement (tolerance 1×10⁻³)
2. **Performance** — wall-time speedup (CPU loop time / GPU loop time)

This repository is the home for GPU regression and benchmarking workflows.
**Carbon-2.0 state points are the initial testbed** — not the long-term scope of
the project. Planned additions include **carbon nanoparticle (CNP)** and **SMD**
simulation test cases.


## Test catalog

| Test | Status | Location | What it exercises |
|------|--------|----------|-----------------|
| Carbon-2.0 state points | **Available** | `./` (this directory) | GPU correctness and speedup across 5 production P–T conditions |
| Graphite/diamond scaling | **Available** | `scaling/` | Consistency and speedup vs. system size (`replicate`) |
| Carbon nanoparticle (CNP) | Planned | TBD | Larger / more complex carbon systems |
| SMD simulations | Planned | TBD | Production-style MD workloads |

All current tests read input structures from `carbon_2.0_simulation_setup`
(read-only) and run against a cloned ChIMES GPU branch under
`vendor/chimes_calculator/`. Future test suites may pull inputs from other
sources following the same CPU-vs-GPU comparison pattern.


## First-time setup

After cloning this repository, run `setup.sh` on a machine with git, Intel MPI,
and CUDA (e.g. Stampede3 login node):

```bash
git clone git@github.com:laubachb/UMich-chimes_gpu_acceleration.git
cd UMich-chimes_gpu_acceleration

# Carbon-2.0 inputs required for current tests; place alongside repo or set CARBON_SETUP
./setup.sh
```

`setup.sh` will:

1. Verify `carbon_2.0_simulation_setup` is available (needed for current tests)
2. Clone `laubachb/chimes_calculator-myLLfork` branch `laubachb/gpu-acceleration`
   into `vendor/chimes_calculator/`
3. Build `lmp_mpi_chimes` (CPU) and `lmp_mpi_chimes_gpu` (GPU)
4. Write `config.env` with paths for all test scripts

Options:

```bash
./setup.sh --skip-clone     # ChIMES already cloned or using CHIMES_DIR
./setup.sh --skip-build     # only clone and write config.env
CUDA_ARCH=90 ./setup.sh     # H100 instead of default 120 (Blackwell)
CARBON_SETUP=/path/to/carbon_2.0_simulation_setup ./setup.sh
CHIMES_DIR=/path/to/existing/chimes ./setup.sh --skip-clone
```

On Stampede3, GPU builds use `hosttype=UT-TACC` inside `install_gpu.sh` to work
around the impi-vs-cuda module conflict.


## Test 1: Carbon-2.0 state points (initial testbed)

The first GPU validation suite uses five **Carbon-2.0 production conditions**
as a chemically diverse baseline: graphite, diamond, and melt densities from
1–3.6 g/cc at 1500–8000 K.

| State point | Atoms | T (K) | Source |
|-------------|------:|------:|--------|
| `1500K_graph` | 384 | 1500 | `carbon_2.0_simulation_setup/conditions/1500K_graph/` |
| `2000K_1.0gcc` | 64 | 2000 | `.../2000K_1.0gcc/` |
| `3000K_diam` | 216 | 3000 | `.../3000K_diam/` |
| `6000K_3.6gcc` | 200 | 6000 | `.../6000K_3.6gcc/` |
| `8000K_3.0gcc` | 64 | 8000 | `.../8000K_3.0gcc/` |

Each case: POSCAR geometry, INCAR `TEBEG` temperature, Carbon-2.0 (2+3+4B
Tersoff) parameters, timestep 0.5 fs, step-0 force dump, then 200 NVE steps.


### Run (Stampede3)

```bash
# First time only:
./setup.sh

# Batch
sbatch submit_stampede3.slurm

# Or interactive on a GPU node
idev -p rtx-small -N 1 -n 1 -t 02:00:00 -A <YOUR_ALLOCATION>
module purge
module load intel/24.0 impi/21.11 gcc/13.2.0 cuda/12.8 python/3.12.11
./prepare.sh
./run_benchmark.sh
```

### Workflow

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


## Test 2: Graphite/diamond scaling study

Under `scaling/`, graphite and diamond unit cells from the Carbon-2.0 testbed
are replicated with LAMMPS `replicate` to measure how GPU speedup and
consistency scale with atom count. See `scaling/README.md`.

```bash
cd scaling
sbatch submit_stampede3.slurm
```


## Directory layout

```
UMich-chimes_gpu_acceleration/
  README.md
  setup.sh                 # clone ChIMES + build CPU/GPU binaries + config.env
  config.env.example
  prepare.sh               # Carbon-2.0 test: generate LAMMPS inputs
  run_benchmark.sh         # Carbon-2.0 test: run all state points
  submit_stampede3.slurm
  scripts/                 # shared comparison utilities
  statepoints/             # Carbon-2.0 generated inputs (gitignored)
  results/               # Carbon-2.0 run outputs (gitignored)
  scaling/               # scaling test suite
```


## Output interpretation

### Per test case (`results/<name>/summary.json`)

- `force_pass` — max per-atom |Δf| for fx/fy/fz at step 0 ≤ tolerance
- `thermo_pass` — all thermo output steps agree within tolerance
- `cpu_loop_s`, `gpu_loop_s`, `speedup` — timing for the 200-step NVE phase
- `final_property_diffs` — |CPU − GPU| for Temp, Press, Density, PotEng, TotEng
  at the final output step

### Suite summary (`results/SUMMARY.md`)

Markdown table of consistency and speedup across all Carbon-2.0 conditions.


## Scripts (manual use)

```bash
python3 scripts/prepare_statepoints.py \
    --carbon-setup ../carbon_2.0_simulation_setup \
    --out-dir statepoints

python3 scripts/compare_statepoint.py \
    --name 2000K_1.0gcc \
    --cpu-dir results/2000K_1.0gcc/cpu \
    --gpu-dir results/2000K_1.0gcc/gpu \
    --tol 1e-3 \
    --json-out results/2000K_1.0gcc/summary.json

python3 scripts/summarize_results.py --results-dir results
```


## Notes

- **Read-only upstream**: tests never write into `carbon_2.0_simulation_setup`
  or the cloned ChIMES tree under `vendor/chimes_calculator/`.
- **Module conflict on Stampede3**: use `hosttype=UT-TACC` when building the GPU
  binary on login nodes (`vendor/chimes_calculator/etc/lmp/install_gpu.sh`).
- **Runtime modules**: sequential `module load intel impi gcc cuda` on GPU nodes.
- Speedup varies with atom count and interaction complexity; larger systems
  generally benefit more from GPU acceleration.
- **Adding new tests**: follow the same pattern — `prepare` inputs, run CPU and
  GPU binaries, compare with `scripts/compare_statepoint.py`, summarize results.
  CNP and SMD suites will be added as separate directories when ready.
