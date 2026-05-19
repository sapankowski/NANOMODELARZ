#!/usr/bin/env python3
"""Plot Task A convergence for Ni and NiO.

Run from the project root after the VASP convergence jobs finish:

    python3 common/A/plot_encut_convergence.py
"""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

try:
    import matplotlib.pyplot as plt
except ModuleNotFoundError:
    plt = None

from make_results_table import OUTPUT_DIR, ROOT, SYSTEMS, energy, kmesh, output_run_dir


def collect_encut(system_path: Path, atoms: int) -> list[tuple[int, float]]:
    encuts = next(cfg["encuts"] for cfg in SYSTEMS.values() if cfg["path"] == system_path)
    points: list[tuple[int, float]] = []
    for encut in encuts:
        run = system_path / "ENCUT" / f"ENCUT_{encut}"
        total_energy = energy(run)
        if total_energy is None:
            continue
        points.append((encut, total_energy / atoms))
    return points


def ibzkpt_count(run_dir: Path) -> int | None:
    ibzkpt = output_run_dir(run_dir) / "IBZKPT"
    if not ibzkpt.exists():
        return None
    lines = ibzkpt.read_text(errors="ignore").splitlines()
    if len(lines) < 2:
        return None
    try:
        return int(lines[1].split()[0])
    except (IndexError, ValueError):
        return None


def collect_kpoints(system_path: Path, atoms: int) -> list[tuple[int, str, float]]:
    points: list[tuple[int, str, float]] = []
    kmeshes = next(cfg["kmeshes"] for cfg in SYSTEMS.values() if cfg["path"] == system_path)
    for mesh in kmeshes:
        run = system_path / "KPOINTS" / f"K_{mesh:02d}x{mesh:02d}x{mesh:02d}"
        total_energy = energy(run)
        count = ibzkpt_count(run)
        if total_energy is None or count is None:
            continue
        points.append((count, kmesh(run), total_energy / atoms))
    return points


def plot_matplotlib(output_prefix: Path) -> list[Path]:
    if plt is None:
        return []

    outputs: list[Path] = []
    figures = [
        (
            "ENCUT",
            "ENCUT Convergence",
            "ENCUT (eV)",
            lambda cfg: [(encut, str(encut), value) for encut, value in collect_encut(cfg["path"], cfg["atoms"])],
            output_prefix.with_name(output_prefix.name + "_ENCUT_convergence"),
        ),
        (
            "KPOINTS",
            "k-point Convergence",
            "Number of irreducible k-points (IBZKPT)",
            lambda cfg: collect_kpoints(cfg["path"], cfg["atoms"]),
            output_prefix.with_name(output_prefix.name + "_KPOINTS_convergence"),
        ),
    ]

    for _kind, title, xlabel, collector, prefix in figures:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)

        for axis, (system, cfg) in zip(axes, SYSTEMS.items()):
            points = collector(cfg)
            if not points:
                axis.text(0.5, 0.5, "No completed runs", ha="center", va="center")
                axis.set_title(system)
                axis.set_axis_off()
                continue

            x_values = [point[0] for point in points]
            labels = [point[1] for point in points]
            energies = [point[2] for point in points]

            axis.plot(x_values, energies, marker="o", linewidth=2.0, color="tab:blue")
            for x, label, value in zip(x_values, labels, energies):
                axis.annotate(label, (x, value), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8)

            axis.set_title(f"{system}")
            axis.set_xlabel(xlabel)
            axis.set_ylabel("Total energy per atom (eV/atom)")
            axis.grid(True, linestyle=":", linewidth=0.7, alpha=0.8)

        fig.suptitle(f"Task A {title}", fontsize=14)
        png = prefix.with_suffix(".png")
        pdf = prefix.with_suffix(".pdf")
        fig.savefig(png, dpi=300)
        fig.savefig(pdf)
        outputs.extend([png, pdf])
    return outputs


def scale(value: float, source_min: float, source_max: float, target_min: float, target_max: float) -> float:
    if source_max == source_min:
        return (target_min + target_max) / 2.0
    fraction = (value - source_min) / (source_max - source_min)
    return target_min + fraction * (target_max - target_min)


def plot_svg(output_prefix: Path) -> list[Path]:
    outputs = []
    outputs.append(
        plot_svg_figure(
            output_prefix.with_name(output_prefix.name + "_ENCUT_convergence").with_suffix(".svg"),
            "Task A ENCUT Convergence",
            "ENCUT (eV)",
            lambda cfg: [(encut, str(encut), value) for encut, value in collect_encut(cfg["path"], cfg["atoms"])],
        )
    )
    outputs.append(
        plot_svg_figure(
            output_prefix.with_name(output_prefix.name + "_KPOINTS_convergence").with_suffix(".svg"),
            "Task A k-point Convergence",
            "Number of irreducible k-points (IBZKPT)",
            lambda cfg: collect_kpoints(cfg["path"], cfg["atoms"]),
        )
    )
    return outputs


def plot_svg_figure(output: Path, title: str, xlabel: str, collector) -> Path:
    width = 1100
    height = 470
    panel_width = 470
    panel_height = 300
    top = 95
    left_positions = [80, 610]
    bottom = top + panel_height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: Arial, sans-serif; fill: #222; }",
        ".title { font-size: 22px; font-weight: 700; }",
        ".subtitle { font-size: 16px; font-weight: 700; }",
        ".label { font-size: 13px; }",
        ".tick { font-size: 11px; fill: #444; }",
        ".grid { stroke: #d0d0d0; stroke-dasharray: 2 4; stroke-width: 1; }",
        ".axis { stroke: #333; stroke-width: 1.3; }",
        ".line { fill: none; stroke: #1f77b4; stroke-width: 2.5; }",
        ".point { fill: #1f77b4; stroke: white; stroke-width: 1.5; }",
        "</style>",
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<text x="{width / 2}" y="35" text-anchor="middle" class="title">{escape(title)}</text>',
        f'<text x="550" y="455" text-anchor="middle" class="label">{escape(xlabel)}</text>',
        '<text x="20" y="245" text-anchor="middle" class="label" transform="rotate(-90 20 245)">Total energy per atom (eV/atom)</text>',
    ]

    for left, (system, cfg) in zip(left_positions, SYSTEMS.items()):
        points = collector(cfg)
        parts.append(f'<text x="{left + panel_width / 2}" y="70" text-anchor="middle" class="subtitle">{escape(system)}</text>')

        if not points:
            parts.append(f'<text x="{left + panel_width / 2}" y="{top + panel_height / 2}" text-anchor="middle" class="label">No completed runs</text>')
            continue

        x_values = [point[0] for point in points]
        labels = [point[1] for point in points]
        energies = [point[2] for point in points]

        x_min, x_max = min(x_values), max(x_values)
        y_min = min(energies)
        y_max = max(energies)
        padding = max((y_max - y_min) * 0.08, 1e-6)
        y_min -= padding
        y_max += padding

        for tick in [y_min, y_min + (y_max - y_min) * 0.25, (y_min + y_max) / 2, y_min + (y_max - y_min) * 0.75, y_max]:
            y = scale(tick, y_min, y_max, bottom, top)
            parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + panel_width}" y2="{y:.1f}" class="grid"/>')
            parts.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" class="tick">{tick:.3f}</text>')

        for x_value, label in zip(x_values, labels):
            x = scale(x_value, x_min, x_max, left, left + panel_width)
            parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" class="grid"/>')
            parts.append(f'<text x="{x:.1f}" y="{bottom + 18}" text-anchor="middle" class="tick">{escape(label)}</text>')

        parts.append(f'<rect x="{left}" y="{top}" width="{panel_width}" height="{panel_height}" fill="none" class="axis"/>')

        svg_points = []
        for x_value, energy_value in zip(x_values, energies):
            x = scale(x_value, x_min, x_max, left, left + panel_width)
            y = scale(energy_value, y_min, y_max, bottom, top)
            svg_points.append(f"{x:.1f},{y:.1f}")

        parts.append(f'<polyline points="{" ".join(svg_points)}" class="line"/>')
        for x_value, energy_value in zip(x_values, energies):
            x = scale(x_value, x_min, x_max, left, left + panel_width)
            y = scale(energy_value, y_min, y_max, bottom, top)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" class="point"/>')
            parts.append(f'<text x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle" class="tick">{energy_value:.3f}</text>')

    parts.append("</svg>")
    output.write_text("\n".join(parts) + "\n")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output-prefix",
        type=Path,
        default=OUTPUT_DIR / "Task_A",
        help="Output filename prefix. Default: outputs/A/Task_A",
    )
    args = parser.parse_args()

    output_prefix = args.output_prefix
    if not output_prefix.is_absolute():
        output_prefix = ROOT / output_prefix

    outputs = plot_matplotlib(output_prefix)
    if not outputs:
        outputs = plot_svg(output_prefix)

    print("Wrote " + " and ".join(str(output) for output in outputs))


if __name__ == "__main__":
    main()
