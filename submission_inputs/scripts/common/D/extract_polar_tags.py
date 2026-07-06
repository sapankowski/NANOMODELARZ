#!/usr/bin/env python3
"""Extract VASP phonon polar-correction INCAR tags from a LEPSILON OUTCAR."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


FLOAT_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?")


def floats(line: str) -> list[float]:
    return [float(value) for value in FLOAT_RE.findall(line)]


def parse_dielectric(lines: list[str]) -> list[list[float]]:
    starts = [
        index
        for index, line in enumerate(lines)
        if "MACROSCOPIC STATIC DIELECTRIC TENSOR" in line and "including local field" in line
    ]
    if not starts:
        starts = [index for index, line in enumerate(lines) if "MACROSCOPIC STATIC DIELECTRIC TENSOR" in line]
    if not starts:
        raise ValueError("Could not find dielectric tensor in OUTCAR")

    tensor: list[list[float]] = []
    for line in lines[starts[-1] + 1 :]:
        values = floats(line)
        if len(values) == 3:
            tensor.append(values)
            if len(tensor) == 3:
                return tensor
        elif tensor:
            break
    raise ValueError("Could not parse three dielectric tensor rows")


def parse_born_charges(lines: list[str]) -> list[list[list[float]]]:
    starts = [index for index, line in enumerate(lines) if "BORN EFFECTIVE CHARGES" in line]
    if not starts:
        raise ValueError("Could not find Born effective charge tensors in OUTCAR")

    charges: list[list[list[float]]] = []
    cursor = starts[-1] + 1
    while cursor < len(lines):
        if not lines[cursor].strip().startswith("ion"):
            cursor += 1
            continue
        cursor += 1
        tensor: list[list[float]] = []
        while cursor < len(lines) and len(tensor) < 3:
            values = floats(lines[cursor])
            if len(values) >= 4:
                tensor.append(values[-3:])
            cursor += 1
        if len(tensor) == 3:
            charges.append(tensor)
        else:
            break
    if not charges:
        raise ValueError("Could not parse any Born effective charge tensors")
    return charges


def read_poscar_nions(path: Path) -> int:
    lines = [line.split() for line in path.read_text(errors="ignore").splitlines() if line.strip()]
    if len(lines) < 7:
        raise ValueError(f"POSCAR is too short: {path}")
    counts_line = lines[5] if all(value.isdigit() for value in lines[5]) else lines[6]
    return sum(int(value) for value in counts_line)


def expand_charges(charges: list[list[list[float]]], target_nions: int | None) -> list[list[list[float]]]:
    if target_nions is None or target_nions == len(charges):
        return charges
    if target_nions % len(charges) != 0:
        raise ValueError(
            f"Cannot expand {len(charges)} Born-charge tensors to {target_nions} target ions"
        )
    repeat = target_nions // len(charges)
    expanded: list[list[list[float]]] = []
    for tensor in charges:
        expanded.extend([tensor] * repeat)
    return expanded


def format_matrix_rows(rows: list[list[float]], indent: str = "  ") -> list[str]:
    return [indent + " ".join(f"{value:14.8f}" for value in row) for row in rows]


def flatten_matrix(rows: list[list[float]]) -> list[float]:
    return [value for row in rows for value in row]


def format_tags(dielectric: list[list[float]], charges: list[list[list[float]]]) -> str:
    dielectric_values = flatten_matrix(dielectric)
    charge_values = [value for tensor in charges for value in flatten_matrix(tensor)]
    lines = ["LPHON_POLAR = .TRUE."]
    lines.extend(format_values_tag("PHON_DIELECTRIC", dielectric_values))
    lines.extend(format_values_tag("PHON_BORN_CHARGES", charge_values))
    return "\n".join(lines) + "\n"


def format_values_tag(name: str, values: list[float], values_per_line: int = 9) -> list[str]:
    rows = [
        " ".join(f"{value:.8f}" for value in values[index : index + values_per_line])
        for index in range(0, len(values), values_per_line)
    ]
    if len(rows) == 1:
        return [f"{name} = {rows[0]}"]
    lines = [f"{name} = \\"]
    for index, row in enumerate(rows):
        lines.append(f"  {row}" + (" \\" if index < len(rows) - 1 else ""))
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outcar", type=Path, required=True, help="LEPSILON OUTCAR")
    parser.add_argument("--output", type=Path, required=True, help="Output INCAR tag snippet")
    parser.add_argument(
        "--target-poscar",
        type=Path,
        help="Expand Born-charge tensors to match this POSCAR ion count",
    )
    args = parser.parse_args()

    lines = args.outcar.read_text(errors="ignore").splitlines()
    dielectric = parse_dielectric(lines)
    charges = parse_born_charges(lines)
    target_nions = read_poscar_nions(args.target_poscar) if args.target_poscar else None
    charges = expand_charges(charges, target_nions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(format_tags(dielectric, charges))
    print(f"Wrote polar phonon tags for {len(charges)} ions to {args.output}")


if __name__ == "__main__":
    main()
