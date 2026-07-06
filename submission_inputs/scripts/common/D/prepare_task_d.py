#!/usr/bin/env python3
"""Prepare Task D phonon inputs for Ni and NiO.

Run from the project root:

    python3 common/D/prepare_task_d.py
"""

from __future__ import annotations

import os
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "outputs" / "D"


@dataclass
class Poscar:
    comment: str
    scale: str
    lattice: list[list[float]]
    species: list[str]
    counts: list[int]
    coordinate_mode: str
    positions: list[tuple[str, list[float]]]


CASES = [
    {
        "key": "Ni_PBE_FM",
        "system": "Ni",
        "case_dir": ROOT / "Ni" / "D" / "PBE_FM",
        "source_static": ROOT / "outputs" / "B" / "calculations" / "Ni" / "B" / "PBE_FM" / "static",
        "fallback_poscar": ROOT / "Ni" / "B" / "PBE_FM" / "static" / "POSCAR",
        "potcar": ROOT / "Ni" / "POTCAR",
        "encut": 520,
        "supercell": (2, 2, 2),
        "kmesh": 8,
        "qmesh": 32,
        "metallic": True,
        "use_fcc_primitive": True,
        "force_ibrion": 5,
        "force_isym": 0,
        "spin_block": "ISPIN  = 2\nMAGMOM = 8*0.6",
        "ldau_block": "",
        "polar": False,
        "path": [
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
        "key": "NiO_DFTU_AFM",
        "system": "NiO",
        "case_dir": ROOT / "NiO" / "D" / "DFTU_AFM",
        "source_static": ROOT / "outputs" / "B" / "calculations" / "NiO" / "B" / "DFTU_AFM" / "static",
        "fallback_poscar": ROOT / "NiO" / "B" / "DFTU_AFM" / "static" / "POSCAR",
        "potcar": ROOT / "NiO" / "POTCAR",
        "encut": 700,
        "supercell": (1, 1, 1),
        "kmesh": 16,
        "qmesh": 32,
        "metallic": False,
        "split_nio_magnetic_species": True,
        "potcar_dataset_indices": [0, 0, 1],
        "preconverge_force_constants": True,
        "force_ibrion": 6,
        "force_isym": 2,
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
        "polar": True,
        "primitive_kmesh": 16,
        "primitive_spin_block": "ISPIN  = 2\nMAGMOM = 2.0 -2.0 2*0.0",
        "path": [
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
    content = "".join(datasets[index] for index in indices)
    target = run_dir / "POTCAR"
    if target.is_symlink() or target.exists():
        target.unlink()
    target.write_text(content)


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
    positions: list[tuple[str, list[float]]] = []
    for element, count in zip(species, counts):
        for _ in range(count):
            parts = lines[cursor].split()
            positions.append((element, [float(value) for value in parts[:3]]))
            cursor += 1
    if not coordinate_mode.lower().startswith("d"):
        raise ValueError(f"Only direct-coordinate POSCARs are supported for supercell generation: {path}")
    return Poscar(
        comment=lines[0].strip(),
        scale=lines[1].strip(),
        lattice=[[float(value) for value in lines[index].split()[:3]] for index in range(2, 5)],
        species=species,
        counts=counts,
        coordinate_mode="Direct",
        positions=positions,
    )


def make_supercell(poscar: Poscar, repeat: tuple[int, int, int]) -> Poscar:
    nx, ny, nz = repeat
    factor = nx * ny * nz
    lattice = [
        [component * nx for component in poscar.lattice[0]],
        [component * ny for component in poscar.lattice[1]],
        [component * nz for component in poscar.lattice[2]],
    ]
    positions: list[tuple[str, list[float]]] = []
    for element in poscar.species:
        element_positions = [coords for atom_element, coords in poscar.positions if atom_element == element]
        for coords in element_positions:
            for ix in range(nx):
                for iy in range(ny):
                    for iz in range(nz):
                        positions.append(
                            (
                                element,
                                [
                                    (coords[0] + ix) / nx,
                                    (coords[1] + iy) / ny,
                                    (coords[2] + iz) / nz,
                                ],
                            )
                        )
    return Poscar(
        comment=f"{poscar.comment} {nx}x{ny}x{nz} phonon supercell",
        scale=poscar.scale,
        lattice=lattice,
        species=poscar.species,
        counts=[count * factor for count in poscar.counts],
        coordinate_mode="Direct",
        positions=positions,
    )


def make_fcc_primitive(poscar: Poscar) -> Poscar:
    if len(poscar.species) != 1:
        raise ValueError("FCC primitive conversion expects a single-species POSCAR")
    a1, a2, a3 = poscar.lattice
    lattice = [
        [(a2[index] + a3[index]) * 0.5 for index in range(3)],
        [(a1[index] + a3[index]) * 0.5 for index in range(3)],
        [(a1[index] + a2[index]) * 0.5 for index in range(3)],
    ]
    return Poscar(
        comment=f"{poscar.comment} primitive fcc cell",
        scale=poscar.scale,
        lattice=lattice,
        species=poscar.species,
        counts=[1],
        coordinate_mode="Direct",
        positions=[(poscar.species[0], [0.0, 0.0, 0.0])],
    )


def split_nio_magnetic_species(poscar: Poscar) -> Poscar:
    if poscar.species != ["Ni", "O"] or poscar.counts != [2, 2]:
        raise ValueError("NiO magnetic split expects species Ni O with counts 2 2")
    ni_positions = [coords for element, coords in poscar.positions if element == "Ni"]
    o_positions = [coords for element, coords in poscar.positions if element == "O"]
    return Poscar(
        comment=f"{poscar.comment} Ni-up/Ni-down formal species",
        scale=poscar.scale,
        lattice=poscar.lattice,
        species=["Ni_up", "Ni_down", "O"],
        counts=[1, 1, 2],
        coordinate_mode="Direct",
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
        lines.append("  " + " ".join(f"{value:18.12f}" for value in coords))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


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


def write_line_qpoints(path: Path, label: str, segments: list[tuple], points_per_segment: int = 40) -> None:
    lines = [
        f"{label} phonon path",
        str(points_per_segment),
        "Line-mode",
        "Reciprocal",
    ]
    for start_label, start, end_label, end in segments:
        lines.append(fmt_point(start, start_label))
        lines.append(fmt_point(end, end_label))
        lines.append("")
    write(path, "\n".join(lines))


def write_mesh_qpoints(path: Path, label: str, mesh: int) -> None:
    write(
        path,
        f"""\
        {label} phonon DOS q-point mesh
        0
        Gamma
        {mesh} {mesh} {mesh}
        0 0 0
        """,
    )


def electronic_blocks(case: dict, primitive: bool = False, write_restart: bool = False) -> list[str]:
    spin_block = case.get("primitive_spin_block", case["spin_block"]) if primitive else case["spin_block"]
    smear = "ISMEAR = 1\nSIGMA  = 0.10" if case["metallic"] else "ISMEAR = 0\nSIGMA  = 0.05"
    restart_block = "LWAVE  = .TRUE.\nLCHARG = .TRUE." if write_restart else "LWAVE  = .FALSE.\nLCHARG = .FALSE."
    return [
        f"PREC   = Accurate\nENCUT  = {case['encut']}\nEDIFF  = 1E-8\nNELM   = 240\nLREAL  = .FALSE.\nLASPH  = .TRUE.\nADDGRID = .FALSE.",
        clean(spin_block).strip(),
        clean(case["ldau_block"]).strip(),
        smear,
        restart_block,
    ]


def preconverge_incar(case: dict) -> str:
    blocks = [
        f"SYSTEM = {case['key']} phonon preconvergence",
        "ISTART = 0\nICHARG = 2",
        *electronic_blocks(case, write_restart=True),
        "IBRION = -1\nNSW    = 0\nISIF   = 2\nISYM   = 2",
    ]
    return "\n\n".join(block for block in blocks if block) + "\n"


def force_constants_incar(case: dict) -> str:
    start_block = "ISTART = 1\nICHARG = 1" if case.get("preconverge_force_constants") else "ISTART = 0\nICHARG = 2"
    ionic_block = (
        f"IBRION = {case.get('force_ibrion', 5)}\n"
        "NFREE  = 2\n"
        "POTIM  = 0.015\n"
        "NSW    = 1\n"
        "ISIF   = 2\n"
        f"ISYM   = {case.get('force_isym', 0)}"
    )
    blocks = [
        f"SYSTEM = {case['key']} finite-difference phonons",
        start_block,
        *electronic_blocks(case),
        ionic_block,
    ]
    return "\n\n".join(block for block in blocks if block) + "\n"


def postprocess_incar(case: dict, task: str) -> str:
    phonon_block = (
        "LPHON_READ_FORCE_CONSTANTS = .TRUE.\n"
        "LPHON_DISPERSION = .TRUE.\n"
        "PHON_NWRITE = 2"
        if task == "dispersion"
        else "LPHON_READ_FORCE_CONSTANTS = .TRUE.\nPHON_DOS = 2\nPHON_NEDOS = 1200\nPHON_SIGMA = 0.10"
    )
    blocks = [
        f"SYSTEM = {case['key']} phonon {task}",
        "ISTART = 0\nICHARG = 2",
        *electronic_blocks(case),
        "ISYM   = 0",
        phonon_block,
    ]
    return "\n\n".join(block for block in blocks if block) + "\n"


def dielectric_incar(case: dict) -> str:
    blocks = [
        f"SYSTEM = {case['key']} dielectric and Born charges",
        "ISTART = 0\nICHARG = 2",
        *electronic_blocks(case, primitive=True),
        "IBRION = -1\nNSW    = 0\nISIF   = 2",
        "LEPSILON = .TRUE.",
    ]
    return "\n\n".join(block for block in blocks if block) + "\n"


def prepare_case(case: dict) -> None:
    primitive_poscar = read_poscar(poscar_for(case))
    if case.get("use_fcc_primitive"):
        primitive_poscar = make_fcc_primitive(primitive_poscar)
    if case.get("split_nio_magnetic_species"):
        primitive_poscar = split_nio_magnetic_species(primitive_poscar)
    supercell_poscar = make_supercell(primitive_poscar, case["supercell"])
    if not case["potcar"].exists():
        raise FileNotFoundError(f"Missing POTCAR for {case['key']}: {case['potcar']}")

    if case["polar"]:
        run_dir = case["case_dir"] / "dielectric"
        run_dir.mkdir(parents=True, exist_ok=True)
        write_poscar(run_dir / "POSCAR", primitive_poscar)
        write_potcar_for_case(run_dir, case)
        write_mesh_kpoints(run_dir / "KPOINTS", case["key"], case["primitive_kmesh"])
        write(run_dir / "INCAR", dielectric_incar(case))

    steps = ["force_constants", "dispersion", "dos"]
    if case.get("preconverge_force_constants"):
        steps.insert(0, "preconverge")

    for step in steps:
        run_dir = case["case_dir"] / step
        run_dir.mkdir(parents=True, exist_ok=True)
        write_poscar(run_dir / "POSCAR", supercell_poscar)
        write_potcar_for_case(run_dir, case)
        write_mesh_kpoints(run_dir / "KPOINTS", case["key"], case["kmesh"])

    if case.get("preconverge_force_constants"):
        write(case["case_dir"] / "preconverge" / "INCAR", preconverge_incar(case))
    write(case["case_dir"] / "force_constants" / "INCAR", force_constants_incar(case))
    write(case["case_dir"] / "dispersion" / "INCAR", postprocess_incar(case, "dispersion"))
    write(case["case_dir"] / "dos" / "INCAR", postprocess_incar(case, "dos"))
    write_line_qpoints(case["case_dir"] / "dispersion" / "QPOINTS", case["key"], case["path"])
    write_mesh_qpoints(case["case_dir"] / "dos" / "QPOINTS", case["key"], case["qmesh"])


def write_readmes() -> None:
    write(
        ROOT / "Ni" / "D" / "README.md",
        """\
        # Task D: Ni Phonons

        Prepared case:

        - `PBE_FM`: ferromagnetic Ni phonons from the Task B relaxed ground-state structure.

        Each case contains:

        - `force_constants`: 2x2x2 finite-difference primitive-cell supercell calculation.
        - `dispersion`: reads `vaspout.h5` force constants and evaluates a high-symmetry QPOINTS path.
        - `dos`: reads `vaspout.h5` force constants and evaluates a uniform q-point mesh for PhDOS.

        Shared scripts live in `../../common/D/`. Outputs are written under `../../outputs/D/`.
        """,
    )
    write(
        ROOT / "NiO" / "D" / "README.md",
        """\
        # Task D: NiO Phonons

        Prepared case:

        - `DFTU_AFM`: AFM-II DFT+U NiO phonons from the Task B relaxed ground-state structure.

        The case contains:

        - `dielectric`: primitive magnetic-cell LEPSILON run for Born effective charges and dielectric tensor.
        - `preconverge`: static magnetic-cell run that writes CHGCAR/WAVECAR for the phonon step.
        - `force_constants`: finite-difference calculation in the 4-ion magnetic primitive cell.
        - `dispersion`: reads `vaspout.h5` force constants and evaluates a high-symmetry QPOINTS path.
        - `dos`: reads `vaspout.h5` force constants and evaluates a uniform q-point mesh for PhDOS.

        The 32-ion 2x2x2 NiO phonon supercell was not used in this workflow because it crashed during
        the static DFT+U SCF initialization on the available VASP build, before the first electronic
        iteration. The magnetic primitive-cell setup follows the standard AFM-II NiO DFT+U convention and
        keeps the calculation runnable for the project report.

        The Slurm workflow extracts polar correction tags from `dielectric/OUTCAR` and appends them to
        the phonon calculations. Shared scripts live in `../../common/D/`. Outputs are written under
        `../../outputs/D/`.
        """,
    )
    write(
        ROOT / "common" / "D" / "README.md",
        """\
        # Common Task D Scripts

        Run these from the project root.

        Prepare phonon inputs:

        ```bash
        python3 common/D/prepare_task_d.py
        ```

        Submit the VASP workflow:

        ```bash
        sbatch run_task_d.slurm
        ```

        After VASP finishes, summarize results and create SVG/PDF plots:

        ```bash
        python3 common/D/analyze_task_d.py
        ```

        Outputs are written under `outputs/D/`.
        """,
    )


def main() -> None:
    for directory in ("calculations", "reports", "figures", "slurm"):
        (OUTPUT_DIR / directory).mkdir(parents=True, exist_ok=True)
    for case in CASES:
        prepare_case(case)
    write_readmes()
    print("Prepared Task D inputs in Ni/D and NiO/D")


if __name__ == "__main__":
    main()
