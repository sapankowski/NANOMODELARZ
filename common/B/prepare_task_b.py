#!/usr/bin/env python3
"""Prepare Task B magnetic-state, relaxation, and isolated-atom inputs."""

from __future__ import annotations

import os
import shutil
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "outputs" / "B"

NI_ENCUT = 520
NI_KMESH = 24
NIO_ENCUT = 700
NIO_KMESH = 16


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


def base_relax_incar(system: str, encut: int, metallic: bool, spin_block: str, ldau_block: str = "") -> str:
    smear = "ISMEAR = 1\nSIGMA  = 0.10" if metallic else "ISMEAR = 0\nSIGMA  = 0.05"
    return f"""\
        SYSTEM = {system} relaxation

        ISTART = 0
        ICHARG = 2

        PREC   = Accurate
        ENCUT  = {encut}
        EDIFF  = 1E-7
        EDIFFG = -0.02
        NELM   = 200
        LREAL  = .FALSE.
        LASPH  = .TRUE.
        ADDGRID = .TRUE.

        {spin_block}
        {ldau_block}
        IBRION = 2
        NSW    = 120
        ISIF   = 3
        POTIM  = 0.5

        {smear}

        LORBIT = 11
        LWAVE  = .FALSE.
        LCHARG = .FALSE.
        """


def base_static_incar(system: str, encut: int, metallic: bool, spin_block: str, ldau_block: str = "") -> str:
    smear = "ISMEAR = -5" if not metallic else "ISMEAR = -5"
    return f"""\
        SYSTEM = {system} relaxed static

        ISTART = 0
        ICHARG = 2

        PREC   = Accurate
        ENCUT  = {encut}
        EDIFF  = 1E-7
        NELM   = 200
        LREAL  = .FALSE.
        LASPH  = .TRUE.
        ADDGRID = .TRUE.

        {spin_block}
        {ldau_block}
        IBRION = -1
        NSW    = 0
        ISIF   = 2

        {smear}

        LORBIT = 11
        LWAVE  = .FALSE.
        LCHARG = .FALSE.
        """


def nio_ldau_block() -> str:
    return """\
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
        """


def prepare_relax_static(
    case_dir: Path,
    label: str,
    poscar: Path,
    potcar: Path,
    encut: int,
    kmesh: int,
    metallic: bool,
    spin_block: str,
    ldau_block: str = "",
) -> None:
    for step in ("relax", "static"):
        run_dir = case_dir / step
        run_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(poscar, run_dir / "POSCAR")
        link_potcar(run_dir, potcar)
        write_kpoints(run_dir / "KPOINTS", label, kmesh)

    write(case_dir / "relax" / "INCAR", base_relax_incar(label, encut, metallic, spin_block, ldau_block))
    write(case_dir / "static" / "INCAR", base_static_incar(label, encut, metallic, spin_block, ldau_block))


def write_atom_poscar(path: Path, element: str) -> None:
    write(
        path,
        f"""\
        isolated {element} atom
        1.0
          15.000000 0.000000 0.000000
          0.000000 15.000000 0.000000
          0.000000 0.000000 15.000000
        {element}
        1
        Cartesian
          7.500000 7.500000 7.500000
        """,
    )


def split_o_potcar(combined: Path, output: Path) -> None:
    lines = combined.read_text(errors="ignore").splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.strip().startswith("PAW_PBE O ")), None)
    if start is None:
        raise ValueError(f"Could not find O POTCAR block in {combined}")

    end = next((i + 1 for i in range(start, len(lines)) if "End of Dataset" in lines[i]), None)
    if end is None:
        raise ValueError(f"Could not find end of O POTCAR block in {combined}")
    block = "".join(lines[start:end])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(block)


def prepare_atom(case_dir: Path, element: str, potcar: Path, magmom: float) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    write_atom_poscar(case_dir / "POSCAR", element)
    link_potcar(case_dir, potcar)
    write(
        case_dir / "KPOINTS",
        """\
        isolated atom Gamma point
        0
        Gamma
        1 1 1
        0 0 0
        """,
    )
    write(
        case_dir / "INCAR",
        f"""\
        SYSTEM = isolated {element} atom

        ISTART = 0
        ICHARG = 2
        ISPIN  = 2
        MAGMOM = {magmom}

        PREC   = Accurate
        ENCUT  = {NIO_ENCUT}
        EDIFF  = 1E-7
        NELM   = 200
        LREAL  = .FALSE.
        LASPH  = .TRUE.

        IBRION = -1
        NSW    = 0

        ISMEAR = 0
        SIGMA  = 0.05

        LORBIT = 11
        LWAVE  = .FALSE.
        LCHARG = .FALSE.
        """,
    )


def prepare() -> None:
    ni_poscar = ROOT / "Ni" / "POSCAR"
    ni_potcar = ROOT / "Ni" / "POTCAR"
    nio_poscar = ROOT / "NiO" / "A" / "INPUT_FILES" / "POSCAR"
    nio_potcar = ROOT / "NiO" / "POTCAR"
    if not all(path.exists() for path in (ni_poscar, ni_potcar, nio_poscar, nio_potcar)):
        missing = [str(path.relative_to(ROOT)) for path in (ni_poscar, ni_potcar, nio_poscar, nio_potcar) if not path.exists()]
        raise FileNotFoundError("Missing required input files: " + ", ".join(missing))

    prepare_relax_static(
        ROOT / "Ni" / "B" / "PBE_NM",
        "Ni PBE NM",
        ni_poscar,
        ni_potcar,
        NI_ENCUT,
        NI_KMESH,
        metallic=True,
        spin_block="ISPIN = 1",
    )
    prepare_relax_static(
        ROOT / "Ni" / "B" / "PBE_FM",
        "Ni PBE FM",
        ni_poscar,
        ni_potcar,
        NI_ENCUT,
        NI_KMESH,
        metallic=True,
        spin_block="ISPIN  = 2\nMAGMOM = 4*0.6",
    )

    nio_cases = [
        ("PBE_FM", "NiO PBE FM", "ISPIN  = 2\nMAGMOM = 2*2.0 2*0.0", ""),
        ("PBE_AFM", "NiO PBE AFM-II", "ISPIN  = 2\nMAGMOM = 2.0 -2.0 2*0.0", ""),
        ("DFTU_FM", "NiO DFT+U FM", "ISPIN  = 2\nMAGMOM = 2*2.0 2*0.0", nio_ldau_block()),
        ("DFTU_AFM", "NiO DFT+U AFM-II", "ISPIN  = 2\nMAGMOM = 2.0 -2.0 2*0.0", nio_ldau_block()),
    ]
    for folder, label, spin_block, ldau_block in nio_cases:
        prepare_relax_static(
            ROOT / "NiO" / "B" / folder,
            label,
            nio_poscar,
            nio_potcar,
            NIO_ENCUT,
            NIO_KMESH,
            metallic=False,
            spin_block=spin_block,
            ldau_block=ldau_block,
        )

    o_potcar = ROOT / "NiO" / "B" / "POTCAR_O"
    split_o_potcar(nio_potcar, o_potcar)
    prepare_atom(ROOT / "Ni" / "B" / "ATOM_Ni", "Ni", ni_potcar, 2.0)
    prepare_atom(ROOT / "NiO" / "B" / "ATOM_O", "O", o_potcar, 2.0)

    write(
        ROOT / "Ni" / "B" / "README.md",
        """\
        # Task B: Ni

        Prepared cases:

        - `PBE_NM`: non-magnetic structural relaxation followed by static energy.
        - `PBE_FM`: ferromagnetic structural relaxation followed by static energy.
        - `ATOM_Ni`: isolated Ni atom reference for cohesive energy.

        Shared scripts live in `../../common/B/`. Outputs are written under `../../outputs/B/`.
        """,
    )
    write(
        ROOT / "NiO" / "B" / "README.md",
        """\
        # Task B: NiO

        Prepared cases:

        - `PBE_FM`: ferromagnetic PBE relaxation followed by static energy.
        - `PBE_AFM`: AFM-II PBE relaxation followed by static energy.
        - `DFTU_FM`: ferromagnetic DFT+U relaxation followed by static energy.
        - `DFTU_AFM`: AFM-II DFT+U relaxation followed by static energy.
        - `ATOM_O`: isolated O atom reference for cohesive energy.

        DFT+U uses `LDAUTYPE = 2`, `U(Ni) = 7.2 eV`, `J(Ni) = 1.0 eV`,
        i.e. Dudarev `Ueff = U - J = 6.2 eV`.

        Shared scripts live in `../../common/B/`. Outputs are written under `../../outputs/B/`.
        """,
    )
    (OUTPUT_DIR / "slurm").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "calculations").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "reports").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "structures").mkdir(parents=True, exist_ok=True)


def main() -> None:
    prepare()
    print("Prepared Task B inputs in Ni/B and NiO/B")


if __name__ == "__main__":
    main()
