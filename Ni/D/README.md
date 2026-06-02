# Task D: Ni Phonons

Prepared case:

- `PBE_FM`: ferromagnetic Ni phonons from the Task B relaxed ground-state structure.

Each case contains:

- `force_constants`: 2x2x2 finite-difference supercell calculation.
- `dispersion`: reads `vaspout.h5` force constants and evaluates a high-symmetry QPOINTS path.
- `dos`: reads `vaspout.h5` force constants and evaluates a uniform q-point mesh for PhDOS.

Shared scripts live in `../../common/D/`. Outputs are written under `../../outputs/D/`.
