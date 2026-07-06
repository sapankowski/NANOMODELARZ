#!/usr/bin/env python3
"""Preflight checks for Task D VASP input folders."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CASES = [ROOT / "Ni" / "D" / "PBE_FM", ROOT / "NiO" / "D" / "DFTU_AFM"]
STEPS = ["dielectric", "preconverge", "force_constants", "dispersion", "dos"]
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


def count_numeric_values(values: str) -> int:
    return len(values.split())


def check_step(step_dir: Path) -> list[str]:
    errors: list[str] = []
    poscar = step_dir / "POSCAR"
    incar = step_dir / "INCAR"
    potcar = step_dir / "POTCAR"
    if not (poscar.exists() and incar.exists() and potcar.exists()):
        return errors

    species, counts = read_poscar(poscar)
    nions = sum(counts)
    nspecies = len(species)
    tags = read_incar_tags(incar)
    ndatasets = len(DATASET_RE.findall(potcar.read_text(errors="ignore")))

    if ndatasets != nspecies:
        errors.append(f"{step_dir}: POTCAR has {ndatasets} datasets but POSCAR has {nspecies} species")

    magmom = tags.get("MAGMOM")
    if magmom and expand_multiplicity(magmom) != nions:
        errors.append(f"{step_dir}: MAGMOM expands to {expand_multiplicity(magmom)} values but POSCAR has {nions} ions")

    if tags.get("LDAU", "").upper() in {".TRUE.", "TRUE", "T"}:
        for tag in ("LDAUL", "LDAUU", "LDAUJ"):
            if tag not in tags:
                errors.append(f"{step_dir}: {tag} missing while LDAU is enabled")
            elif count_numeric_values(tags[tag]) != nspecies:
                errors.append(f"{step_dir}: {tag} has {count_numeric_values(tags[tag])} values but POSCAR has {nspecies} species")

    return errors


def main() -> None:
    errors: list[str] = []
    checked = 0
    for case in CASES:
        for step in STEPS:
            step_dir = case / step
            if step_dir.exists():
                checked += 1
                errors.extend(check_step(step_dir))

    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print(f"Task D input preflight passed for {checked} step directories")


if __name__ == "__main__":
    main()
