#!/usr/bin/env python3
"""Prepare Task C electronic-structure inputs.

Run from the project root:

    python3 common/C/prepare_task_c.py
"""

from __future__ import annotations

import os
import shutil
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "outputs" / "C"


CASES = [
    {
        "key": "Ni_PBE_FM",
        "system": "Ni",
        "case_dir": ROOT / "Ni" / "C" / "PBE_FM",
        "source_static": ROOT / "outputs" / "B" / "calculations" / "Ni" / "B" / "PBE_FM" / "static",
        "fallback_poscar": ROOT / "Ni" / "B" / "PBE_FM" / "static" / "POSCAR",
        "potcar": ROOT / "Ni" / "POTCAR",
        "encut": 520,
        "scf_mesh": 24,
        "dos_mesh": 32,
        "metallic": True,
        "spin_block": "ISPIN  = 2\nMAGMOM = 4*0.6",
        "ldau_block": "",
        "band_path": [
            ("G", (0.0, 0.0, 0.0), "X", (0.0, 0.5, 0.5)),
            ("X", (0.0, 0.5, 0.5), "W", (0.25, 0.5, 0.75)),
            ("W", (0.25, 0.5, 0.75), "K", (0.375, 0.375, 0.75)),
            ("K", (0.375, 0.375, 0.75), "G", (0.0, 0.0, 0.0)),
            ("G", (0.0, 0.0, 0.0), "L", (0.5, 0.5, 0.5)),
            ("L", (0.5, 0.5, 0.5), "U", (0.625, 0.25, 0.625)),
            ("U", (0.625, 0.25, 0.625), "W", (0.25, 0.5, 0.75)),
            ("W", (0.25, 0.5, 0.75), "L", (0.5, 0.5, 0.5)),
        ],
    },
    {
        "key": "NiO_PBE_AFM",
        "system": "NiO",
        "case_dir": ROOT / "NiO" / "C" / "PBE_AFM",
        "source_static": ROOT / "outputs" / "B" / "calculations" / "NiO" / "B" / "PBE_AFM" / "static",
        "fallback_poscar": ROOT / "NiO" / "B" / "PBE_AFM" / "static" / "POSCAR",
        "potcar": ROOT / "NiO" / "POTCAR",
        "encut": 700,
        "scf_mesh": 16,
        "dos_mesh": 20,
        "metallic": False,
        "spin_block": "ISPIN  = 2\nMAGMOM = 2.0 -2.0 2*0.0",
        "ldau_block": "",
        "band_path": [
            ("G", (0.0, 0.0, 0.0), "L", (0.5, 0.0, 0.0)),
            ("L", (0.5, 0.0, 0.0), "B", (0.5, 0.0, 0.5)),
            ("B", (0.5, 0.0, 0.5), "G", (0.0, 0.0, 0.0)),
            ("G", (0.0, 0.0, 0.0), "Z", (0.5, 0.5, 0.5)),
            ("Z", (0.5, 0.5, 0.5), "F", (0.5, 0.5, 0.0)),
            ("F", (0.5, 0.5, 0.0), "G", (0.0, 0.0, 0.0)),
        ],
    },
    {
        "key": "NiO_DFTU_AFM",
        "system": "NiO",
        "case_dir": ROOT / "NiO" / "C" / "DFTU_AFM",
        "source_static": ROOT / "outputs" / "B" / "calculations" / "NiO" / "B" / "DFTU_AFM" / "static",
        "fallback_poscar": ROOT / "NiO" / "B" / "DFTU_AFM" / "static" / "POSCAR",
        "potcar": ROOT / "NiO" / "POTCAR",
        "encut": 700,
        "scf_mesh": 16,
        "dos_mesh": 20,
        "metallic": False,
        "spin_block": "ISPIN  = 2\nMAGMOM = 2.0 -2.0 2*0.0",
        "ldau_block": """\
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
        """,
        "band_path": [
            ("G", (0.0, 0.0, 0.0), "L", (0.5, 0.0, 0.0)),
            ("L", (0.5, 0.0, 0.0), "B", (0.5, 0.0, 0.5)),
            ("B", (0.5, 0.0, 0.5), "G", (0.0, 0.0, 0.0)),
            ("G", (0.0, 0.0, 0.0), "Z", (0.5, 0.5, 0.5)),
            ("Z", (0.5, 0.5, 0.5), "F", (0.5, 0.5, 0.0)),
            ("F", (0.5, 0.5, 0.0), "G", (0.0, 0.0, 0.0)),
        ],
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


def poscar_for(case: dict) -> Path:
    contcar = case["source_static"] / "CONTCAR"
    if contcar.exists() and contcar.stat().st_size > 0:
        return contcar
    if case["fallback_poscar"].exists():
        return case["fallback_poscar"]
    raise FileNotFoundError(f"No relaxed POSCAR/CONTCAR found for {case['key']}")


def write_mesh_kpoints(path: Path, label: str, mesh: int) -> None:
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


def fmt_point(point: tuple[float, float, float], label: str) -> str:
    return f"  {point[0]:.8f} {point[1]:.8f} {point[2]:.8f} ! {label}"


def write_band_kpoints(path: Path, label: str, segments: list[tuple]) -> None:
    lines = [
        f"{label} high-symmetry path",
        "40",
        "Line-mode",
        "Reciprocal",
    ]
    for start_label, start, end_label, end in segments:
        lines.append(fmt_point(start, start_label))
        lines.append(fmt_point(end, end_label))
        lines.append("")
    write(path, "\n".join(lines))


def common_incar(case: dict, label: str, icharg: int, lcharg: bool) -> str:
    smear = "ISMEAR = 1\nSIGMA  = 0.10" if case["metallic"] else "ISMEAR = -5"
    spin_block = clean(case["spin_block"]).strip()
    ldau_block = clean(case["ldau_block"]).strip()
    lcharg_value = ".TRUE." if lcharg else ".FALSE."
    blocks = [
        f"SYSTEM = {label}",
        f"ISTART = 0\nICHARG = {icharg}\nPREC   = Accurate\n"
        f"ENCUT  = {case['encut']}\n"
        "EDIFF  = 1E-7\nNELM   = 200\nLREAL  = .FALSE.\nLASPH  = .TRUE.\nADDGRID = .TRUE.",
        spin_block,
        ldau_block,
        "IBRION = -1\nNSW    = 0\nISIF   = 2",
        smear,
        "LORBIT = 11\nNEDOS  = 3001",
        f"LWAVE  = .FALSE.\nLCHARG = {lcharg_value}",
    ]
    return "\n\n".join(block for block in blocks if block) + "\n"


def prepare_case(case: dict) -> None:
    poscar = poscar_for(case)
    if not case["potcar"].exists():
        raise FileNotFoundError(f"Missing POTCAR for {case['key']}: {case['potcar']}")

    for step in ("scf", "dos", "bands"):
        run_dir = case["case_dir"] / step
        run_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(poscar, run_dir / "POSCAR")
        link_potcar(run_dir, case["potcar"])

    write_mesh_kpoints(case["case_dir"] / "scf" / "KPOINTS", case["key"], case["scf_mesh"])
    write_mesh_kpoints(case["case_dir"] / "dos" / "KPOINTS", case["key"], case["dos_mesh"])
    write_band_kpoints(case["case_dir"] / "bands" / "KPOINTS", case["key"], case["band_path"])

    write(case["case_dir"] / "scf" / "INCAR", common_incar(case, f"{case['key']} SCF charge", 2, True))
    write(
        case["case_dir"] / "dos" / "INCAR",
        common_incar(case, f"{case['key']} DOS and PDOS", 11, False),
    )
    write(
        case["case_dir"] / "bands" / "INCAR",
        common_incar(case, f"{case['key']} projected bands", 11, False),
    )


def write_readmes() -> None:
    write(
        ROOT / "Ni" / "C" / "README.md",
        """\
        # Task C: Ni Electronic Structure

        Prepared case:

        - `PBE_FM`: ferromagnetic Ni electronic structure from the Task B relaxed ground-state structure.

        Each case contains `scf`, `dos`, and `bands` subfolders. Shared scripts live in `../../common/C/`.
        Outputs are written under `../../outputs/C/`.
        """,
    )
    write(
        ROOT / "NiO" / "C" / "README.md",
        """\
        # Task C: NiO Electronic Structure

        Prepared cases:

        - `PBE_AFM`: AFM-II PBE electronic structure from the Task B relaxed ground-state structure.
        - `DFTU_AFM`: AFM-II DFT+U electronic structure from the Task B relaxed ground-state structure.

        The DFT+U case uses `LDAUTYPE = 2`, `U(Ni) = 7.2 eV`, and `J(Ni) = 1.0 eV`.
        Each case contains `scf`, `dos`, and `bands` subfolders. Shared scripts live in `../../common/C/`.
        Outputs are written under `../../outputs/C/`.
        """,
    )
    write(
        ROOT / "common" / "C" / "README.md",
        """\
        # Common Task C Scripts

        Run these from the project root.

        Prepare electronic-structure inputs:

        ```bash
        python3 common/C/prepare_task_c.py
        ```

        Submit the VASP workflow:

        ```bash
        sbatch run_task_c.slurm
        ```

        After VASP finishes, summarize results and create SVG plots:

        ```bash
        python3 common/C/analyze_task_c.py
        ```

        Outputs are written under `outputs/C/`.
        """,
    )


def main() -> None:
    for directory in ("calculations", "reports", "figures", "slurm"):
        (OUTPUT_DIR / directory).mkdir(parents=True, exist_ok=True)
    for case in CASES:
        prepare_case(case)
    write_readmes()
    print("Prepared Task C inputs in Ni/C and NiO/C")


if __name__ == "__main__":
    main()
