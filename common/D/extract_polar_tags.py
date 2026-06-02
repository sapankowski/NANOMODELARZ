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


def format_matrix_rows(rows: list[list[float]], indent: str = "  ") -> list[str]:
    return [indent + " ".join(f"{value:14.8f}" for value in row) for row in rows]


def format_tags(dielectric: list[list[float]], charges: list[list[list[float]]]) -> str:
    lines = ["LPHON_POLAR = .TRUE.", "PHON_DIELECTRIC = \\"]
    dielectric_rows = format_matrix_rows(dielectric)
    for index, row in enumerate(dielectric_rows):
        lines.append(row + (" \\" if index < len(dielectric_rows) - 1 else ""))

    lines.append("")
    lines.append("PHON_BORN_CHARGES = \\")
    charge_rows = []
    for tensor in charges:
        charge_rows.extend(format_matrix_rows(tensor))
        charge_rows.append("  \\")
    if charge_rows:
        charge_rows[-1] = charge_rows[-1].rstrip(" \\")
    lines.extend(charge_rows)
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outcar", type=Path, required=True, help="LEPSILON OUTCAR")
    parser.add_argument("--output", type=Path, required=True, help="Output INCAR tag snippet")
    args = parser.parse_args()

    lines = args.outcar.read_text(errors="ignore").splitlines()
    dielectric = parse_dielectric(lines)
    charges = parse_born_charges(lines)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(format_tags(dielectric, charges))
    print(f"Wrote polar phonon tags for {len(charges)} ions to {args.output}")


if __name__ == "__main__":
    main()
