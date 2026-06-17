#!/usr/bin/env python3
"""
compare_statepoint.py -- CPU vs GPU comparison for one Carbon-2.0 state point.

Writes a JSON summary and prints a human-readable report.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def parse_log(path: Path):
    thermo_rows = []
    loop_times = []
    headers = []
    in_block = False

    for line in path.read_text().splitlines():
        m_hdr = re.match(r"^\s*(Step\s+.+)", line)
        if m_hdr:
            headers = m_hdr.group(1).split()
            in_block = True
            continue

        if not in_block:
            continue

        m_loop = re.match(r"\s*Loop time of\s+([\d.eE+\-]+)", line)
        if m_loop:
            loop_times.append(float(m_loop.group(1)))
            in_block = False
            headers = []
            continue

        parts = line.split()
        if parts and headers and len(parts) == len(headers):
            try:
                thermo_rows.append({h: float(v) for h, v in zip(headers, parts)})
            except ValueError:
                pass

    return thermo_rows, loop_times


def parse_forces_dump(path: Path):
    forces = {}
    col_names = []
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("ITEM: ATOMS"):
            col_names = lines[i].strip().split()[2:]
            i += 1
            break
        i += 1

    id_idx = col_names.index("id")
    fx_idx = col_names.index("fx")
    fy_idx = col_names.index("fy")
    fz_idx = col_names.index("fz")

    while i < len(lines):
        parts = lines[i].strip().split()
        if not parts or parts[0].startswith("ITEM"):
            break
        atom_id = int(parts[id_idx])
        forces[atom_id] = {
            "fx": float(parts[fx_idx]),
            "fy": float(parts[fy_idx]),
            "fz": float(parts[fz_idx]),
        }
        i += 1
    return forces


def compare_forces(cpu_forces, gpu_forces, tol):
    common_ids = sorted(set(cpu_forces) & set(gpu_forces))
    diffs = {"fx": [], "fy": [], "fz": []}
    for aid in common_ids:
        for comp in ("fx", "fy", "fz"):
            diffs[comp].append(abs(cpu_forces[aid][comp] - gpu_forces[aid][comp]))

    stats = {
        "n_atoms": len(common_ids),
        "max_abs_fx": max(diffs["fx"]) if diffs["fx"] else 0.0,
        "max_abs_fy": max(diffs["fy"]) if diffs["fy"] else 0.0,
        "max_abs_fz": max(diffs["fz"]) if diffs["fz"] else 0.0,
        "mean_abs_fx": sum(diffs["fx"]) / len(diffs["fx"]) if diffs["fx"] else 0.0,
        "mean_abs_fy": sum(diffs["fy"]) / len(diffs["fy"]) if diffs["fy"] else 0.0,
        "mean_abs_fz": sum(diffs["fz"]) / len(diffs["fz"]) if diffs["fz"] else 0.0,
    }
    passed = all(stats[f"max_abs_{c}"] <= tol for c in ("fx", "fy", "fz"))
    return passed, stats


def compare_thermo(cpu_rows, gpu_rows, tol):
    failures = []
    if len(cpu_rows) != len(gpu_rows):
        return False, [f"row_count cpu={len(cpu_rows)} gpu={len(gpu_rows)}"]

    for step_i, (cr, gr) in enumerate(zip(cpu_rows, gpu_rows)):
        for col in cr:
            if col not in gr:
                continue
            err = abs(cr[col] - gr[col])
            if err > tol:
                failures.append(
                    {
                        "step": step_i,
                        "column": col,
                        "cpu": cr[col],
                        "gpu": gr[col],
                        "abs_err": err,
                    }
                )
    return len(failures) == 0, failures


def timed_run(loop_times):
    if len(loop_times) >= 2:
        return loop_times[1]
    if len(loop_times) == 1:
        return loop_times[0]
    return None


def compare_statepoint(name, cpu_dir, gpu_dir, tol, out_json=None):
    cpu_log = cpu_dir / "log.lammps"
    gpu_log = gpu_dir / "log.lammps"
    cpu_dump = cpu_dir / "forces.dump"
    gpu_dump = gpu_dir / "forces.dump"

    cpu_thermo, cpu_times = parse_log(cpu_log)
    gpu_thermo, gpu_times = parse_log(gpu_log)
    cpu_forces = parse_forces_dump(cpu_dump)
    gpu_forces = parse_forces_dump(gpu_dump)

    force_pass, force_stats = compare_forces(cpu_forces, gpu_forces, tol)
    thermo_pass, thermo_failures = compare_thermo(cpu_thermo, gpu_thermo, tol)

    cpu_t = timed_run(cpu_times)
    gpu_t = timed_run(gpu_times)
    speedup = (cpu_t / gpu_t) if cpu_t and gpu_t and gpu_t > 0 else None

    final_cpu = cpu_thermo[-1] if cpu_thermo else {}
    final_gpu = gpu_thermo[-1] if gpu_thermo else {}
    property_cols = ["Temp", "Press", "Density", "PotEng", "TotEng"]
    property_diffs = {}
    for col in property_cols:
        if col in final_cpu and col in final_gpu:
            property_diffs[col] = abs(final_cpu[col] - final_gpu[col])

    summary = {
        "statepoint": name,
        "tolerance": tol,
        "n_atoms": force_stats.get("n_atoms", 0),
        "force_pass": force_pass,
        "force_stats": force_stats,
        "thermo_pass": thermo_pass,
        "thermo_failures": len(thermo_failures),
        "cpu_loop_s": cpu_t,
        "gpu_loop_s": gpu_t,
        "speedup": speedup,
        "final_property_diffs": property_diffs,
        "overall_pass": force_pass and thermo_pass,
    }

    if out_json:
        out_json.write_text(json.dumps(summary, indent=2) + "\n")

    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", required=True)
    ap.add_argument("--cpu-dir", type=Path, required=True)
    ap.add_argument("--gpu-dir", type=Path, required=True)
    ap.add_argument("--tol", type=float, default=1e-3)
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args()

    summary = compare_statepoint(
        args.name, args.cpu_dir, args.gpu_dir, args.tol, args.json_out
    )

    print(f"State point: {summary['statepoint']}")
    print(f"  Atoms     : {summary['n_atoms']}")
    print(f"  Forces    : {'PASS' if summary['force_pass'] else 'FAIL'}")
    fs = summary["force_stats"]
    print(
        f"    max|Δf| fx={fs['max_abs_fx']:.3e} "
        f"fy={fs['max_abs_fy']:.3e} fz={fs['max_abs_fz']:.3e}"
    )
    print(f"  Thermo    : {'PASS' if summary['thermo_pass'] else 'FAIL'}")
    if summary["cpu_loop_s"] is not None and summary["gpu_loop_s"] is not None:
        print(
            f"  Timing    : CPU={summary['cpu_loop_s']:.2f}s  "
            f"GPU={summary['gpu_loop_s']:.2f}s  "
            f"speedup={summary['speedup']:.2f}x"
        )
    print(f"  Overall   : {'PASS' if summary['overall_pass'] else 'FAIL'}")
    sys.exit(0 if summary["overall_pass"] else 1)


if __name__ == "__main__":
    main()
