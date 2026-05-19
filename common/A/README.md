# Common Task A Scripts

Run these from the project root.

Prepare or refresh all Ni and NiO convergence input folders:

```bash
python3 common/A/prepare_convergence.py
```

After VASP finishes in all `Ni/A/ENCUT/*`, `Ni/A/KPOINTS/*`, `NiO/A/ENCUT/*`, and `NiO/A/KPOINTS/*` folders, create the report table:

```bash
python3 common/A/make_results_table.py
```

The table is written to:

- `outputs/A/Task_A_results_table.md`
- `outputs/A/Task_A_results_table.csv`

Raw VASP outputs are written under `outputs/A/calculations/`, mirroring the input folder names.
Slurm stdout/stderr files are written under `outputs/A/slurm/`.

Create the ENCUT and k-point convergence plots:

```bash
python3 common/A/plot_encut_convergence.py
```

The plots are written to:

- `outputs/A/Task_A_ENCUT_convergence.png`
- `outputs/A/Task_A_ENCUT_convergence.pdf`
- `outputs/A/Task_A_KPOINTS_convergence.png`
- `outputs/A/Task_A_KPOINTS_convergence.pdf`

If `matplotlib` is unavailable, the script writes `outputs/A/Task_A_ENCUT_convergence.svg`
and `outputs/A/Task_A_KPOINTS_convergence.svg` instead.
