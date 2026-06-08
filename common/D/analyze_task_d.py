#!/usr/bin/env python3
"""Analyze Task D phonon outputs and create phonon plots."""

from __future__ import annotations

import csv
import math
import re
import shutil
import subprocess
from html import escape
from pathlib import Path

from prepare_task_d import CASES, ROOT


OUTPUT_DIR = ROOT / "outputs" / "D"
CALC_DIR = OUTPUT_DIR / "calculations"
REPORT_DIR = OUTPUT_DIR / "reports"
FIGURE_DIR = OUTPUT_DIR / "figures"

MODE_RE = re.compile(
    r"^\s*(\d+)\s+(f\/i|f)\s*=\s*([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s+THz"
    r".*?([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s+cm-1"
    r"\s+([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s+meV",
    re.M,
)
FLOAT_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?")
BRANCH_RE = re.compile(
    r"^\s*(\d+)\s+"
    r"([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s+"
    r"([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s+"
    r"([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s+"
    r"([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s*$"
)


def calc_case(case: dict, step: str) -> Path:
    return CALC_DIR / case["case_dir"].relative_to(ROOT) / step


def read_text(path: Path) -> str:
    return path.read_text(errors="ignore") if path.exists() else ""


def parse_mode_lines(text: str) -> list[dict[str, float | int | bool]]:
    modes = []
    for match in MODE_RE.finditer(text):
        imaginary = match.group(2) == "f/i"
        thz = float(match.group(3))
        cm1 = float(match.group(4))
        mev = float(match.group(5))
        if imaginary:
            thz = -abs(thz)
            cm1 = -abs(cm1)
            mev = -abs(mev)
        modes.append(
            {
                "mode": int(match.group(1)),
                "thz": thz,
                "cm1": cm1,
                "mev": mev,
                "imaginary": imaginary,
            }
        )
    return modes


def parse_branch_frequency(line: str) -> dict[str, float | int | bool] | None:
    match = BRANCH_RE.match(line)
    if not match:
        return None
    thz = float(match.group(2))
    return {
        "mode": int(match.group(1)),
        "thz": thz,
        "cm1": float(match.group(4)),
        "mev": float(match.group(5)),
        "imaginary": thz < 0.0,
    }


def expected_qpoints(qpoints: Path) -> int | None:
    if not qpoints.exists():
        return None
    lines = qpoints.read_text(errors="ignore").splitlines()
    if len(lines) < 5 or "line" not in lines[2].lower():
        return None
    try:
        points_per_segment = int(lines[1].split()[0])
    except (IndexError, ValueError):
        return None
    labels = [line for line in lines[4:] if "!" in line]
    return (len(labels) // 2) * points_per_segment


def qpoint_path(qpoints: Path) -> tuple[list[float], list[tuple[float, str]]]:
    if not qpoints.exists():
        return [], []
    lines = qpoints.read_text(errors="ignore").splitlines()
    try:
        points_per_segment = int(lines[1].split()[0])
    except (IndexError, ValueError):
        points_per_segment = 40

    labeled_points: list[tuple[str, tuple[float, float, float]]] = []
    for line in lines[4:]:
        if "!" not in line:
            continue
        left, label = line.split("!", 1)
        values = [float(value) for value in left.split()[:3]]
        labeled_points.append((label.strip().replace("Gamma", "G"), tuple(values)))

    x_values: list[float] = []
    ticks: list[tuple[float, str]] = []
    distance = 0.0
    for segment_index in range(0, len(labeled_points), 2):
        if segment_index + 1 >= len(labeled_points):
            break
        start_label, start = labeled_points[segment_index]
        end_label, end = labeled_points[segment_index + 1]
        if not x_values:
            ticks.append((0.0, start_label))
        step = math.sqrt(sum((a - b) ** 2 for a, b in zip(start, end)))
        for point_index in range(points_per_segment):
            fraction = point_index / max(points_per_segment - 1, 1)
            x_values.append(distance + step * fraction)
        distance += step
        if ticks and abs(ticks[-1][0] - distance) < 1e-8:
            if end_label not in ticks[-1][1].split("/"):
                ticks[-1] = (ticks[-1][0], f"{ticks[-1][1]}/{end_label}")
        else:
            ticks.append((distance, end_label))
    return x_values, ticks


def parse_dispersion(path: Path) -> list[list[dict[str, float | int | bool]]]:
    text = read_text(path / "OUTCAR")
    if not text:
        return []

    q_blocks_from_branches: list[list[dict[str, float | int | bool]]] = []
    current_branch_block: list[dict[str, float | int | bool]] = []
    expect_branch_frequency = False
    for line in text.splitlines():
        if re.match(r"\s*q-point No\.", line):
            if current_branch_block:
                q_blocks_from_branches.append(current_branch_block)
            current_branch_block = []
            expect_branch_frequency = False
            continue
        if "branch index" in line and "f[THz]" in line:
            expect_branch_frequency = True
            continue
        if expect_branch_frequency:
            mode = parse_branch_frequency(line)
            if mode:
                current_branch_block.append(mode)
            expect_branch_frequency = False
    if current_branch_block:
        q_blocks_from_branches.append(current_branch_block)
    if q_blocks_from_branches:
        return q_blocks_from_branches

    q_blocks: list[list[dict[str, float | int | bool]]] = []
    current: list[str] = []
    in_q_block = False
    for line in text.splitlines():
        if "q-point" in line.lower() and FLOAT_RE.search(line):
            if current:
                modes = parse_mode_lines("\n".join(current))
                if modes:
                    q_blocks.append(modes)
            current = []
            in_q_block = True
        elif in_q_block:
            current.append(line)
    if current:
        modes = parse_mode_lines("\n".join(current))
        if modes:
            q_blocks.append(modes)
    if q_blocks:
        return q_blocks

    modes = parse_mode_lines(text)
    npoints = expected_qpoints(path / "QPOINTS")
    if npoints and modes and len(modes) % npoints == 0:
        modes_per_q = len(modes) // npoints
        return [modes[index : index + modes_per_q] for index in range(0, len(modes), modes_per_q)]
    return []


def parse_gamma_modes(case: dict) -> list[dict[str, float | int | bool]]:
    dispersion = parse_dispersion(calc_case(case, "dispersion"))
    if dispersion:
        return dispersion[0]
    return parse_mode_lines(read_text(calc_case(case, "force_constants") / "OUTCAR"))


def parse_dos(path: Path) -> list[tuple[float, float]]:
    lines = read_text(path / "OUTCAR").splitlines()
    if not lines:
        return []
    marker_indices = [
        index
        for index, line in enumerate(lines)
        if "phonon" in line.lower() and "dos" in line.lower()
    ]
    best: list[tuple[float, float]] = []
    for start in marker_indices:
        rows: list[tuple[float, float]] = []
        for line in lines[start + 1 : start + 5000]:
            values = [float(value) for value in FLOAT_RE.findall(line)]
            if len(values) >= 2 and not any(char.isalpha() for char in line.replace("E", "").replace("e", "")):
                rows.append((values[0], values[1]))
            elif len(rows) > 10:
                break
        if len(rows) > len(best):
            best = rows
    return best


def scale(value: float, source_min: float, source_max: float, target_min: float, target_max: float) -> float:
    if source_max == source_min:
        return (target_min + target_max) / 2.0
    return target_min + (value - source_min) * (target_max - target_min) / (source_max - source_min)


def svg_header(width: int, height: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: Arial, sans-serif; fill: #222; }",
        ".title { font-size: 21px; font-weight: 700; }",
        ".label { font-size: 13px; }",
        ".tick { font-size: 11px; fill: #444; }",
        ".axis { stroke: #333; stroke-width: 1.2; fill: none; }",
        ".grid { stroke: #d4d4d4; stroke-dasharray: 2 4; stroke-width: 1; }",
        ".qline { stroke: #777; stroke-dasharray: 4 5; stroke-width: 1; }",
        ".branch { fill: none; stroke: #1f77b4; stroke-width: 1.35; }",
        ".zero { stroke: #d62728; stroke-width: 1.2; stroke-dasharray: 5 4; }",
        ".dos { fill: none; stroke: #2ca02c; stroke-width: 1.8; }",
        "</style>",
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2}" y="30" text-anchor="middle" class="title">{escape(title)}</text>',
    ]


def polyline(points: list[tuple[float, float]], cls: str) -> str:
    coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{coords}" class="{cls}"/>'


def plot_dispersion(case: dict) -> Path | None:
    q_blocks = parse_dispersion(calc_case(case, "dispersion"))
    if not q_blocks:
        return None
    x_values, ticks = qpoint_path(calc_case(case, "dispersion") / "QPOINTS")
    if not x_values:
        x_values = list(range(len(q_blocks)))
        ticks = [(0.0, "G"), (float(len(q_blocks) - 1), "")]
    point_count = min(len(x_values), len(q_blocks))
    q_blocks = q_blocks[:point_count]
    x_values = x_values[:point_count]

    branches = list(zip(*[[float(mode["thz"]) for mode in modes] for modes in q_blocks]))
    all_freqs = [freq for branch in branches for freq in branch]
    ymin = min(min(all_freqs), 0.0)
    ymax = max(max(all_freqs), 1e-6)
    padding = max((ymax - ymin) * 0.08, 0.2)
    ymin -= padding
    ymax += padding

    output = FIGURE_DIR / f"{case['key']}_phonon_dispersion.svg"
    width, height = 780, 500
    left, right, top, bottom = 82, 730, 60, 420
    xmax = max(x_values) if x_values else 1.0
    parts = svg_header(width, height, f"{case['key']} phonon dispersion")
    parts.append(f'<rect x="{left}" y="{top}" width="{right-left}" height="{bottom-top}" class="axis"/>')
    zero_y = scale(0.0, ymin, ymax, bottom, top)
    parts.append(f'<line x1="{left}" y1="{zero_y:.1f}" x2="{right}" y2="{zero_y:.1f}" class="zero"/>')
    for tick_value, label in ticks:
        x = scale(tick_value, 0, xmax, left, right)
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" class="qline"/>')
        parts.append(f'<text x="{x:.1f}" y="{bottom + 18}" text-anchor="middle" class="tick">{escape(label)}</text>')
    for branch in branches:
        points = [(scale(x, 0, xmax, left, right), scale(freq, ymin, ymax, bottom, top)) for x, freq in zip(x_values, branch)]
        parts.append(polyline(points, "branch"))
    parts.append(f'<text x="{(left+right)/2}" y="465" text-anchor="middle" class="label">High-symmetry q-path</text>')
    parts.append('<text x="24" y="250" text-anchor="middle" class="label" transform="rotate(-90 24 250)">Frequency (THz)</text>')
    parts.append("</svg>")
    output.write_text("\n".join(parts) + "\n")
    return output


def plot_dos(case: dict) -> Path | None:
    dos = parse_dos(calc_case(case, "dos"))
    if not dos:
        return None
    frequencies = [row[0] for row in dos]
    densities = [row[1] for row in dos]
    output = FIGURE_DIR / f"{case['key']}_phdos.svg"
    width, height = 760, 460
    left, right, top, bottom = 82, 710, 60, 390
    xmin, xmax = min(frequencies), max(frequencies)
    ymin, ymax = 0.0, max(densities) if densities else 1.0
    ymax = max(ymax, 1e-9)
    parts = svg_header(width, height, f"{case['key']} phonon DOS")
    parts.append(f'<rect x="{left}" y="{top}" width="{right-left}" height="{bottom-top}" class="axis"/>')
    parts.append(polyline([(scale(x, xmin, xmax, left, right), scale(y, ymin, ymax, bottom, top)) for x, y in dos], "dos"))
    parts.append(f'<text x="{(left+right)/2}" y="430" text-anchor="middle" class="label">Frequency (THz)</text>')
    parts.append('<text x="24" y="230" text-anchor="middle" class="label" transform="rotate(-90 24 230)">PhDOS</text>')
    parts.append("</svg>")
    output.write_text("\n".join(parts) + "\n")
    return output


def write_tables(summary_rows: list[dict[str, str]], mode_rows: list[dict[str, str]]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, rows in (
        ("Task_D_summary_table", summary_rows),
        ("Task_D_gamma_modes", mode_rows),
    ):
        if not rows:
            continue
        with (REPORT_DIR / f"{filename}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        headers = list(rows[0])
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ]
        for row in rows:
            lines.append("| " + " | ".join(row[header] for header in headers) + " |")
        (REPORT_DIR / f"{filename}.md").write_text("\n".join(lines) + "\n")


def convert_svg_figures(figures: list[Path]) -> list[Path]:
    converter = shutil.which("rsvg-convert")
    if converter is None:
        return []
    report_figure_dir = ROOT / "report" / "figures"
    report_figure_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for figure in figures:
        pdf = report_figure_dir / figure.with_suffix(".pdf").name
        subprocess.run([converter, "-f", "pdf", "-o", str(pdf), str(figure)], check=True)
        outputs.append(pdf)
    return outputs


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, str]] = []
    mode_rows: list[dict[str, str]] = []
    figures: list[Path] = []

    for case in CASES:
        gamma_modes = parse_gamma_modes(case)
        imaginary_count = sum(1 for mode in gamma_modes if bool(mode["imaginary"]) and abs(float(mode["thz"])) > 0.05)
        stable = "pending" if not gamma_modes else ("no" if imaginary_count else "yes")
        min_frequency = min((float(mode["thz"]) for mode in gamma_modes), default=None)
        summary_rows.append(
            {
                "System": case["system"],
                "Case": case["key"],
                "Gamma modes found": str(len(gamma_modes)) if gamma_modes else "pending",
                "Lowest Gamma frequency, THz": "pending" if min_frequency is None else f"{min_frequency:.4f}",
                "Imaginary modes": "pending" if not gamma_modes else str(imaginary_count),
                "Dynamically stable?": stable,
            }
        )
        for mode in gamma_modes:
            mode_rows.append(
                {
                    "System": case["system"],
                    "Case": case["key"],
                    "Mode": str(mode["mode"]),
                    "Frequency, THz": f"{float(mode['thz']):.6f}",
                    "Frequency, cm^-1": f"{float(mode['cm1']):.3f}",
                    "Imaginary?": "yes" if mode["imaginary"] else "no",
                    "Dynamically stable?": "no" if mode["imaginary"] else "yes",
                }
            )
        for figure in (plot_dispersion(case), plot_dos(case)):
            if figure is not None:
                figures.append(figure)

    write_tables(summary_rows, mode_rows)
    print(f"Wrote {REPORT_DIR / 'Task_D_summary_table.md'}")
    if mode_rows:
        print(f"Wrote {REPORT_DIR / 'Task_D_gamma_modes.md'}")
    if figures:
        print("Wrote figures: " + ", ".join(str(path.relative_to(ROOT)) for path in figures))
        pdfs = convert_svg_figures(figures)
        if pdfs:
            print("Wrote report PDFs: " + ", ".join(str(path.relative_to(ROOT)) for path in pdfs))
    else:
        print("No phonon figures written yet; run the Task D VASP jobs first.")


if __name__ == "__main__":
    main()
