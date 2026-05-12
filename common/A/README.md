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

- `Task_A_results_table.md`
- `Task_A_results_table.csv`
