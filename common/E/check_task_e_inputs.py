#!/usr/bin/env python3
"""Preflight checks for Task E VASP input folders."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CASES = [ROOT / "Ni" / "E" / "PBE_FM" / "elastic", ROOT / "NiO" / "E" / "DFTU_AFM" / "elastic"]
DATASET_RE = re.compile(r"End of Dataset")
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
            errors.append(f"{case_dir}: missing {filename}")
    if errors:
        return errors

    species, counts = read_poscar(case_dir / "POSCAR")
    tags = read_incar_tags(case_dir / "INCAR")
    nspecies = len(species)
    nions = sum(counts)
    ndatasets = len(DATASET_RE.findall((case_dir / "POTCAR").read_text(errors="ignore")))

    if ndatasets != nspecies:
        errors.append(f"{case_dir}: POTCAR has {ndatasets} datasets but POSCAR has {nspecies} species")
    if tags.get("IBRION") != "6" or tags.get("ISIF") != "3":
        errors.append(f"{case_dir}: expected IBRION = 6 and ISIF = 3 for elastic constants")
    magmom = tags.get("MAGMOM")
    if magmom and expand_multiplicity(magmom) != nions:
        errors.append(f"{case_dir}: MAGMOM expands to {expand_multiplicity(magmom)} values but POSCAR has {nions} ions")
    if tags.get("LDAU", "").upper() in {".TRUE.", "TRUE", "T"}:
        for tag in ("LDAUL", "LDAUU", "LDAUJ"):
            if tag not in tags:
                errors.append(f"{case_dir}: {tag} missing while LDAU is enabled")
            elif count_values(tags[tag]) != nspecies:
                errors.append(f"{case_dir}: {tag} has {count_values(tags[tag])} values but POSCAR has {nspecies} species")
    return errors


def main() -> None:
    errors: list[str] = []
    for case in CASES:
        errors.extend(check_case(case))
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print(f"Task E input preflight passed for {len(CASES)} elastic calculations")


if __name__ == "__main__":
    main()
