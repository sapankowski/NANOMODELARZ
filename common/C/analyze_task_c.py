#!/usr/bin/env python3
"""Analyze Task C VASP outputs and create electronic-structure plots."""

from __future__ import annotations

import csv
import math
import re
import shutil
import subprocess
from html import escape
from pathlib import Path

from prepare_task_c import CASES, ROOT


OUTPUT_DIR = ROOT / "outputs" / "C"
CALC_DIR = OUTPUT_DIR / "calculations"
REPORT_DIR = OUTPUT_DIR / "reports"
FIGURE_DIR = OUTPUT_DIR / "figures"


def calc_case(case: dict, step: str) -> Path:
    return CALC_DIR / case["case_dir"].relative_to(ROOT) / step


def read_text(path: Path) -> str:
    return path.read_text(errors="ignore") if path.exists() else ""


def efermi(path: Path) -> float | None:
    outcar = read_text(path / "OUTCAR")
    matches = re.findall(r"E-fermi\s*:\s*(-?\d+\.\d+)", outcar)
    if matches:
        return float(matches[-1])
    doscar = path / "DOSCAR"
    if doscar.exists():
        lines = doscar.read_text(errors="ignore").splitlines()
        if len(lines) >= 6:
            parts = lines[5].split()
            if len(parts) >= 4:
                try:
                    return float(parts[3])
                except ValueError:
                    pass
    return None


def total_moment(path: Path) -> float | None:
    oszicar = path / "OSZICAR"
    if oszicar.exists():
        matches = re.findall(r"mag=\s*(-?\d+\.\d+)", oszicar.read_text(errors="ignore"))
        if matches:
            return float(matches[-1])
    outcar = read_text(path / "OUTCAR")
    blocks = re.findall(r"magnetization \(x\)\s+.*?-+\n(.*?)\n-+\n", outcar, flags=re.S)
    if not blocks:
        return None
    values = []
    for line in blocks[-1].splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].isdigit():
            values.append(float(parts[4]))
    return sum(values) if values else None


def read_poscar_species(path: Path) -> list[str]:
    lines = path.read_text(errors="ignore").splitlines()
    elements = lines[5].split()
    counts = [int(value) for value in lines[6].split()]
    return [element for element, count in zip(elements, counts) for _ in range(count)]


def parse_doscar(path: Path) -> dict | None:
    doscar = path / "DOSCAR"
    poscar = path / "POSCAR"
    if not doscar.exists() or not poscar.exists():
        return None

    lines = doscar.read_text(errors="ignore").splitlines()
    if len(lines) < 7:
        return None
    try:
        natoms = int(lines[0].split()[0])
        header = lines[5].split()
        nedos = int(float(header[2]))
        fermi = float(header[3])
    except (IndexError, ValueError):
        return None

    total = []
    cursor = 6
    for line in lines[cursor : cursor + nedos]:
        parts = [float(value) for value in line.split()]
        if len(parts) >= 5:
            total.append({"energy": parts[0] - fermi, "up": parts[1], "down": -parts[2]})
        elif len(parts) >= 3:
            total.append({"energy": parts[0] - fermi, "up": parts[1], "down": 0.0})
    cursor += nedos

    species = read_poscar_species(poscar)
    pdos = {}
    for atom_index in range(natoms):
        if cursor >= len(lines):
            break
        cursor += 1
        element = species[atom_index] if atom_index < len(species) else f"ion{atom_index + 1}"
        for line in lines[cursor : cursor + nedos]:
            parts = [float(value) for value in line.split()]
            if len(parts) < 2:
                continue
            energy = parts[0] - fermi
            values = parts[1:]
            spin = len(values) >= 18
            if spin:
                s = values[0] + values[1]
                p = sum(values[i] for i in range(2, min(8, len(values))))
                d = sum(values[i] for i in range(8, min(18, len(values))))
            else:
                s = values[0]
                p = sum(values[1:4])
                d = sum(values[4:9])
            for orbital, value in (("s", s), ("p", p), ("d", d)):
                key = f"{element}_{orbital}"
                pdos.setdefault(key, []).append((energy, value))
        cursor += nedos

    return {"fermi": fermi, "total": total, "pdos": pdos}


def parse_eigenval(path: Path) -> dict | None:
    eigenval = path / "EIGENVAL"
    if not eigenval.exists():
        return None
    lines = [line.strip() for line in eigenval.read_text(errors="ignore").splitlines()]
    if len(lines) < 8:
        return None
    try:
        counts = lines[5].split()
        nkpts = int(counts[1])
        nbands = int(counts[2])
    except (IndexError, ValueError):
        return None

    kpoints = []
    bands_up = [[] for _ in range(nbands)]
    bands_down = [[] for _ in range(nbands)]
    occupancies = []
    cursor = 6
    for _ in range(nkpts):
        while cursor < len(lines) and not lines[cursor]:
            cursor += 1
        if cursor >= len(lines):
            break
        parts = lines[cursor].split()
        cursor += 1
        if len(parts) < 4:
            break
        kpoints.append(tuple(float(value) for value in parts[:3]))
        for band in range(nbands):
            if cursor >= len(lines):
                break
            values = lines[cursor].split()
            cursor += 1
            if len(values) >= 5:
                bands_up[band].append(float(values[1]))
                bands_down[band].append(float(values[2]))
                occupancies.append((float(values[1]), float(values[3])))
                occupancies.append((float(values[2]), float(values[4])))
            elif len(values) >= 3:
                bands_up[band].append(float(values[1]))
                occupancies.append((float(values[1]), float(values[2])))

    return {
        "kpoints": kpoints,
        "bands_up": [band for band in bands_up if band],
        "bands_down": [band for band in bands_down if band],
        "occupancies": occupancies,
    }


def parse_procar_projection(path: Path, targets: list[tuple[str, str]]) -> dict[str, list[list[float]]]:
    procar = path / "PROCAR"
    poscar = path / "POSCAR"
    if not procar.exists() or not poscar.exists():
        return {}
    species = read_poscar_species(poscar)
    lines = procar.read_text(errors="ignore").splitlines()
    if len(lines) < 3:
        return {}
    match = re.search(r"# of k-points:\s*(\d+)\s+# of bands:\s*(\d+)\s+# of ions:\s*(\d+)", lines[1])
    if not match:
        return {}
    nkpts, nbands, nions = (int(match.group(i)) for i in range(1, 4))
    weights = {f"{element}_{orbital}": [[] for _ in range(nbands)] for element, orbital in targets}
    orbital_columns = {"s": [0], "p": [1, 2, 3], "d": [4, 5, 6, 7, 8]}

    cursor = 2
    k_seen = 0
    while cursor < len(lines) and k_seen < nkpts:
        if not lines[cursor].lstrip().startswith("k-point"):
            cursor += 1
            continue
        k_seen += 1
        cursor += 1
        for band_index in range(nbands):
            while cursor < len(lines) and not lines[cursor].lstrip().startswith("band"):
                cursor += 1
            if cursor >= len(lines):
                break
            cursor += 1
            while cursor < len(lines) and not lines[cursor].lstrip().startswith("ion"):
                cursor += 1
            cursor += 1
            totals = {key: 0.0 for key in weights}
            for ion_index in range(nions):
                if cursor >= len(lines):
                    break
                parts = lines[cursor].split()
                cursor += 1
                if len(parts) < 11 or not parts[0].isdigit():
                    continue
                element = species[ion_index] if ion_index < len(species) else ""
                values = [float(value) for value in parts[1:10]]
                for target_element, orbital in targets:
                    if element != target_element:
                        continue
                    key = f"{target_element}_{orbital}"
                    totals[key] += sum(values[idx] for idx in orbital_columns[orbital])
            for key, value in totals.items():
                weights[key][band_index].append(value)
    return weights


def kdistances(kpoints: list[tuple[float, float, float]]) -> list[float]:
    if not kpoints:
        return []
    distances = [0.0]
    for previous, current in zip(kpoints, kpoints[1:]):
        step = math.sqrt(sum((a - b) ** 2 for a, b in zip(previous, current)))
        distances.append(distances[-1] + step)
    return distances


def band_gap(path: Path) -> tuple[float | None, str, str]:
    data = parse_eigenval(path)
    if data is None:
        return None, "pending", "pending"

    eigenval = path / "EIGENVAL"
    lines = [line.strip() for line in eigenval.read_text(errors="ignore").splitlines()]
    try:
        counts = lines[5].split()
        nkpts = int(counts[1])
        nbands = int(counts[2])
    except (IndexError, ValueError):
        return None, "pending", "pending"

    occupied = []
    unoccupied = []
    cursor = 6
    for k_index in range(nkpts):
        while cursor < len(lines) and not lines[cursor]:
            cursor += 1
        cursor += 1
        for _band in range(nbands):
            values = lines[cursor].split()
            cursor += 1
            if len(values) >= 5:
                pairs = [(float(values[1]), float(values[3])), (float(values[2]), float(values[4]))]
            elif len(values) >= 3:
                pairs = [(float(values[1]), float(values[2]))]
            else:
                pairs = []
            for energy, occ in pairs:
                if occ > 0.5:
                    occupied.append((energy, k_index))
                else:
                    unoccupied.append((energy, k_index))

    if not occupied or not unoccupied:
        return None, "pending", "pending"
    vbm = max(occupied, key=lambda item: item[0])
    cbm = min(unoccupied, key=lambda item: item[0])
    gap = max(0.0, cbm[0] - vbm[0])
    character = "Metallic" if gap < 0.05 else "Insulating"
    gap_type = "metallic" if character == "Metallic" else ("direct" if vbm[1] == cbm[1] else "indirect")
    return gap, character, gap_type


def dominant_orbitals(dos: dict | None, window: float = 0.5) -> str:
    if dos is None:
        return "pending"
    totals = {}
    for key, points in dos["pdos"].items():
        value = sum(density for energy, density in points if abs(energy) <= window)
        if value > 0.0:
            totals[key] = value
    if not totals:
        return "pending"
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:3]
    return ", ".join(key.replace("_", " ") for key, _value in ranked)


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
        ".kline { stroke: #777; stroke-dasharray: 4 5; stroke-width: 1; }",
        ".up { fill: none; stroke: #1f77b4; stroke-width: 1.5; }",
        ".down { fill: none; stroke: #d62728; stroke-width: 1.2; }",
        ".pdos1 { fill: none; stroke: #2ca02c; stroke-width: 1.4; }",
        ".pdos2 { fill: none; stroke: #9467bd; stroke-width: 1.4; }",
        ".pdos3 { fill: none; stroke: #ff7f0e; stroke-width: 1.4; }",
        ".legend-line { stroke-width: 2.4; stroke-linecap: round; }",
        ".legend-dot { stroke: white; stroke-width: 1; }",
        ".legend-bg { fill: white; fill-opacity: 0.78; stroke: #bbbbbb; stroke-opacity: 0.65; stroke-width: 0.8; }",
        "</style>",
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2}" y="30" text-anchor="middle" class="title">{escape(title)}</text>',
    ]


def polyline(points: list[tuple[float, float]], cls: str) -> str:
    coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{coords}" class="{cls}"/>'


def legend_line(x: float, y: float, cls: str, label: str) -> str:
    return (
        f'<line x1="{x}" y1="{y}" x2="{x + 28}" y2="{y}" class="{cls} legend-line"/>'
        f'<text x="{x + 36}" y="{y + 4}" class="label">{escape(label)}</text>'
    )


def legend_dot(x: float, y: float, color: str, label: str) -> str:
    return (
        f'<circle cx="{x + 14}" cy="{y}" r="4" fill="{color}" fill-opacity="0.65" class="legend-dot"/>'
        f'<text x="{x + 36}" y="{y + 4}" class="label">{escape(label)}</text>'
    )


def legend_background(x: float, y: float, width: float, rows: int) -> str:
    height = 18 + max(rows, 1) * 22
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="4" class="legend-bg"/>'


def projection_targets(case: dict) -> list[tuple[str, str]]:
    if case["system"] == "NiO":
        return [("Ni", "d"), ("O", "p")]
    return [("Ni", "d"), ("Ni", "p")]


def band_ticks(path: Path, distances: list[float]) -> list[tuple[float, str]]:
    kpoints = path / "KPOINTS"
    if not kpoints.exists() or not distances:
        return [(0.0, "G"), (distances[-1], "")]

    lines = kpoints.read_text(errors="ignore").splitlines()
    try:
        points_per_segment = int(lines[1].split()[0])
    except (IndexError, ValueError):
        points_per_segment = 40

    labels = []
    for line in lines[4:]:
        if "!" not in line:
            continue
        label = line.split("!", 1)[1].strip().replace("Gamma", "G")
        if label:
            labels.append(label)

    ticks: list[tuple[float, str]] = [(0.0, labels[0] if labels else "G")]
    segment_count = len(labels) // 2
    for segment_index in range(segment_count):
        distance_index = min(segment_index * points_per_segment + points_per_segment - 1, len(distances) - 1)
        end_label = labels[2 * segment_index + 1]
        distance = distances[distance_index]
        if ticks and abs(ticks[-1][0] - distance) < 1e-8:
            if end_label and end_label not in ticks[-1][1].split("/"):
                ticks[-1] = (ticks[-1][0], f"{ticks[-1][1]}/{end_label}" if ticks[-1][1] else end_label)
        else:
            ticks.append((distance, end_label))
    return ticks


def draw_band_ticks(
    parts: list[str],
    ticks: list[tuple[float, str]],
    xmax: float,
    left: int,
    right: int,
    top: int,
    bottom: int,
) -> None:
    for distance, label in ticks:
        x = scale(distance, 0, xmax, left, right)
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" class="kline"/>')
        if label:
            parts.append(f'<text x="{x:.1f}" y="{bottom + 18}" text-anchor="middle" class="tick">{escape(label)}</text>')


def plot_dos(case: dict, dos: dict | None) -> Path | None:
    if dos is None or not dos["total"]:
        return None
    output = FIGURE_DIR / f"{case['key']}_dos.svg"
    width, height = 760, 460
    left, right, top, bottom = 80, 710, 60, 390
    energies = [point["energy"] for point in dos["total"] if -8.0 <= point["energy"] <= 8.0]
    up = [point["up"] for point in dos["total"] if -8.0 <= point["energy"] <= 8.0]
    down = [point["down"] for point in dos["total"] if -8.0 <= point["energy"] <= 8.0]
    if not energies:
        return None
    ymax = max(max(up), abs(min(down)), 1e-9)
    parts = svg_header(width, height, f"{case['key']} total and spin-resolved DOS")
    parts.append(f'<rect x="{left}" y="{top}" width="{right-left}" height="{bottom-top}" class="axis"/>')
    parts.append(f'<line x1="{left}" y1="{scale(0, -ymax, ymax, bottom, top):.1f}" x2="{right}" y2="{scale(0, -ymax, ymax, bottom, top):.1f}" class="grid"/>')
    parts.append(f'<line x1="{scale(0, -8, 8, left, right):.1f}" y1="{top}" x2="{scale(0, -8, 8, left, right):.1f}" y2="{bottom}" class="grid"/>')
    parts.append(polyline([(scale(e, -8, 8, left, right), scale(v, -ymax, ymax, bottom, top)) for e, v in zip(energies, up)], "up"))
    parts.append(polyline([(scale(e, -8, 8, left, right), scale(v, -ymax, ymax, bottom, top)) for e, v in zip(energies, down)], "down"))
    parts.append(f'<text x="{(left+right)/2}" y="430" text-anchor="middle" class="label">Energy - E_F (eV)</text>')
    parts.append('<text x="22" y="230" text-anchor="middle" class="label" transform="rotate(-90 22 230)">DOS (states/eV)</text>')
    parts.append(legend_background(right - 168, top + 6, 145, 2))
    parts.append(legend_line(right - 155, top + 22, "up", "spin up"))
    parts.append(legend_line(right - 155, top + 44, "down", "spin down"))
    parts.append("</svg>")
    output.write_text("\n".join(parts) + "\n")
    return output


def plot_pdos(case: dict, dos: dict | None) -> Path | None:
    if dos is None or not dos["pdos"]:
        return None
    output = FIGURE_DIR / f"{case['key']}_pdos.svg"
    width, height = 760, 460
    left, right, top, bottom = 80, 710, 60, 390
    selected = []
    for key in ("Ni_d", "O_p", "Ni_s", "Ni_p", "O_s"):
        if key in dos["pdos"]:
            selected.append((key, dos["pdos"][key]))
    selected = selected[:5]
    values = [density for _key, points in selected for energy, density in points if -8.0 <= energy <= 8.0]
    ymax = max(values) if values else 1.0
    parts = svg_header(width, height, f"{case['key']} projected DOS")
    parts.append(f'<rect x="{left}" y="{top}" width="{right-left}" height="{bottom-top}" class="axis"/>')
    parts.append(f'<line x1="{scale(0, -8, 8, left, right):.1f}" y1="{top}" x2="{scale(0, -8, 8, left, right):.1f}" y2="{bottom}" class="grid"/>')
    classes = ["up", "pdos1", "pdos2", "pdos3", "down"]
    parts.append(legend_background(right - 168, top + 6, 145, len(selected)))
    for idx, (key, points) in enumerate(selected):
        visible = [(energy, density) for energy, density in points if -8.0 <= energy <= 8.0]
        parts.append(polyline([(scale(e, -8, 8, left, right), scale(v, 0, ymax, bottom, top)) for e, v in visible], classes[idx]))
        parts.append(legend_line(right - 155, top + 22 + idx * 20, classes[idx], key.replace("_", " ")))
    parts.append(f'<text x="{(left+right)/2}" y="430" text-anchor="middle" class="label">Energy - E_F (eV)</text>')
    parts.append('<text x="22" y="230" text-anchor="middle" class="label" transform="rotate(-90 22 230)">PDOS (states/eV)</text>')
    parts.append("</svg>")
    output.write_text("\n".join(parts) + "\n")
    return output


def plot_bands(case: dict, data: dict | None, fermi: float | None, projected: bool = False) -> Path | None:
    if data is None or fermi is None or not data["kpoints"]:
        return None
    output = FIGURE_DIR / f"{case['key']}_{'projected_bands' if projected else 'bands'}.svg"
    width, height = 760, 500
    left, right, top, bottom = 80, 710, 60, 420
    distances = kdistances(data["kpoints"])
    xmax = max(distances) if distances else 1.0
    ymin, ymax = -8.0, 8.0
    parts = svg_header(width, height, f"{case['key']} {'projected ' if projected else ''}band structure")
    parts.append(f'<rect x="{left}" y="{top}" width="{right-left}" height="{bottom-top}" class="axis"/>')
    parts.append(f'<line x1="{left}" y1="{scale(0, ymin, ymax, bottom, top):.1f}" x2="{right}" y2="{scale(0, ymin, ymax, bottom, top):.1f}" class="grid"/>')
    draw_band_ticks(parts, band_ticks(calc_case(case, "bands"), distances), xmax, left, right, top, bottom)
    for band in data["bands_up"]:
        shifted = [energy - fermi for energy in band]
        visible = [(x, e) for x, e in zip(distances, shifted) if ymin <= e <= ymax]
        if len(visible) > 1:
            parts.append(polyline([(scale(x, 0, xmax, left, right), scale(e, ymin, ymax, bottom, top)) for x, e in visible], "up"))
    for band in data["bands_down"]:
        shifted = [energy - fermi for energy in band]
        visible = [(x, e) for x, e in zip(distances, shifted) if ymin <= e <= ymax]
        if len(visible) > 1:
            parts.append(polyline([(scale(x, 0, xmax, left, right), scale(e, ymin, ymax, bottom, top)) for x, e in visible], "down"))
    projections = {}
    if projected:
        projections = parse_procar_projection(calc_case(case, "bands"), projection_targets(case))
        colors = {"Ni_d": "#2ca02c", "O_p": "#ff7f0e", "Ni_p": "#9467bd"}
        legend_rows = len(projections) + 1 + (1 if data["bands_down"] else 0)
        parts.append(legend_background(right - 188, top + 8, 168, legend_rows))
        band_stride = max(1, len(data["bands_up"]) // 13)
        kpoint_stride = max(1, len(distances) // 80)
        for target_index, (key, weights) in enumerate(projections.items()):
            color = colors.get(key, "#2ca02c")
            for band_index in range(0, min(len(data["bands_up"]), len(weights)), band_stride):
                band = data["bands_up"][band_index]
                band_weights = weights[band_index]
                for index, (x, energy, weight) in enumerate(zip(distances, band, band_weights)):
                    if index % kpoint_stride or weight < 0.15:
                        continue
                    e = energy - fermi
                    if ymin <= e <= ymax:
                        radius = 1.0 + 3.2 * math.sqrt(min(weight, 1.0))
                        parts.append(
                            f'<circle cx="{scale(x, 0, xmax, left, right):.1f}" '
                            f'cy="{scale(e, ymin, ymax, bottom, top):.1f}" r="{radius:.2f}" '
                            f'fill="{color}" fill-opacity="0.34"/>'
                        )
            parts.append(legend_dot(right - 175, top + 24 + target_index * 22, color, key.replace("_", " ")))
    spin_legend_y = top + (24 + 22 * len(projections) if projected else 24)
    if not projected:
        legend_rows = 1 + (1 if data["bands_down"] else 0)
        parts.append(legend_background(right - 188, top + 8, 168, legend_rows))
    parts.append(legend_line(right - 175, spin_legend_y, "up", "spin up"))
    if data["bands_down"]:
        parts.append(legend_line(right - 175, spin_legend_y + 22, "down", "spin down"))
    parts.append(f'<text x="{(left+right)/2}" y="465" text-anchor="middle" class="label">High-symmetry k-path</text>')
    parts.append('<text x="22" y="250" text-anchor="middle" class="label" transform="rotate(-90 22 250)">Energy - E_F (eV)</text>')
    parts.append("</svg>")
    output.write_text("\n".join(parts) + "\n")
    return output


def write_tables(rows: list[dict[str, str]]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with (REPORT_DIR / "Task_C_results_table.csv").open("w", newline="") as handle:
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
    (REPORT_DIR / "Task_C_results_table.md").write_text("\n".join(lines) + "\n")


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
    rows = []
    figures = []
    for case in CASES:
        dos_dir = calc_case(case, "dos")
        bands_dir = calc_case(case, "bands")
        dos = parse_doscar(dos_dir)
        eigen = parse_eigenval(bands_dir)
        fermi = efermi(dos_dir) or efermi(bands_dir)
        # Use the dense uniform DOS mesh for the gap estimate; the line-mode
        # band path is for plotting and may miss extrema away from the path.
        gap, character, gap_type = band_gap(dos_dir)
        for figure in (
            plot_dos(case, dos),
            plot_pdos(case, dos),
            plot_bands(case, eigen, fermi),
            plot_bands(case, eigen, fermi, projected=True),
        ):
            if figure is not None:
                figures.append(figure)
        rows.append(
            {
                "System": case["system"],
                "Case": case["key"],
                "Metallic / Insulating": character,
                "Band gap, eV": "pending" if gap is None else f"{gap:.4f}",
                "Band gap type": gap_type,
                "Dominant orbitals at EF": dominant_orbitals(dos),
                "Magnetic moment, muB": "pending" if total_moment(dos_dir) is None else f"{total_moment(dos_dir):.4f}",
            }
        )
    write_tables(rows)
    print(f"Wrote {REPORT_DIR / 'Task_C_results_table.md'} and {REPORT_DIR / 'Task_C_results_table.csv'}")
    if figures:
        print("Wrote figures: " + ", ".join(str(path.relative_to(ROOT)) for path in figures))
        pdfs = convert_svg_figures(figures)
        if pdfs:
            print("Wrote report PDFs: " + ", ".join(str(path.relative_to(ROOT)) for path in pdfs))
    else:
        print("No figures written yet; run the Task C VASP jobs first.")


if __name__ == "__main__":
    main()
