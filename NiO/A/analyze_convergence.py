#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SYSTEM = "NiO"
NATOMS = 8
CRITERION_MEV_PER_ATOM = 1.0


def parse_toten(path: Path) -> float | None:
    outcar = path / "OUTCAR"
    if outcar.exists():
        matches = re.findall(r"free\s+energy\s+TOTEN\s+=\s+(-?\d+\.\d+)", outcar.read_text(errors="ignore"))
        if matches:
            return float(matches[-1])
    oszicar = path / "OSZICAR"
    if oszicar.exists():
        matches = re.findall(r"E0=\s*(-?\d+\.\d+)", oszicar.read_text(errors="ignore"))
        if matches:
            return float(matches[-1])
    return None


def parse_ibzkpt(path: Path) -> int | None:
    ibz = path / "IBZKPT"
    if ibz.exists():
        lines = ibz.read_text(errors="ignore").splitlines()
        if len(lines) > 1:
            try:
                return int(lines[1].split()[0])
            except (IndexError, ValueError):
                return None
    return None


def parse_mesh(path: Path) -> str:
    lines = (path / "KPOINTS").read_text(errors="ignore").splitlines()
    return "x".join(lines[3].split()[:3]) if len(lines) >= 4 else ""


def read_encut(path: Path) -> int | None:
    match = re.search(r"^\s*ENCUT\s*=\s*(\d+)", (path / "INCAR").read_text(errors="ignore"), flags=re.MULTILINE)
    return int(match.group(1)) if match else None


def collect_encut() -> list[dict]:
    rows = []
    for run in sorted((ROOT / "ENCUT").glob("ENCUT_*"), key=lambda p: int(p.name.split("_")[-1])):
        energy = parse_toten(run)
        rows.append({
            "system": SYSTEM,
            "test": "ENCUT",
            "encut_eV": int(run.name.split("_")[-1]),
            "kmesh": parse_mesh(run),
            "ibzkpt": parse_ibzkpt(run),
            "energy_eV": energy,
            "energy_per_atom_eV": energy / NATOMS if energy is not None else None,
            "delta_to_reference_meV_per_atom": None,
        })
    return rows


def collect_kpoints() -> list[dict]:
    rows = []
    for run in sorted((ROOT / "KPOINTS").glob("K_*"), key=lambda p: int(p.name.split("_")[-1].split("x")[0])):
        energy = parse_toten(run)
        rows.append({
            "system": SYSTEM,
            "test": "KPOINTS",
            "encut_eV": read_encut(run),
            "kmesh": parse_mesh(run),
            "ibzkpt": parse_ibzkpt(run),
            "energy_eV": energy,
            "energy_per_atom_eV": energy / NATOMS if energy is not None else None,
            "delta_to_reference_meV_per_atom": None,
        })
    return rows


def choose(rows: list[dict]) -> dict | None:
    available = [row for row in rows if row["energy_per_atom_eV"] is not None]
    if not available:
        return None
    reference = available[-1]["energy_per_atom_eV"]
    for index, row in enumerate(available):
        for candidate in available[index:]:
            candidate["delta_to_reference_meV_per_atom"] = abs(candidate["energy_per_atom_eV"] - reference) * 1000.0
        if max(candidate["delta_to_reference_meV_per_atom"] for candidate in available[index:]) <= CRITERION_MEV_PER_ATOM:
            return row
    return available[-1]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot(rows: list[dict], x_key: str, xlabel: str, filename: str) -> None:
    available = [row for row in rows if row["energy_per_atom_eV"] is not None]
    if not available:
        return
    import matplotlib.pyplot as plt

    x = [row[x_key] if row[x_key] is not None else index + 1 for index, row in enumerate(available)]
    y = [row["energy_per_atom_eV"] for row in available]
    plt.figure(figsize=(6, 4))
    plt.plot(x, y, marker="o")
    plt.xlabel(xlabel)
    plt.ylabel("Total energy (eV/atom)")
    plt.title(f"{SYSTEM} convergence")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    out = ROOT / "plots" / filename
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=300)
    plt.close()


def main() -> None:
    encut_rows = collect_encut()
    kpoint_rows = collect_kpoints()
    encut_choice = choose(encut_rows)
    kpoint_choice = choose(kpoint_rows)
    summary = [{
        "system": SYSTEM,
        "encut_eV": encut_choice["encut_eV"] if encut_choice else "",
        "kpoint_mesh": kpoint_choice["kmesh"] if kpoint_choice else "",
        "energy_convergence_meV_per_atom": max(
            [value for value in [
                encut_choice["delta_to_reference_meV_per_atom"] if encut_choice else None,
                kpoint_choice["delta_to_reference_meV_per_atom"] if kpoint_choice else None,
            ] if value is not None],
            default="",
        ),
    }]
    write_csv(ROOT / "results" / "encut.csv", encut_rows)
    write_csv(ROOT / "results" / "kpoints.csv", kpoint_rows)
    write_csv(ROOT / "results" / "summary_table.csv", summary)
    plot(encut_rows, "encut_eV", "ENCUT (eV)", "encut.png")
    plot(kpoint_rows, "ibzkpt", "Number of IBZKPT points", "kpoints.png")
    print("Wrote tables to results/ and available plots to plots/.")


if __name__ == "__main__":
    main()
