#!/usr/bin/env python3
"""Prepare Task E elastic-tensor inputs for Ni and NiO.

Run from the project root:

    python3 common/E/prepare_task_e.py
"""

from __future__ import annotations

import os
import re
import shutil
import textwrap
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "outputs" / "E"


@dataclass
class Poscar:
    comment: str
    scale: str
    lattice: list[list[float]]
    species: list[str]
    counts: list[int]
    coordinate_mode: str
    positions: list[tuple[str, list[str]]]


CASES = [
    {
        "key": "Ni_PBE_FM",
        "system": "Ni",
        "case_dir": ROOT / "Ni" / "E" / "PBE_FM",
        "source_static": ROOT / "outputs" / "B" / "calculations" / "Ni" / "B" / "PBE_FM" / "static",
        "fallback_poscar": ROOT / "Ni" / "B" / "PBE_FM" / "static" / "POSCAR",
        "potcar": ROOT / "Ni" / "POTCAR",
        "encut": 520,
        "kmesh": 24,
        "metallic": True,
        "spin_block": "ISPIN  = 2\nMAGMOM = 4*0.6",
        "ldau_block": "",
        "isym": 2,
        "magnetic_species_split": False,
    },
    {
        "key": "NiO_DFTU_AFM",
        "system": "NiO",
        "case_dir": ROOT / "NiO" / "E" / "DFTU_AFM",
        "source_static": ROOT / "outputs" / "B" / "calculations" / "NiO" / "B" / "DFTU_AFM" / "static",
        "fallback_poscar": ROOT / "NiO" / "B" / "DFTU_AFM" / "static" / "POSCAR",
        "potcar": ROOT / "NiO" / "POTCAR",
        "encut": 700,
        "kmesh": 16,
        "metallic": False,
        "spin_block": "ISPIN  = 2\nMAGMOM = 2.0 -2.0 2*0.0",
        "ldau_block": """\
            LDAU      = .TRUE.
            LDAUTYPE  = 2
            LDAUL     = 2 2 -1
            LDAUU     = 7.2 7.2 0.0
            LDAUJ     = 1.0 1.0 0.0
            LDAUPRINT = 0
            LMAXMIX   = 4

            AMIX      = 0.2
            BMIX      = 0.00001
            AMIX_MAG  = 0.8
            BMIX_MAG  = 0.00001
        """,
        "isym": 0,
        "magnetic_species_split": True,
        "potcar_dataset_indices": [0, 0, 1],
    },
]


def clean(text: str) -> str:
    return textwrap.dedent(text).strip() + "\n"


def write(path: Path, text: str) -> None:
    content = clean(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(errors="ignore") == content:
        return
    path.write_text(content)


def link_potcar(run_dir: Path, potcar: Path) -> None:
    target = run_dir / "POTCAR"
    if target.exists() or target.is_symlink():
        target.unlink()
    target.symlink_to(os.path.relpath(potcar, run_dir))


def split_potcar_datasets(path: Path) -> list[str]:
    text = path.read_text(errors="ignore")
    parts = re.split(r"(End of Dataset\s*\n)", text)
    datasets: list[str] = []
    for index in range(0, len(parts) - 1, 2):
        dataset = parts[index] + parts[index + 1]
        if dataset.strip():
            datasets.append(dataset)
    if not datasets:
        raise ValueError(f"Could not split POTCAR datasets: {path}")
    return datasets


def write_potcar_for_case(run_dir: Path, case: dict) -> None:
    indices = case.get("potcar_dataset_indices")
    if not indices:
        link_potcar(run_dir, case["potcar"])
        return
    datasets = split_potcar_datasets(case["potcar"])
    target = run_dir / "POTCAR"
    if target.exists() or target.is_symlink():
        target.unlink()
    target.write_text("".join(datasets[index] for index in indices))


def poscar_for(case: dict) -> Path:
    contcar = case["source_static"] / "CONTCAR"
    if contcar.exists() and contcar.stat().st_size > 0:
        return contcar
    if case["fallback_poscar"].exists():
        return case["fallback_poscar"]
    raise FileNotFoundError(f"No relaxed POSCAR/CONTCAR found for {case['key']}")


def read_poscar(path: Path) -> Poscar:
    lines = [line.rstrip() for line in path.read_text(errors="ignore").splitlines() if line.strip()]
    if len(lines) < 8:
        raise ValueError(f"POSCAR is too short: {path}")
    species = lines[5].split()
    counts = [int(value) for value in lines[6].split()]
    cursor = 7
    if lines[cursor].lower().startswith("s"):
        cursor += 1
    coordinate_mode = lines[cursor].strip()
    cursor += 1
    positions: list[tuple[str, list[str]]] = []
    for element, count in zip(species, counts):
        for _ in range(count):
            parts = lines[cursor].split()
            positions.append((element, parts[:3]))
            cursor += 1
    return Poscar(
        comment=lines[0].strip(),
        scale=lines[1].strip(),
        lattice=[[float(value) for value in lines[index].split()[:3]] for index in range(2, 5)],
        species=species,
        counts=counts,
        coordinate_mode=coordinate_mode,
        positions=positions,
    )


def split_nio_magnetic_species(poscar: Poscar) -> Poscar:
    if poscar.species != ["Ni", "O"] or poscar.counts != [2, 2]:
        raise ValueError("NiO magnetic split expects POSCAR species Ni O with counts 2 2")
    ni_positions = [coords for element, coords in poscar.positions if element == "Ni"]
    o_positions = [coords for element, coords in poscar.positions if element == "O"]
    return Poscar(
        comment=f"{poscar.comment} Ni-up/Ni-down formal species",
        scale=poscar.scale,
        lattice=poscar.lattice,
        species=["Ni_up", "Ni_down", "O"],
        counts=[1, 1, 2],
        coordinate_mode=poscar.coordinate_mode,
        positions=[
            ("Ni_up", ni_positions[0]),
            ("Ni_down", ni_positions[1]),
            ("O", o_positions[0]),
            ("O", o_positions[1]),
        ],
    )


def write_poscar(path: Path, poscar: Poscar) -> None:
    lines = [poscar.comment, poscar.scale]
    lines.extend("  " + " ".join(f"{value:18.12f}" for value in vector) for vector in poscar.lattice)
    lines.append("  " + " ".join(poscar.species))
    lines.append("  " + " ".join(str(count) for count in poscar.counts))
    lines.append(poscar.coordinate_mode)
    for _element, coords in poscar.positions:
        lines.append("  " + " ".join(coords))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def write_kpoints(path: Path, label: str, mesh: int) -> None:
    write(
        path,
        f"""\
        {label} Gamma-centered {mesh}x{mesh}x{mesh}
        0
        Gamma
        {mesh} {mesh} {mesh}
        0 0 0
        """,
    )


def elastic_incar(case: dict) -> str:
    smear = "ISMEAR = 1\nSIGMA  = 0.10" if case["metallic"] else "ISMEAR = 0\nSIGMA  = 0.05"
    blocks = [
        f"SYSTEM = {case['key']} elastic constants",
        "ISTART = 0\nICHARG = 2",
        f"""\
        PREC   = Accurate
        ENCUT  = {case['encut']}
        EDIFF  = 1E-8
        NELM   = 240
        NWRITE = 1
        LREAL  = .FALSE.
        LASPH  = .TRUE.
        ADDGRID = .TRUE.
        """,
        clean(case["spin_block"]).strip(),
        clean(case["ldau_block"]).strip(),
        f"""\
        IBRION = 6
        ISIF   = 3
        NSW    = 1
        NFREE  = 2
        POTIM  = 0.015
        ISYM   = {case['isym']}
        """,
        smear,
        "LORBIT = 11\nLWAVE  = .FALSE.\nLCHARG = .FALSE.",
    ]
    return "\n\n".join(clean(block).strip() for block in blocks if clean(block).strip()) + "\n"


def prepare_case(case: dict) -> None:
    poscar = read_poscar(poscar_for(case))
    if case["magnetic_species_split"]:
        poscar = split_nio_magnetic_species(poscar)
    if not case["potcar"].exists():
        raise FileNotFoundError(f"Missing POTCAR for {case['key']}: {case['potcar']}")

    run_dir = case["case_dir"] / "elastic"
    run_dir.mkdir(parents=True, exist_ok=True)
    write_poscar(run_dir / "POSCAR", poscar)
    write_potcar_for_case(run_dir, case)
    write_kpoints(run_dir / "KPOINTS", case["key"], case["kmesh"])
    write(run_dir / "INCAR", elastic_incar(case))


def write_readmes() -> None:
    write(
        ROOT / "Ni" / "E" / "README.md",
        """\
        # Task E: Ni Mechanical Properties

        Prepared case:

        - `PBE_FM/elastic`: finite-difference stress-strain elastic tensor for ferromagnetic Ni,
          using the Task B relaxed ground-state structure.

        Shared scripts live in `../../common/E/`. Outputs are written under `../../outputs/E/`.
        """,
    )
    write(
        ROOT / "NiO" / "E" / "README.md",
        """\
        # Task E: NiO Mechanical Properties

        Prepared case:

        - `DFTU_AFM/elastic`: finite-difference stress-strain elastic tensor for AFM-II DFT+U NiO,
          using the Task B relaxed ground-state structure.

        The two Ni atoms are written as formal `Ni_up` and `Ni_down` species with duplicated Ni
        POTCAR data so that opposite magnetic moments remain explicit during the elastic calculation.
        The DFT+U parameters match Tasks A-D: `U(Ni) = 7.2 eV`, `J(Ni) = 1.0 eV`.

        Shared scripts live in `../../common/E/`. Outputs are written under `../../outputs/E/`.
        """,
    )
    write(
        ROOT / "common" / "E" / "README.md",
        """\
        # Common Task E Scripts

        Run these from the project root.

        Prepare elastic-tensor inputs:

        ```bash
        python3 common/E/prepare_task_e.py
        ```

        Submit the VASP workflow:

        ```bash
        sbatch run_task_e.slurm
        ```

        After VASP finishes, summarize elastic constants and derived mechanical properties:

        ```bash
        python3 common/E/analyze_task_e.py
        ```

        Outputs are written under `outputs/E/`.
        """,
    )


def main() -> None:
    for directory in ("calculations", "reports", "slurm"):
        (OUTPUT_DIR / directory).mkdir(parents=True, exist_ok=True)
    for case in CASES:
        prepare_case(case)
    write_readmes()
    print("Prepared Task E inputs in Ni/E and NiO/E")


if __name__ == "__main__":
    main()
