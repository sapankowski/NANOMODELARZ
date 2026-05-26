# Task C: NiO Electronic Structure

Prepared cases:

- `PBE_AFM`: AFM-II PBE electronic structure from the Task B relaxed ground-state structure.
- `DFTU_AFM`: AFM-II DFT+U electronic structure from the Task B relaxed ground-state structure.

The DFT+U case uses `LDAUTYPE = 2`, `U(Ni) = 7.2 eV`, and `J(Ni) = 1.0 eV`.
Each case contains `scf`, `dos`, and `bands` subfolders. Shared scripts live in `../../common/C/`.
Outputs are written under `../../outputs/C/`.
