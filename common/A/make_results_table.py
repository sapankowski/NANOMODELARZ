#!/usr/bin/env python3
"""Create the Task A convergence summary table for Ni and NiO.

Run from the project root after the VASP jobs finish:

    python3 common/A/make_results_table.py
"""

from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SYSTEMS = {
    "Ni": {"path": ROOT / "Ni" / "A", "atoms": 4},
    "NiO": {"path": ROOT / "NiO" / "A", "atoms": 8},
}
CRITERION_MEV_PER_ATOM = 1.0


def energy(run_dir: Path) -> float | None:
    outcar = run_dir / "OUTCAR"
    if outcar.exists():
        matches = re.findall(
            r"free\s+energy\s+TOTEN\s+=\s+(-?\d+\.\d+)",
            outcar.read_text(errors="ignore"),
        )
        if matches:
            return float(matches[-1])

    oszicar = run_dir / "OSZICAR"
    if oszicar.exists():
        matches = re.findall(r"E0=\s*(-?\d+\.\d+)", oszicar.read_text(errors="ignore"))
        if matches:
            return float(matches[-1])

    return None


def kmesh(run_dir: Path) -> str:
    kpoints = run_dir / "KPOINTS"
    if not kpoints.exists():
        return ""
    lines = kpoints.read_text(errors="ignore").splitlines()
    return "x".join(lines[3].split()[:3]) if len(lines) >= 4 else ""


def collect_encut(system_path: Path, atoms: int) -> list[dict]:
    rows = []
    for run in sorted((system_path / "ENCUT").glob("ENCUT_*"), key=lambda p: int(p.name.split("_")[-1])):
        total_energy = energy(run)
        encut = int(run.name.split("_")[-1])
        rows.append(
            {
                "label": str(encut),
                "energy_per_atom": total_energy / atoms if total_energy is not None else None,
            }
        )
    return rows


def collect_kpoints(system_path: Path, atoms: int) -> list[dict]:
    rows = []
    for run in sorted((system_path / "KPOINTS").glob("K_*"), key=lambda p: int(p.name.split("_")[-1].split("x")[0])):
        total_energy = energy(run)
        rows.append(
            {
                "label": kmesh(run),
                "energy_per_atom": total_energy / atoms if total_energy is not None else None,
            }
        )
    return rows


def choose_converged(rows: list[dict]) -> tuple[str, float | None]:
    completed = [row for row in rows if row["energy_per_atom"] is not None]
    if not completed:
        return "pending", None

    reference = completed[-1]["energy_per_atom"]
    for index, row in enumerate(completed):
        remaining_deltas = [
            abs(candidate["energy_per_atom"] - reference) * 1000.0
            for candidate in completed[index:]
        ]
        if max(remaining_deltas) <= CRITERION_MEV_PER_ATOM:
            return row["label"], max(remaining_deltas)

    return completed[-1]["label"], 0.0


def build_table() -> list[dict]:
    table = []
    for system, cfg in SYSTEMS.items():
        encut, encut_delta = choose_converged(collect_encut(cfg["path"], cfg["atoms"]))
        kpoints, kpoint_delta = choose_converged(collect_kpoints(cfg["path"], cfg["atoms"]))
        deltas = [value for value in (encut_delta, kpoint_delta) if value is not None]
        convergence = f"{max(deltas):.3f} meV/atom" if deltas else "pending VASP outputs"
        table.append(
            {
                "System": system,
                "ENCUT, eV": encut,
                "k-point mesh": kpoints,
                "Energy convergence": convergence,
            }
        )
    return table


def write_csv(rows: list[dict]) -> None:
    with (ROOT / "Task_A_results_table.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict]) -> None:
    headers = list(rows[0])
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row[header]) for header in headers) + " |")
    (ROOT / "Task_A_results_table.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    rows = build_table()
    write_csv(rows)
    write_markdown(rows)
    print("Wrote Task_A_results_table.md and Task_A_results_table.csv")


if __name__ == "__main__":
    main()
