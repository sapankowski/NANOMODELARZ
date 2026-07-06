# Task A: Ni Convergence Tests

This folder contains VASP inputs for Task A convergence tests on fcc Ni in the ferromagnetic state.

- `INPUT_FILES/`: main reference inputs for this material.
- `ENCUT/ENCUT_*`: fixed `24x24x24` k-point mesh, varied cutoff energy.
- `KPOINTS/K_*`: fixed `ENCUT = 520 eV`, varied Gamma-centered k-point mesh.

- Shared scripts live in `../../common/A/`.

Run VASP in every generated `ENCUT/*` and `KPOINTS/*` folder.

After the jobs finish, create the report table from the project root:

```bash
python3 common/A/make_results_table.py
```

The convergence criterion is 1 meV/atom relative to the most demanding tested parameter.
Use `outputs/A/Task_A_results_table.md` or `outputs/A/Task_A_results_table.csv` in the report.
