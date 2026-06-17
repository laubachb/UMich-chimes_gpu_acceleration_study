#!/usr/bin/env python3
"""
Prepare replicated graphite/diamond scaling runs for CPU vs GPU benchmarking.

Reads base POSCAR/INCAR from carbon_2.0_simulation_setup (read-only).
Uses LAMMPS 'replicate' to tile the unit cell without modifying upstream files.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCALING_ROOT = SCRIPT_DIR.parent
PARENT_ROOT = SCALING_ROOT.parent
POSCAR_SCRIPT = PARENT_ROOT / "scripts" / "poscar_to_lammps.py"

BASE_SYSTEMS = {
    "graphite": {
        "source": "1500K_graph",
        "replicates": [(1, 1, 1), (2, 2, 2), (3, 3, 3)],
    },
    "diamond": {
        "source": "3000K_diam",
        "replicates": [(1, 1, 1), (2, 2, 2), (3, 3, 3), (4, 4, 4)],
    },
}

IN_LAMMPS_TEMPLATE = """\
##########################################
# Carbon-2.0 scaling study: {phase} {repl_label}
# Base: carbon_2.0_simulation_setup/conditions/{source}/
# Replicate: {nx} x {ny} x {nz}
##########################################

variable run_steps    equal 200
variable tstep        equal 0.5
variable temperature  equal {temperature:.1f}
variable io_freq      equal 20

variable repl_x       equal {nx}
variable repl_y       equal {ny}
variable repl_z       equal {nz}

variable data_file    string system.data
variable param_file   string params.txt

units           real
newton          on
atom_style      atomic
atom_modify     sort 0 0.0
atom_modify     map array

neighbor        1.5 bin
neigh_modify    delay 0 every 1 check yes

read_data       ${{data_file}}
replicate       ${{repl_x}} ${{repl_y}} ${{repl_z}}

velocity        all create ${{temperature}} 1234 dist gaussian mom yes rot yes loop all

pair_style      chimesFF
pair_coeff      * * ${{param_file}}

dump        forces all custom 1 forces.dump id type x y z fx fy fz
dump_modify forces sort id format float %20.10f
run         0
undump      forces

fix         1 all nve
thermo_style custom step time temp press density ke pe etotal econserve
thermo_modify line one format float %20.5f flush yes
thermo      ${{io_freq}}
timestep    ${{tstep}}
run         ${{run_steps}}
"""


def parse_temperature(incar_path: Path) -> float:
    text = incar_path.read_text()
    match = re.search(r"TEBEG\s*=\s*([0-9.+-]+)", text)
    if not match:
        raise ValueError(f"TEBEG not found in {incar_path}")
    return float(match.group(1))


def count_atoms(data_path: Path) -> int:
    for line in data_path.read_text().splitlines():
        if line.endswith("atoms"):
            return int(line.split()[0])
    raise ValueError(f"Could not parse atom count from {data_path}")


def repl_label(nx: int, ny: int, nz: int) -> str:
    return f"{nx}x{ny}x{nz}"


def prepare_case(
    phase: str,
    source: str,
    nx: int,
    ny: int,
    nz: int,
    carbon_setup: Path,
    out_root: Path,
    param_file: Path,
) -> Path:
    src = carbon_setup / "conditions" / source
    name = f"{phase}_{repl_label(nx, ny, nz)}"
    out_dir = out_root / name
    out_dir.mkdir(parents=True, exist_ok=True)

    temperature = parse_temperature(src / "INCAR")
    base_data = out_dir / "system.data"

    subprocess.run(
        [sys.executable, str(POSCAR_SCRIPT), str(src / "POSCAR"), str(base_data)],
        check=True,
    )

    base_atoms = count_atoms(base_data)
    total_atoms = base_atoms * nx * ny * nz

    (out_dir / "in.lammps").write_text(
        IN_LAMMPS_TEMPLATE.format(
            phase=phase,
            source=source,
            repl_label=repl_label(nx, ny, nz),
            nx=nx,
            ny=ny,
            nz=nz,
            temperature=temperature,
        )
    )
    shutil.copy2(param_file, out_dir / "params.txt")

    meta = (
        f"phase={phase}\n"
        f"name={name}\n"
        f"source={source}\n"
        f"repl_x={nx}\n"
        f"repl_y={ny}\n"
        f"repl_z={nz}\n"
        f"base_atoms={base_atoms}\n"
        f"expected_atoms={total_atoms}\n"
        f"temperature_K={temperature}\n"
    )
    (out_dir / "scaling.meta").write_text(meta)
    print(f"Prepared {name}: {base_atoms} -> {total_atoms} atoms ({nx}x{ny}x{nz})")
    return out_dir


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--carbon-setup",
        type=Path,
        default=PARENT_ROOT.parent / "carbon_2.0_simulation_setup",
    )
    ap.add_argument("--out-dir", type=Path, default=SCALING_ROOT / "statepoints")
    ap.add_argument("--param-file", type=Path, default=None)
    args = ap.parse_args()

    param_file = args.param_file or (
        args.carbon_setup
        / "force_fields"
        / "published_params.Carbon-2.0.Small.2+3+4b.Tersoff.txt"
    )
    if not param_file.is_file():
        raise FileNotFoundError(param_file)

    print(f"Carbon setup : {args.carbon_setup}")
    print(f"Output dir   : {args.out_dir}")
    print()

    n_cases = 0
    for phase, cfg in BASE_SYSTEMS.items():
        for nx, ny, nz in cfg["replicates"]:
            prepare_case(
                phase,
                cfg["source"],
                nx,
                ny,
                nz,
                args.carbon_setup,
                args.out_dir,
                param_file,
            )
            n_cases += 1

    print(f"\nDone. Prepared {n_cases} scaling case(s).")


if __name__ == "__main__":
    main()
