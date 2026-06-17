#!/usr/bin/env python3
"""Summarize CPU vs GPU scaling results for graphite and diamond replication studies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_meta(case_dir: Path):
    meta = {}
    for line in (case_dir / "scaling.meta").read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            meta[k] = v
    return meta


def load_summaries(results_dir: Path):
    rows = []
    for json_path in sorted(results_dir.glob("*/summary.json")):
        summary = json.loads(json_path.read_text())
        case = json_path.parent.name
        meta = load_meta(results_dir.parent / "statepoints" / case)
        rows.append(
            {
                "case": case,
                "phase": meta.get("phase", case.split("_")[0]),
                "repl": f"{meta.get('repl_x', '?')}x{meta.get('repl_y', '?')}x{meta.get('repl_z', '?')}",
                "expected_atoms": int(meta.get("expected_atoms", summary.get("n_atoms", 0))),
                "n_atoms": summary.get("n_atoms", 0),
                "force_pass": summary.get("force_pass", False),
                "thermo_pass": summary.get("thermo_pass", False),
                "overall_pass": summary.get("overall_pass", False),
                "cpu_loop_s": summary.get("cpu_loop_s"),
                "gpu_loop_s": summary.get("gpu_loop_s"),
                "speedup": summary.get("speedup"),
                "max_force_err": max(
                    summary.get("force_stats", {}).get(f"max_abs_{c}", 0.0)
                    for c in ("fx", "fy", "fz")
                ),
            }
        )
    return rows


def print_phase_table(phase: str, rows):
    phase_rows = [r for r in rows if r["phase"] == phase]
    if not phase_rows:
        return

    phase_rows.sort(key=lambda r: r["expected_atoms"])
    print(f"\n{phase.upper()} scaling")
    header = (
        f"{'Replicate':<12} {'Natoms':>8} {'Force':>6} {'Thermo':>7} "
        f"{'CPU (s)':>10} {'GPU (s)':>10} {'Speedup':>8} {'max|Δf|':>12}"
    )
    print(header)
    print("-" * len(header))
    for r in phase_rows:
        print(
            f"{r['repl']:<12} {r['n_atoms']:>8} "
            f"{'PASS' if r['force_pass'] else 'FAIL':>6} "
            f"{'PASS' if r['thermo_pass'] else 'FAIL':>7} "
            f"{r['cpu_loop_s']:>10.2f} {r['gpu_loop_s']:>10.2f} "
            f"{r['speedup']:>8.2f}x {r['max_force_err']:>12.3e}"
        )


def write_markdown(rows, out_path: Path):
    lines = [
        "# Carbon-2.0 Graphite/Diamond Scaling Study",
        "",
        "Replication of base unit cells via LAMMPS `replicate`:",
        "- **Graphite** base: `1500K_graph` (384 atoms)",
        "- **Diamond** base: `3000K_diam` (216 atoms)",
        "",
    ]

    for phase in ("graphite", "diamond"):
        phase_rows = sorted(
            [r for r in rows if r["phase"] == phase],
            key=lambda r: r["expected_atoms"],
        )
        if not phase_rows:
            continue

        lines.extend(
            [
                f"## {phase.capitalize()}",
                "",
                "| Replicate | Natoms | Force | Thermo | CPU (s) | GPU (s) | Speedup | max |Δf| |",
                "|-----------|-------:|-------|--------|--------:|--------:|--------:|---------:|",
            ]
        )
        for r in phase_rows:
            lines.append(
                f"| {r['repl']} | {r['n_atoms']} | "
                f"{'PASS' if r['force_pass'] else 'FAIL'} | "
                f"{'PASS' if r['thermo_pass'] else 'FAIL'} | "
                f"{r['cpu_loop_s']:.2f} | {r['gpu_loop_s']:.2f} | "
                f"{r['speedup']:.2f}x | {r['max_force_err']:.3e} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Speedup trend",
            "",
            "Speedup generally increases with system size as GPU parallelism",
            "outweighs kernel launch and host/device transfer overhead.",
            "",
        ]
    )

    for phase in ("graphite", "diamond"):
        phase_rows = sorted(
            [r for r in rows if r["phase"] == phase],
            key=lambda r: r["expected_atoms"],
        )
        if len(phase_rows) < 2:
            continue
        base = phase_rows[0]
        best = max(phase_rows, key=lambda r: r["speedup"] or 0)
        lines.append(
            f"- **{phase}**: {base['speedup']:.2f}x at {base['n_atoms']} atoms "
            f"-> {best['speedup']:.2f}x at {best['n_atoms']} atoms"
        )

    out_path.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--results-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "results",
    )
    ap.add_argument("--markdown-out", type=Path, default=None)
    args = ap.parse_args()

    rows = load_summaries(args.results_dir)
    if not rows:
        print("No scaling results found.")
        return

    print("Carbon-2.0 scaling summary")
    print_phase_table("graphite", rows)
    print_phase_table("diamond", rows)

    all_pass = all(r["overall_pass"] for r in rows)
    print(f"\nOverall suite: {'PASS' if all_pass else 'FAIL'}")

    md_out = args.markdown_out or (args.results_dir / "SCALING.md")
    write_markdown(rows, md_out)
    print(f"Markdown summary: {md_out}")


if __name__ == "__main__":
    main()
