# Submission Input Bundle

This folder collects the input files used for the Ni/NiO project calculations.
It is intended as a local replacement for adding files to an Overleaf project.

## Contents

- `calculations/Ni/...` and `calculations/NiO/...`: mirrored task folders with
  VASP input files (`INCAR`, `KPOINTS`, `POSCAR`, `POTCAR`, `QPOINTS`) and the
  task-level `README.md` files.
- `scripts/common/...`: preparation, checking, analysis, and plotting scripts
  used to generate and analyze the task inputs and outputs.
- `scripts/run_task_*.slurm`: top-level Slurm submission scripts for Tasks A--E.

Large generated files such as `WAVECAR`, `CHGCAR`, `vasprun.xml`, `OUTCAR`,
`DOSCAR`, and `vaspout.h5` are not duplicated here.  The relevant analyzed
outputs remain in `outputs/`, and the full calculation directories remain under
`Ni/` and `NiO/`.
