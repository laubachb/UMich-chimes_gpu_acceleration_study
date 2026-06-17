#!/usr/bin/env python3
"""Convert a VASP POSCAR file to a LAMMPS atomic data file."""

from __future__ import annotations

import argparse
from pathlib import Path


def _read_poscar(path: Path):
    lines = [line.rstrip() for line in path.read_text().splitlines() if line.strip()]
    scale = float(lines[1].split()[0])
    lattice = [
        [float(x) for x in lines[i].split()[:3]]
        for i in range(2, 5)
    ]
    lattice = [[scale * v for v in vec] for vec in lattice]

    idx = 5
    symbols = lines[idx].split()
    idx += 1
    counts = [int(x) for x in lines[idx].split()]
    idx += 1
    coord_type = lines[idx].strip().lower()
    idx += 1

    natoms = sum(counts)
    frac = []
    for i in range(natoms):
        frac.append([float(x) for x in lines[idx + i].split()[:3]])

    a, b, c = lattice
    cart = []
    for f in frac:
        if coord_type.startswith("d"):
            x = f[0] * a[0] + f[1] * b[0] + f[2] * c[0]
            y = f[0] * a[1] + f[1] * b[1] + f[2] * c[1]
            z = f[0] * a[2] + f[1] * b[2] + f[2] * c[2]
        else:
            x, y, z = f[0], f[1], f[2]
        cart.append((x, y, z))

    return natoms, lattice, cart


def write_lammps_data(natoms: int, lattice, cart, out_path: Path, mass: float = 12.011):
    a, b, c = lattice
    xhi, yhi, zhi = a[0], b[1], c[2]
    xy, xz, yz = b[0], c[0], c[1]

    lines = [
        "# LAMMPS data file converted from POSCAR",
        "",
        f"{natoms} atoms",
        "",
        "1 atom types",
        "",
        f"0.0 {xhi:.10f} xlo xhi",
        f"0.0 {yhi:.10f} ylo yhi",
        f"0.0 {zhi:.10f} zlo zhi",
        f"{xy:.10f} {xz:.10f} {yz:.10f} xy xz yz",
        "",
        "Masses",
        "",
        f"1 {mass:.4f}",
        "",
        "Atoms # atomic",
        "",
    ]
    for i, (x, y, z) in enumerate(cart, start=1):
        lines.append(f"{i} 1 {x:.10f} {y:.10f} {z:.10f}")

    out_path.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("poscar", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    natoms, lattice, cart = _read_poscar(args.poscar)
    write_lammps_data(natoms, lattice, cart, args.output)
    print(f"Wrote {args.output} ({natoms} atoms)")


if __name__ == "__main__":
    main()
