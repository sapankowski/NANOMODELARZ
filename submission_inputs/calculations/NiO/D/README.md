# Task D: NiO Phonons

Prepared case:

- `DFTU_AFM`: AFM-II DFT+U NiO phonons from the Task B relaxed ground-state structure.

The case contains:

- `dielectric`: primitive magnetic-cell LEPSILON run for Born effective charges and dielectric tensor.
- `preconverge`: static magnetic-cell run that writes CHGCAR/WAVECAR for the phonon step.
- `force_constants`: finite-difference calculation in the 4-ion magnetic primitive cell.
- `dispersion`: reads `vaspout.h5` force constants and evaluates a high-symmetry QPOINTS path.
- `dos`: reads `vaspout.h5` force constants and evaluates a uniform q-point mesh for PhDOS.

The 32-ion 2x2x2 NiO phonon supercell was not used in this workflow because it crashed during
the static DFT+U SCF initialization on the available VASP build, before the first electronic
iteration. The magnetic primitive-cell setup follows the standard AFM-II NiO DFT+U convention and
keeps the calculation runnable for the project report.

The Slurm workflow extracts polar correction tags from `dielectric/OUTCAR` and appends them to
the phonon calculations. Shared scripts live in `../../common/D/`. Outputs are written under
`../../outputs/D/`.
