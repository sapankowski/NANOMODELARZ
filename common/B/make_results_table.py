#!/usr/bin/env python3
"""Summarize Task B magnetic, relaxation, and cohesive-energy results."""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "outputs" / "B"
CALC_DIR = OUTPUT_DIR / "calculations"
REPORT_DIR = OUTPUT_DIR / "reports"
STRUCTURE_DIR = OUTPUT_DIR / "structures"

CASES = [
    {"system": "Ni", "method": "PBE", "ordering": "NM", "path": Path("Ni/B/PBE_NM"), "metal_atoms": 4, "oxygen_atoms": 0},
    {"system": "Ni", "method": "PBE", "ordering": "FM", "path": Path("Ni/B/PBE_FM"), "metal_atoms": 4, "oxygen_atoms": 0},
    {"system": "NiO", "method": "PBE", "ordering": "FM", "path": Path("NiO/B/PBE_FM"), "metal_atoms": 2, "oxygen_atoms": 2},
    {"system": "NiO", "method": "PBE", "ordering": "AFM-II", "path": Path("NiO/B/PBE_AFM"), "metal_atoms": 2, "oxygen_atoms": 2},
    {"system": "NiO", "method": "DFT+U (U=7.2, J=1.0)", "ordering": "FM", "path": Path("NiO/B/DFTU_FM"), "metal_atoms": 2, "oxygen_atoms": 2},
    {"system": "NiO", "method": "DFT+U (U=7.2, J=1.0)", "ordering": "AFM-II", "path": Path("NiO/B/DFTU_AFM"), "metal_atoms": 2, "oxygen_atoms": 2},
]


def run_dir(case: dict, step: str = "static") -> Path:
    return CALC_DIR / case["path"] / step


def atom_dir(name: str) -> Path:
    return CALC_DIR / name


def outcar_text(path: Path) -> str:
    outcar = path / "OUTCAR"
    return outcar.read_text(errors="ignore") if outcar.exists() else ""


def energy(path: Path) -> float | None:
    text = outcar_text(path)
    matches = re.findall(
        r"energy\s+without entropy=\s+(-?\d+\.\d+)\s+energy\(sigma->0\)\s+=\s+(-?\d+\.\d+)",
        text,
    )
    if matches:
        return float(matches[-1][1])
    matches = re.findall(r"free\s+energy\s+TOTEN\s+=\s+(-?\d+\.\d+)", text)
    return float(matches[-1]) if matches else None


def final_forces(path: Path) -> list[tuple[float, float, float]]:
    text = outcar_text(path)
    blocks = re.findall(
        r"POSITION\s+TOTAL-FORCE \(eV/Angst\)\s+-+\n(.*?)(?:\n\s*-{5,}|\n\s*total drift)",
        text,
        flags=re.S,
    )
    if not blocks:
        return []
    forces = []
    for line in blocks[-1].splitlines():
        parts = line.split()
        if len(parts) >= 6:
            try:
                forces.append((float(parts[3]), float(parts[4]), float(parts[5])))
            except ValueError:
                pass
    return forces


def max_force(path: Path) -> float | None:
    forces = final_forces(path)
    if not forces:
        return None
    return max(math.sqrt(fx * fx + fy * fy + fz * fz) for fx, fy, fz in forces)


def stress_pressure(path: Path) -> tuple[str, float | None]:
    text = outcar_text(path)
    matches = re.findall(r"in kB\s+([-\d.Ee+ ]+)", text)
    if not matches:
        return "", None
    values = [float(item) for item in matches[-1].split()[:6]]
    pressure = -(values[0] + values[1] + values[2]) / 3.0
    return " ".join(f"{value:.2f}" for value in values), pressure


def total_moment(path: Path) -> float | None:
    oszicar = path / "OSZICAR"
    if oszicar.exists():
        matches = re.findall(r"mag=\s*(-?\d+\.\d+)", oszicar.read_text(errors="ignore"))
        if matches:
            return float(matches[-1])
    moments = local_moments(path)
    return sum(moments) if moments else None


def local_moments(path: Path) -> list[float]:
    text = outcar_text(path)
    blocks = re.findall(r"magnetization \(x\)\s+.*?-+\n(.*?)\n-+\n", text, flags=re.S)
    if not blocks:
        return []
    moments = []
    for line in blocks[-1].splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].isdigit():
            moments.append(float(parts[4]))
    return moments


def read_poscar(path: Path) -> tuple[list[str], list[list[float]], list[str], list[list[float]]]:
    lines = path.read_text(errors="ignore").splitlines()
    scale = float(lines[1].split()[0])
    lattice = [[float(x) * scale for x in lines[i].split()[:3]] for i in range(2, 5)]
    elements = lines[5].split()
    counts = [int(x) for x in lines[6].split()]
    coord_start = 8 if lines[7].strip().lower().startswith(("d", "c")) else 9
    mode = lines[coord_start - 1].strip().lower()
    species = [element for element, count in zip(elements, counts) for _ in range(count)]
    coords = []
    for line in lines[coord_start : coord_start + sum(counts)]:
        coords.append([float(x) for x in line.split()[:3]])
    if mode.startswith("d"):
        coords = [frac_to_cart(coord, lattice) for coord in coords]
    return elements, lattice, species, coords


def frac_to_cart(frac: list[float], lattice: list[list[float]]) -> list[float]:
    return [
        frac[0] * lattice[0][i] + frac[1] * lattice[1][i] + frac[2] * lattice[2][i]
        for i in range(3)
    ]


def length(vector: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vector))


def angle(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    denom = length(v1) * length(v2)
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / denom)))) if denom else 0.0


def lattice_parameters(poscar: Path) -> dict[str, float | None]:
    if not poscar.exists():
        return {key: None for key in ("a", "b", "c", "alpha", "beta", "gamma")}
    _elements, lattice, _species, _coords = read_poscar(poscar)
    a, b, c = [length(vector) for vector in lattice]
    return {
        "a": a,
        "b": b,
        "c": c,
        "alpha": angle(lattice[1], lattice[2]),
        "beta": angle(lattice[0], lattice[2]),
        "gamma": angle(lattice[0], lattice[1]),
    }


def write_xyz(label: str, poscar: Path) -> str:
    if not poscar.exists():
        return ""
    _elements, _lattice, species, coords = read_poscar(poscar)
    output = STRUCTURE_DIR / f"{label}.xyz"
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [str(len(species)), label]
    for element, coord in zip(species, coords):
        lines.append(f"{element} {coord[0]:.8f} {coord[1]:.8f} {coord[2]:.8f}")
    output.write_text("\n".join(lines) + "\n")
    return str(output.relative_to(ROOT))


def atom_energies() -> tuple[float | None, float | None]:
    return energy(atom_dir("Ni/B/ATOM_Ni")), energy(atom_dir("NiO/B/ATOM_O"))


def cohesive_energy(case: dict, total: float | None, e_ni: float | None, e_o: float | None) -> float | None:
    if total is None or e_ni is None:
        return None
    n_ni = case["metal_atoms"]
    n_o = case["oxygen_atoms"]
    if n_o == 0:
        return (n_ni * e_ni - total) / n_ni
    if e_o is None:
        return None
    return (n_ni * e_ni + n_o * e_o - total) / n_ni


def format_value(value: float | None, digits: int = 4) -> str:
    return "pending" if value is None else f"{value:.{digits}f}"


def build_rows() -> list[dict[str, str]]:
    e_ni_atom, e_o_atom = atom_energies()
    rows = []
    for case in CASES:
        static = run_dir(case)
        total = energy(static)
        lattice = lattice_parameters(static / "POSCAR")
        stress, pressure = stress_pressure(static)
        moments = local_moments(static)
        label = f"{case['system']}_{case['method'].replace(' ', '_').replace('+', 'p')}_{case['ordering']}"
        initial_xyz = write_xyz(label + "_initial", ROOT / case["path"] / "relax" / "POSCAR")
        final_xyz = write_xyz(label + "_relaxed", static / "POSCAR")
        rows.append(
            {
                "System": case["system"],
                "Method": case["method"],
                "Magnetic ordering": case["ordering"],
                "a, A": format_value(lattice["a"]),
                "b, A": format_value(lattice["b"]),
                "c, A": format_value(lattice["c"]),
                "alpha, deg": format_value(lattice["alpha"], 3),
                "beta, deg": format_value(lattice["beta"], 3),
                "gamma, deg": format_value(lattice["gamma"], 3),
                "Max force, eV/A": format_value(max_force(static)),
                "Pressure, kB": format_value(pressure, 3),
                "Stress xx yy zz xy yz zx, kB": stress or "pending",
                "E_total, eV": format_value(total, 6),
                "Total mag, muB": format_value(total_moment(static), 4),
                "Local moments, muB": " ".join(f"{moment:.3f}" for moment in moments) if moments else "pending",
                "Cohesive energy, eV": format_value(cohesive_energy(case, total, e_ni_atom, e_o_atom), 6),
                "Initial XYZ": initial_xyz,
                "Relaxed XYZ": final_xyz,
            }
        )
    return rows


def write_csv(rows: list[dict[str, str]]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with (REPORT_DIR / "Task_B_results_table.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, str]]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    headers = list(rows[0])
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row[header] for header in headers) + " |")
    (REPORT_DIR / "Task_B_results_table.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    rows = build_rows()
    write_csv(rows)
    write_markdown(rows)
    print(f"Wrote {REPORT_DIR / 'Task_B_results_table.md'} and {REPORT_DIR / 'Task_B_results_table.csv'}")


if __name__ == "__main__":
    main()
