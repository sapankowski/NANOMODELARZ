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
OUTPUT_DIR = ROOT / "outputs" / "A"
SYSTEMS = {
    "Ni": {
        "path": ROOT / "Ni" / "A",
        "atoms": 4,
        "encuts": [270, 300, 320, 340, 360, 380, 400, 420, 440, 460, 480, 500, 520, 560, 600],
        "kmeshes": [8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32],
    },
    "NiO": {
        "path": ROOT / "NiO" / "A",
        "atoms": 4,
        "encuts": [400, 425, 450, 475, 500, 520, 550, 575, 600, 625, 650, 675, 700, 725, 750, 775, 800],
        "kmeshes": [4, 6, 8, 10, 12, 14, 16, 18, 20],
    },
}
CRITERION_MEV_PER_ATOM = 1.0


def output_run_dir(input_run_dir: Path) -> Path:
    return OUTPUT_DIR / "calculations" / input_run_dir.relative_to(ROOT)


def energy(run_dir: Path) -> float | None:
    output_dir = output_run_dir(run_dir)
    input_files = [output_dir / name for name in ("INCAR", "KPOINTS", "POSCAR", "POTCAR")]

    outcar = output_dir / "OUTCAR"
    if outcar.exists() and is_current(outcar, input_files):
        matches = re.findall(
            r"energy\s+without entropy=\s+(-?\d+\.\d+)\s+energy\(sigma->0\)\s+=\s+(-?\d+\.\d+)",
            outcar.read_text(errors="ignore"),
        )
        if matches:
            return float(matches[-1][1])

        matches = re.findall(
            r"free\s+energy\s+TOTEN\s+=\s+(-?\d+\.\d+)",
            outcar.read_text(errors="ignore"),
        )
        if matches:
            return float(matches[-1])

    oszicar = output_dir / "OSZICAR"
    if oszicar.exists() and is_current(oszicar, input_files):
        matches = re.findall(r"E0=\s*(-?\d+\.\d+)", oszicar.read_text(errors="ignore"))
        if matches:
            return float(matches[-1])

    return None


def is_current(output: Path, input_files: list[Path]) -> bool:
    """Ignore stale VASP outputs from older input files."""
    existing_inputs = [path for path in input_files if path.exists()]
    if not existing_inputs:
        return True
    newest_input = max(path.stat().st_mtime for path in existing_inputs)
    return output.stat().st_mtime >= newest_input


def kmesh(run_dir: Path) -> str:
    output_kpoints = output_run_dir(run_dir) / "KPOINTS"
    kpoints = output_kpoints if output_kpoints.exists() else run_dir / "KPOINTS"
    if not kpoints.exists():
        return ""
    lines = kpoints.read_text(errors="ignore").splitlines()
    return "x".join(lines[3].split()[:3]) if len(lines) >= 4 else ""


def collect_encut(cfg: dict) -> list[dict]:
    rows = []
    for encut in cfg["encuts"]:
        run = cfg["path"] / "ENCUT" / f"ENCUT_{encut}"
        total_energy = energy(run)
        rows.append(
            {
                "label": str(encut),
                "energy_per_atom": total_energy / cfg["atoms"] if total_energy is not None else None,
            }
        )
    return rows


def collect_kpoints(cfg: dict) -> list[dict]:
    rows = []
    for mesh in cfg["kmeshes"]:
        run = cfg["path"] / "KPOINTS" / f"K_{mesh:02d}x{mesh:02d}x{mesh:02d}"
        total_energy = energy(run)
        rows.append(
            {
                "label": kmesh(run),
                "energy_per_atom": total_energy / cfg["atoms"] if total_energy is not None else None,
            }
        )
    return rows


def choose_converged(rows: list[dict]) -> tuple[str, float | None]:
    completed = [row for row in rows if row["energy_per_atom"] is not None]
    if not completed:
        return "pending", None
    if rows[-1]["energy_per_atom"] is None:
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
        encut, encut_delta = choose_converged(collect_encut(cfg))
        kpoints, kpoint_delta = choose_converged(collect_kpoints(cfg))
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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUTPUT_DIR / "Task_A_results_table.csv").open("w", newline="") as handle:
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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "Task_A_results_table.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    rows = build_table()
    write_csv(rows)
    write_markdown(rows)
    print(f"Wrote {OUTPUT_DIR / 'Task_A_results_table.md'} and {OUTPUT_DIR / 'Task_A_results_table.csv'}")


if __name__ == "__main__":
    main()
