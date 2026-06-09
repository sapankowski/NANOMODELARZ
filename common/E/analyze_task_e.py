#!/usr/bin/env python3
"""Analyze Task E elastic-tensor outputs and derive mechanical properties."""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path

from prepare_task_e import CASES, ROOT


OUTPUT_DIR = ROOT / "outputs" / "E"
CALC_DIR = OUTPUT_DIR / "calculations"
REPORT_DIR = OUTPUT_DIR / "reports"

TENSOR_LABELS = ["XX", "YY", "ZZ", "XY", "YZ", "ZX"]
ELASTIC_HEADER_RE = re.compile(r"TOTAL ELASTIC MODULI\s*\(kBar\)", re.I)
FLOAT_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?")


def calc_case(case: dict) -> Path:
    return CALC_DIR / case["case_dir"].relative_to(ROOT) / "elastic"


def read_text(path: Path) -> str:
    return path.read_text(errors="ignore") if path.exists() else ""


def parse_elastic_tensor(path: Path) -> list[list[float]] | None:
    text = read_text(path / "OUTCAR")
    if not text:
        return None

    matches = list(ELASTIC_HEADER_RE.finditer(text))
    if not matches:
        return None

    for match in reversed(matches):
        lines = text[match.end() :].splitlines()[:20]
        rows: list[list[float]] = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 7 and parts[0].upper() in TENSOR_LABELS:
                try:
                    rows.append([float(value) for value in parts[1:7]])
                except ValueError:
                    continue
            if len(rows) == 6:
                return rows
    return None


def parse_pressure(path: Path) -> float | None:
    text = read_text(path / "OUTCAR")
    matches = re.findall(r"external pressure\s*=\s*([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s*kB", text)
    return float(matches[-1]) if matches else None


def parse_total_energy(path: Path) -> float | None:
    text = read_text(path / "OUTCAR")
    matches = re.findall(r"free\s+energy\s+TOTEN\s*=\s*([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)", text)
    return float(matches[-1]) if matches else None


def parse_max_force(path: Path) -> float | None:
    text = read_text(path / "OUTCAR")
    marker = "TOTAL-FORCE (eV/Angst)"
    index = text.rfind(marker)
    if index < 0:
        return None
    forces = []
    for line in text[index:].splitlines()[2:]:
        values = [float(value) for value in FLOAT_RE.findall(line)]
        if len(values) >= 6:
            fx, fy, fz = values[-3:]
            forces.append(math.sqrt(fx * fx + fy * fy + fz * fz))
        elif forces:
            break
    return max(forces) if forces else None


def cubic_averages(tensor_kbar: list[list[float]]) -> dict[str, float]:
    tensor = [[value * 0.1 for value in row] for row in tensor_kbar]
    c11 = (tensor[0][0] + tensor[1][1] + tensor[2][2]) / 3.0
    c12 = (
        tensor[0][1]
        + tensor[0][2]
        + tensor[1][0]
        + tensor[1][2]
        + tensor[2][0]
        + tensor[2][1]
    ) / 6.0
    c44 = (tensor[3][3] + tensor[4][4] + tensor[5][5]) / 3.0
    bulk = (c11 + 2.0 * c12) / 3.0
    cprime = c11 - c12
    gv = (cprime + 3.0 * c44) / 5.0
    gr_denominator = 4.0 * c44 + 3.0 * cprime
    gr = 5.0 * cprime * c44 / gr_denominator if abs(gr_denominator) > 1e-12 else float("nan")
    shear = (gv + gr) / 2.0 if not math.isnan(gr) else gv
    young = 9.0 * bulk * shear / (3.0 * bulk + shear) if abs(3.0 * bulk + shear) > 1e-12 else float("nan")
    poisson = (3.0 * bulk - 2.0 * shear) / (2.0 * (3.0 * bulk + shear)) if abs(3.0 * bulk + shear) > 1e-12 else float("nan")
    return {
        "C11": c11,
        "C12": c12,
        "C44": c44,
        "Bulk": bulk,
        "Shear_Voigt": gv,
        "Shear_Reuss": gr,
        "Shear_Hill": shear,
        "Young": young,
        "Poisson": poisson,
    }


def mechanical_stability(values: dict[str, float] | None) -> str:
    if values is None:
        return "pending"
    stable = values["C11"] - values["C12"] > 0 and values["C11"] + 2.0 * values["C12"] > 0 and values["C44"] > 0
    return "yes" if stable else "no"


def fmt(value: float | None, digits: int = 2) -> str:
    if value is None or math.isnan(value):
        return "pending"
    return f"{value:.{digits}f}"


def write_full_tensor(case: dict, tensor_kbar: list[list[float]]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{case['key']}_elastic_tensor_GPa.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([""] + TENSOR_LABELS)
        for label, row in zip(TENSOR_LABELS, tensor_kbar):
            writer.writerow([label] + [f"{value * 0.1:.6f}" for value in row])


def write_tables(rows: list[dict[str, str]]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with (REPORT_DIR / "Task_E_results_table.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    headers = list(rows[0])
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row[header] for header in headers) + " |")
    (REPORT_DIR / "Task_E_results_table.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    rows: list[dict[str, str]] = []
    for case in CASES:
        path = calc_case(case)
        tensor = parse_elastic_tensor(path)
        values = cubic_averages(tensor) if tensor is not None else None
        if tensor is not None:
            write_full_tensor(case, tensor)
        rows.append(
            {
                "System": case["system"],
                "Case": case["key"],
                "C11, GPa": fmt(values["C11"] if values else None),
                "C12, GPa": fmt(values["C12"] if values else None),
                "C44, GPa": fmt(values["C44"] if values else None),
                "Bulk modulus, GPa": fmt(values["Bulk"] if values else None),
                "Shear modulus, GPa": fmt(values["Shear_Hill"] if values else None),
                "Young modulus, GPa": fmt(values["Young"] if values else None),
                "Poisson ratio": fmt(values["Poisson"] if values else None, digits=3),
                "Pressure, kB": fmt(parse_pressure(path), digits=3),
                "Max force, eV/A": fmt(parse_max_force(path), digits=4),
                "Total energy, eV": fmt(parse_total_energy(path), digits=6),
                "Mechanically stable?": mechanical_stability(values),
            }
        )
    write_tables(rows)
    print(f"Wrote {REPORT_DIR / 'Task_E_results_table.md'} and {REPORT_DIR / 'Task_E_results_table.csv'}")


if __name__ == "__main__":
    main()
