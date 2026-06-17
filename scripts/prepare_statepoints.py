#!/usr/bin/env python3
"""
Prepare LAMMPS inputs for each Carbon-2.0 state point.

Reads POSCAR/INCAR from carbon_2.0_simulation_setup (read-only) and writes
local run directories under statepoints/.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

STATEPOINTS = [
    "1500K_graph",
    "2000K_1.0gcc",
    "3000K_diam",
    "6000K_3.6gcc",
    "8000K_3.0gcc",
]

IN_LAMMPS_TEMPLATE = """\
##########################################
# Carbon-2.0 CPU vs GPU benchmark: {name}
# Source: carbon_2.0_simulation_setup/conditions/{name}/
##########################################

variable run_steps    equal 200
variable tstep        equal 0.5
variable temperature  equal {temperature:.1f}
variable io_freq      equal 20

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


def prepare_statepoint(
    name: str,
    carbon_setup: Path,
    out_root: Path,
    param_file: Path,
) -> Path:
    src = carbon_setup / "conditions" / name
    if not src.is_dir():
        raise FileNotFoundError(f"Missing condition directory: {src}")

    out_dir = out_root / name
    out_dir.mkdir(parents=True, exist_ok=True)

    poscar = src / "POSCAR"
    incar = src / "INCAR"
    temperature = parse_temperature(incar)

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "poscar_to_lammps.py"),
            str(poscar),
            str(out_dir / "system.data"),
        ],
        check=True,
    )

    (out_dir / "in.lammps").write_text(
        IN_LAMMPS_TEMPLATE.format(name=name, temperature=temperature)
    )
    shutil.copy2(param_file, out_dir / "params.txt")

    meta = (
        f"name={name}\n"
        f"temperature_K={temperature}\n"
        f"source_poscar={poscar}\n"
        f"source_incar={incar}\n"
    )
    (out_dir / "statepoint.meta").write_text(meta)
    return out_dir


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--carbon-setup",
        type=Path,
        default=ROOT.parent / "carbon_2.0_simulation_setup",
        help="Path to carbon_2.0_simulation_setup (read-only)",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "statepoints",
        help="Output directory for prepared state points",
    )
    ap.add_argument(
        "--param-file",
        type=Path,
        default=None,
        help="ChIMES parameter file (default: force field in carbon setup)",
    )
    ap.add_argument(
        "--statepoints",
        nargs="*",
        default=STATEPOINTS,
        help="State point names to prepare",
    )
    args = ap.parse_args()

    param_file = args.param_file or (
        args.carbon_setup
        / "force_fields"
        / "published_params.Carbon-2.0.Small.2+3+4b.Tersoff.txt"
    )
    if not param_file.is_file():
        raise FileNotFoundError(f"Parameter file not found: {param_file}")

    print(f"Carbon setup : {args.carbon_setup}")
    print(f"Output dir   : {args.out_dir}")
    print(f"Parameter file: {param_file}")
    print()

    for name in args.statepoints:
        out = prepare_statepoint(name, args.carbon_setup, args.out_dir, param_file)
        print(f"Prepared {name} -> {out}")

    print(f"\nDone. Prepared {len(args.statepoints)} state point(s).")


if __name__ == "__main__":
    main()
