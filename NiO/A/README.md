# Task A: NiO Convergence Tests

This folder contains convergence tests for rocksalt NiO in an antiferromagnetic state.

- `ENCUT/ENCUT_*`: fixed `10x10x10` k-point mesh, varied cutoff energy.
- `KPOINTS/K_*`: fixed `ENCUT = 520 eV`, varied Gamma-centered k-point mesh.
- `analyze_convergence.py`: parses completed VASP runs and writes CSV tables and plots.

Run VASP in every generated subfolder. After all jobs finish, run:

```bash
python analyze_convergence.py
```

Use `results/summary_table.csv`, `plots/encut.png`, and `plots/kpoints.png` in the report.
The convergence criterion is 1 meV/atom relative to the most demanding tested parameter.
