# Task D: NiO Phonons

Prepared case:

- `DFTU_AFM`: AFM-II DFT+U NiO phonons from the Task B relaxed ground-state structure.

The case contains:

- `dielectric`: primitive magnetic-cell LEPSILON run for Born effective charges and dielectric tensor.
- `force_constants`: 2x2x2 finite-difference supercell calculation.
- `dispersion`: reads `vaspout.h5` force constants and evaluates a high-symmetry QPOINTS path.
- `dos`: reads `vaspout.h5` force constants and evaluates a uniform q-point mesh for PhDOS.

The Slurm workflow extracts polar correction tags from `dielectric/OUTCAR` and appends them to
the phonon calculations. Shared scripts live in `../../common/D/`. Outputs are written under
`../../outputs/D/`.
