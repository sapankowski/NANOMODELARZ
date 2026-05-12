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


SYSTEMS = {
    "Ni": {
        "task_dir": ROOT / "Ni" / "A",
        "fixed_kmesh": 16,
        "fixed_encut": 420,
        "encuts": [270, 320, 370, 420, 470, 520],
        "kmeshes": [6, 8, 10, 12, 14, 16, 18],
        "readme_title": "Task A: Ni Convergence Tests",
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
        "fixed_kmesh": 10,
        "fixed_encut": 520,
        "encuts": [400, 450, 500, 520, 550, 600, 650],
        "kmeshes": [4, 6, 8, 10, 12, 14],
        "readme_title": "Task A: NiO Convergence Tests",
        "incar": """\
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
            """,
    },
}


def clean(text: str) -> str:
    return textwrap.dedent(text).strip() + "\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(clean(text))


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

        This folder contains VASP inputs for Task A convergence tests.

        - `INPUT_FILES/`: main reference inputs for this material.
        - `ENCUT/ENCUT_*`: fixed `{cfg["fixed_kmesh"]}x{cfg["fixed_kmesh"]}x{cfg["fixed_kmesh"]}` k-point mesh, varied cutoff energy.
        - `KPOINTS/K_*`: fixed `ENCUT = {cfg["fixed_encut"]} eV`, varied Gamma-centered k-point mesh.

        Run VASP in every generated `ENCUT/*` and `KPOINTS/*` folder.

        After the jobs finish, create the report table from the project root:

        ```bash
        python3 common/A/make_results_table.py
        ```

        The convergence criterion is 1 meV/atom relative to the most demanding tested parameter.
        """,
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
    for system, cfg in SYSTEMS.items():
        prepare_system(system, cfg)
        print(f"Prepared {system} Task A folders in {cfg['task_dir'].relative_to(ROOT)}")


if __name__ == "__main__":
    main()
