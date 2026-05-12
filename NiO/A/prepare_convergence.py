#!/usr/bin/env python3
"""Create Task A convergence input folders for rocksalt NiO."""

from __future__ import annotations

import os
import re
import shutil
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUTS = ROOT / "INPUT_FILES"
SYSTEM = "NiO"
NATOMS = 8
ENCUTS = [400, 450, 500, 520, 550, 600, 650]
KMESHES = [4, 6, 8, 10, 12, 14]
FIXED_KMESH = 10
FIXED_ENCUT = 520


INCAR_TEMPLATE = """\
SYSTEM = rocksalt NiO AFM static convergence

ISTART = 0
ICHARG = 2

PREC   = Accurate
ENCUT  = {encut}
EDIFF  = 1E-7
NELM   = 200
LREAL  = .FALSE.
LASPH  = .TRUE.
LMAXMIX = 4

ISPIN  = 2
# AFM order in the current conventional cell: opposite moments on z=0 and z=1/2 Ni sites.
MAGMOM = 2.0 -2.0 -2.0 2.0 4*0.0

IBRION = -1
NSW    = 0

ISMEAR = 0
SIGMA  = 0.05

LORBIT = 11
LWAVE  = .FALSE.
LCHARG = .FALSE.
"""


ANALYZER = """\
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
        matches = re.findall(r"free\\s+energy\\s+TOTEN\\s+=\\s+(-?\\d+\\.\\d+)", outcar.read_text(errors="ignore"))
        if matches:
            return float(matches[-1])
    oszicar = path / "OSZICAR"
    if oszicar.exists():
        matches = re.findall(r"E0=\\s*(-?\\d+\\.\\d+)", oszicar.read_text(errors="ignore"))
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
    match = re.search(r"^\\s*ENCUT\\s*=\\s*(\\d+)", (path / "INCAR").read_text(errors="ignore"), flags=re.MULTILINE)
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
"""


README = """\
# Task A: NiO Convergence Tests

This folder contains convergence tests for rocksalt NiO in an antiferromagnetic state.

- `ENCUT/ENCUT_*`: fixed `10x10x10` k-point mesh, varied cutoff energy.
- `KPOINTS/K_*`: fixed `ENCUT = 520 eV`, varied Gamma-centered k-point mesh.
- `analyze_convergence.py`: parses completed VASP runs and writes CSV tables and plots.

Run VASP in every generated subfolder. After all jobs finish, run:

```bash
python analyze_convergence.py
```

Use `results/summary_table.csv`, `plots/encut.png`, and `plots/kpoints.png` in the report.
The convergence criterion is 1 meV/atom relative to the most demanding tested parameter.
"""


def clean(text: str) -> str:
    return textwrap.dedent(text).strip() + "\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(clean(text))


def write_kpoints(path: Path, mesh: int) -> None:
    write(
        path,
        f"""\
        {SYSTEM} Gamma-centered {mesh}x{mesh}x{mesh} k-point mesh
        0
        Gamma
        {mesh} {mesh} {mesh}
        0 0 0
        """,
    )


def link_potcar(run_dir: Path) -> None:
    target = run_dir / "POTCAR"
    if target.exists() or target.is_symlink():
        target.unlink()
    target.symlink_to(os.path.relpath(INPUTS / "POTCAR", run_dir))


def create_run(run_dir: Path, encut: int, mesh: int) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write(run_dir / "INCAR", INCAR_TEMPLATE.format(encut=encut))
    write_kpoints(run_dir / "KPOINTS", mesh)
    shutil.copy2(INPUTS / "POSCAR", run_dir / "POSCAR")
    link_potcar(run_dir)


def main() -> None:
    if not (INPUTS / "POSCAR").exists() or not (INPUTS / "POTCAR").exists():
        raise FileNotFoundError("Expected POSCAR and POTCAR in INPUT_FILES")
    write(INPUTS / "INCAR", INCAR_TEMPLATE.format(encut=FIXED_ENCUT))
    write_kpoints(INPUTS / "KPOINTS", FIXED_KMESH)
    write(ROOT / "README.md", README)
    write(ROOT / "analyze_convergence.py", ANALYZER)
    (ROOT / "analyze_convergence.py").chmod(0o755)
    for encut in ENCUTS:
        create_run(ROOT / "ENCUT" / f"ENCUT_{encut}", encut, FIXED_KMESH)
    for mesh in KMESHES:
        create_run(ROOT / "KPOINTS" / f"K_{mesh:02d}x{mesh:02d}x{mesh:02d}", FIXED_ENCUT, mesh)
    print(f"Prepared {SYSTEM} Task A convergence folders in {ROOT}")


if __name__ == "__main__":
    main()
