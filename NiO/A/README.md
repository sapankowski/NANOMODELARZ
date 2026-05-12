# Task A: NiO Convergence Tests

This folder contains VASP inputs for Task A convergence tests on rocksalt NiO in an antiferromagnetic state.

- `ENCUT/ENCUT_*`: fixed `10x10x10` k-point mesh, varied cutoff energy.
- `KPOINTS/K_*`: fixed `ENCUT = 520 eV`, varied Gamma-centered k-point mesh.
- Shared scripts live in `../../common/A/`.

Run VASP in every generated `ENCUT/*` and `KPOINTS/*` folder. After all jobs finish, create the report table from the project root:

```bash
python3 common/A/make_results_table.py
```

Use `Task_A_results_table.md` or `Task_A_results_table.csv` in the report.
The convergence criterion is 1 meV/atom relative to the most demanding tested parameter.
