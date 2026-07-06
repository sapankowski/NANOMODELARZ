#!/usr/bin/env python3
"""Preflight checks for Task B VASP input folders."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ROOT / "Ni" / "B" / "PBE_NM" / "relax",
    ROOT / "Ni" / "B" / "PBE_NM" / "static",
    ROOT / "Ni" / "B" / "PBE_FM" / "relax",
    ROOT / "Ni" / "B" / "PBE_FM" / "static",
    ROOT / "NiO" / "B" / "PBE_FM" / "relax",
    ROOT / "NiO" / "B" / "PBE_FM" / "static",
    ROOT / "NiO" / "B" / "PBE_AFM" / "relax",
    ROOT / "NiO" / "B" / "PBE_AFM" / "static",
    ROOT / "NiO" / "B" / "DFTU_FM" / "relax",
    ROOT / "NiO" / "B" / "DFTU_FM" / "static",
    ROOT / "NiO" / "B" / "DFTU_AFM" / "relax",
    ROOT / "NiO" / "B" / "DFTU_AFM" / "static",
    ROOT / "Ni" / "B" / "ATOM_Ni",
    ROOT / "NiO" / "B" / "ATOM_O",
]
DATASET_RE = re.compile(r"End of Dataset")
POTCAR_HEADER_RE = re.compile(r"^\s*PAW_PBE\s+\S+", re.M)
TAG_RE = re.compile(r"^\s*([A-Za-z_]+)\s*=\s*(.*?)\s*$")


def read_poscar(path: Path) -> tuple[list[str], list[int]]:
    lines = [line.split() for line in path.read_text(errors="ignore").splitlines() if line.strip()]
    if len(lines) < 7:
        raise ValueError(f"{path}: POSCAR too short")
    if all(value.isdigit() for value in lines[5]):
        species = [f"species_{index + 1}" for index in range(len(lines[5]))]
        counts = [int(value) for value in lines[5]]
    else:
        species = lines[5]
        counts = [int(value) for value in lines[6]]
    return species, counts


def read_incar_tags(path: Path) -> dict[str, str]:
    tags: dict[str, str] = {}
    for line in path.read_text(errors="ignore").splitlines():
        line = line.split("#", 1)[0].strip()
        match = TAG_RE.match(line)
        if match:
            tags[match.group(1).upper()] = match.group(2)
    return tags


def expand_multiplicity(values: str) -> int:
    total = 0
    for token in values.split():
        if "*" in token:
            count, _value = token.split("*", 1)
            total += int(count)
        else:
            total += 1
    return total


def count_values(values: str) -> int:
    return len(values.split())


def check_case(case_dir: Path) -> list[str]:
    errors: list[str] = []
    for filename in ("INCAR", "KPOINTS", "POSCAR", "POTCAR"):
        if not (case_dir / filename).exists():
            errors.append(f"{case_dir.relative_to(ROOT)}: missing {filename}")
    if errors:
        return errors

    species, counts = read_poscar(case_dir / "POSCAR")
    nspecies = len(species)
    nions = sum(counts)
    potcar_text = (case_dir / "POTCAR").read_text(errors="ignore")
    ndatasets = len(DATASET_RE.findall(potcar_text))
    nheaders = len(POTCAR_HEADER_RE.findall(potcar_text))
    tags = read_incar_tags(case_dir / "INCAR")

    if ndatasets != nspecies:
        errors.append(f"{case_dir.relative_to(ROOT)}: POTCAR has {ndatasets} datasets but POSCAR has {nspecies} species")
    if nheaders != nspecies:
        errors.append(f"{case_dir.relative_to(ROOT)}: POTCAR has {nheaders} PAW headers but POSCAR has {nspecies} species")

    magmom = tags.get("MAGMOM")
    if magmom and expand_multiplicity(magmom) != nions:
        errors.append(f"{case_dir.relative_to(ROOT)}: MAGMOM expands to {expand_multiplicity(magmom)} values but POSCAR has {nions} ions")

    if tags.get("LDAU", "").upper() in {".TRUE.", "TRUE", "T"}:
        for tag in ("LDAUL", "LDAUU", "LDAUJ"):
            if tag not in tags:
                errors.append(f"{case_dir.relative_to(ROOT)}: {tag} missing while LDAU is enabled")
            elif count_values(tags[tag]) != nspecies:
                errors.append(f"{case_dir.relative_to(ROOT)}: {tag} has {count_values(tags[tag])} values but POSCAR has {nspecies} species")

    return errors


def main() -> None:
    errors: list[str] = []
    for case_dir in CASES:
        errors.extend(check_case(case_dir))
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print(f"Task B input preflight passed for {len(CASES)} input directories")


if __name__ == "__main__":
    main()
