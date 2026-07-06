#!/usr/bin/env python3
"""Prepare Task A convergence folders for Ni and NiO.

Run from the project root:

    python3 common/A/prepare_convergence.py
"""

from __future__ import annotations

import os
import shutil
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "outputs" / "A"


SYSTEMS = {
    "Ni": {
        "task_dir": ROOT / "Ni" / "A",
        "fixed_kmesh": 24,
        "fixed_encut": 520,
        "encuts": [270, 300, 320, 340, 360, 380, 400, 420, 440, 460, 480, 500, 520, 560, 600],
        "kmeshes": [8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32],
        "readme_title": "Task A: Ni Convergence Tests",
        "description": "This folder contains VASP inputs for Task A convergence tests on fcc Ni in the ferromagnetic state.",
        "incar": """\
            SYSTEM = fcc Ni FM static convergence

            ISTART = 0
            ICHARG = 2

            PREC   = Accurate
            ENCUT  = {encut}
            EDIFF  = 1E-7
            NELM   = 200
            LREAL  = .FALSE.
            LASPH  = .TRUE.

            ISPIN  = 2
            MAGMOM = 4*0.6

            IBRION = -1
            NSW    = 0

            ISMEAR = 1
            SIGMA  = 0.10

            LORBIT = 11
            LWAVE  = .FALSE.
            LCHARG = .FALSE.
            """,
    },
    "NiO": {
        "task_dir": ROOT / "NiO" / "A",
        "fixed_kmesh": 16,
        "fixed_encut": 700,
        "encuts": [400, 425, 450, 475, 500, 520, 550, 575, 600, 625, 650, 675, 700, 725, 750, 775, 800],
        "kmeshes": [4, 6, 8, 10, 12, 14, 16, 18, 20],
        "readme_title": "Task A: NiO Convergence Tests",
        "description": "This folder contains VASP inputs for Task A convergence tests on rocksalt NiO in the AFM-II DFT+U state.",
        "incar": """\
            SYSTEM = rocksalt NiO AFM DFT+U static convergence

            ISTART = 0
            ICHARG = 2

            PREC   = Accurate
            ENCUT  = {encut}
            EDIFF  = 1E-7
            NELM   = 200
            NELMIN = 6
            LREAL  = .FALSE.
            LASPH  = .TRUE.

            ISPIN  = 2
            # AFM-II NiO cell: two Ni sites with opposite moments, followed by two O sites.
            MAGMOM = 2.0 -2.0 2*0.0

            LDAU      = .TRUE.
            LDAUTYPE  = 2
            LDAUL     = 2 -1
            LDAUU     = 7.2 0.0
            LDAUJ     = 1.0 0.0
            LDAUPRINT = 1
            LMAXMIX   = 4

            AMIX      = 0.2
            BMIX      = 0.00001
            AMIX_MAG  = 0.8
            BMIX_MAG  = 0.00001

            IBRION = -1
            NSW    = 0

            ISMEAR = -5

            LORBIT = 11
            LWAVE  = .FALSE.
            LCHARG = .FALSE.
            """,
    },
}


def clean(text: str) -> str:
    return textwrap.dedent(text).strip() + "\n"


def write(path: Path, text: str) -> None:
    content = clean(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(errors="ignore") == content:
        return
    path.write_text(content)


def write_kpoints(path: Path, system: str, mesh: int) -> None:
    write(
        path,
        f"""\
        {system} Gamma-centered {mesh}x{mesh}x{mesh} k-point mesh
        0
        Gamma
        {mesh} {mesh} {mesh}
        0 0 0
        """,
    )


def link_potcar(run_dir: Path, input_dir: Path) -> None:
    target = run_dir / "POTCAR"
    if target.exists() or target.is_symlink():
        target.unlink()
    target.symlink_to(os.path.relpath(input_dir / "POTCAR", run_dir))


def create_run(system: str, cfg: dict, run_dir: Path, encut: int, mesh: int) -> None:
    input_dir = cfg["task_dir"] / "INPUT_FILES"
    run_dir.mkdir(parents=True, exist_ok=True)
    write(run_dir / "INCAR", cfg["incar"].format(encut=encut))
    write_kpoints(run_dir / "KPOINTS", system, mesh)
    shutil.copy2(input_dir / "POSCAR", run_dir / "POSCAR")
    link_potcar(run_dir, input_dir)


def write_readme(system: str, cfg: dict) -> None:
    task_dir = cfg["task_dir"]
    write(
        task_dir / "README.md",
        f"""\
        # {cfg["readme_title"]}

        {cfg["description"]}

        - `INPUT_FILES/`: main reference inputs for this material.
        - `ENCUT/ENCUT_*`: fixed `{cfg["fixed_kmesh"]}x{cfg["fixed_kmesh"]}x{cfg["fixed_kmesh"]}` k-point mesh, varied cutoff energy.
        - `KPOINTS/K_*`: fixed `ENCUT = {cfg["fixed_encut"]} eV`, varied Gamma-centered k-point mesh.
        {extra_notes(system)}
        - Shared scripts live in `../../common/A/`.

        Run VASP in every generated `ENCUT/*` and `KPOINTS/*` folder.

        After the jobs finish, create the report table from the project root:

        ```bash
        python3 common/A/make_results_table.py
        ```

        The convergence criterion is 1 meV/atom relative to the most demanding tested parameter.
        Use `outputs/A/Task_A_results_table.md` or `outputs/A/Task_A_results_table.csv` in the report.
        """,
    )


def extra_notes(system: str) -> str:
    if system != "NiO":
        return ""
    return (
        "- NiO uses spin-polarized antiferromagnetic DFT+U with Dudarev "
        "`U(Ni) = 7.2 eV`, `J(Ni) = 1.0 eV`, so `Ueff = U - J = 6.2 eV`."
    )


def prepare_system(system: str, cfg: dict) -> None:
    input_dir = cfg["task_dir"] / "INPUT_FILES"
    if not (input_dir / "POSCAR").exists() or not (input_dir / "POTCAR").exists():
        raise FileNotFoundError(f"Expected POSCAR and POTCAR in {input_dir}")

    write(input_dir / "INCAR", cfg["incar"].format(encut=cfg["fixed_encut"]))
    write_kpoints(input_dir / "KPOINTS", system, cfg["fixed_kmesh"])
    write_readme(system, cfg)

    for encut in cfg["encuts"]:
        create_run(system, cfg, cfg["task_dir"] / "ENCUT" / f"ENCUT_{encut}", encut, cfg["fixed_kmesh"])

    for mesh in cfg["kmeshes"]:
        create_run(
            system,
            cfg,
            cfg["task_dir"] / "KPOINTS" / f"K_{mesh:02d}x{mesh:02d}x{mesh:02d}",
            cfg["fixed_encut"],
            mesh,
        )


def main() -> None:
    (OUTPUT_DIR / "slurm").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "calculations").mkdir(parents=True, exist_ok=True)
    for system, cfg in SYSTEMS.items():
        prepare_system(system, cfg)
        print(f"Prepared {system} Task A folders in {cfg['task_dir'].relative_to(ROOT)}")


if __name__ == "__main__":
    main()
