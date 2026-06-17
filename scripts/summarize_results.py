#!/usr/bin/env python3
"""Aggregate CPU vs GPU benchmark summaries across Carbon-2.0 state points."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_summaries(results_dir: Path):
    summaries = []
    for json_path in sorted(results_dir.glob("*/summary.json")):
        summaries.append(json.loads(json_path.read_text()))
    return summaries


def print_table(summaries):
    if not summaries:
        print("No summary.json files found.")
        return

    header = (
        f"{'State point':<16} {'Atoms':>6} {'Force':>6} {'Thermo':>7} "
        f"{'CPU (s)':>10} {'GPU (s)':>10} {'Speedup':>8} {'Overall':>8}"
    )
    print(header)
    print("-" * len(header))

    all_pass = True
    for s in summaries:
        force = "PASS" if s["force_pass"] else "FAIL"
        thermo = "PASS" if s["thermo_pass"] else "FAIL"
        overall = "PASS" if s["overall_pass"] else "FAIL"
        all_pass = all_pass and s["overall_pass"]
        cpu_t = s.get("cpu_loop_s")
        gpu_t = s.get("gpu_loop_s")
        speedup = s.get("speedup")
        print(
            f"{s['statepoint']:<16} {s['n_atoms']:>6} {force:>6} {thermo:>7} "
            f"{cpu_t:>10.2f} {gpu_t:>10.2f} {speedup:>8.2f}x {overall:>8}"
        )

    print()
    print(f"Overall suite: {'PASS' if all_pass else 'FAIL'}")


def write_markdown(summaries, out_path: Path):
    lines = [
        "# Carbon-2.0 CPU vs GPU Benchmark Results",
        "",
        "| State point | Atoms | Force | Thermo | CPU (s) | GPU (s) | Speedup | Overall |",
        "|-------------|------:|-------|--------|--------:|--------:|--------:|---------|",
    ]
    for s in summaries:
        lines.append(
            f"| {s['statepoint']} | {s['n_atoms']} | "
            f"{'PASS' if s['force_pass'] else 'FAIL'} | "
            f"{'PASS' if s['thermo_pass'] else 'FAIL'} | "
            f"{s.get('cpu_loop_s', 0):.2f} | {s.get('gpu_loop_s', 0):.2f} | "
            f"{s.get('speedup', 0):.2f}x | "
            f"{'PASS' if s['overall_pass'] else 'FAIL'} |"
        )
    lines.extend(["", "## Per-state-point force errors (max |Δf|)", ""])
    for s in summaries:
        fs = s["force_stats"]
        lines.append(
            f"- **{s['statepoint']}**: "
            f"fx={fs['max_abs_fx']:.3e}, fy={fs['max_abs_fy']:.3e}, "
            f"fz={fs['max_abs_fz']:.3e}"
        )
    lines.extend(["", "## Final-step property differences (|CPU − GPU|)", ""])
    for s in summaries:
        diffs = s.get("final_property_diffs", {})
        if not diffs:
            continue
        parts = ", ".join(f"{k}={v:.3e}" for k, v in diffs.items())
        lines.append(f"- **{s['statepoint']}**: {parts}")

    out_path.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--results-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "results",
    )
    ap.add_argument(
        "--markdown-out",
        type=Path,
        default=None,
        help="Optional path for a markdown summary table",
    )
    args = ap.parse_args()

    summaries = load_summaries(args.results_dir)
    print_table(summaries)

    md_out = args.markdown_out or (args.results_dir / "SUMMARY.md")
    if summaries:
        write_markdown(summaries, md_out)
        print(f"Markdown summary: {md_out}")


if __name__ == "__main__":
    main()
