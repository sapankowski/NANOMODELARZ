# Task E: NiO Mechanical Properties

Prepared case:

- `DFTU_AFM/elastic`: finite-difference stress-strain elastic tensor for AFM-II DFT+U NiO,
  using the Task B relaxed ground-state structure.

The two Ni atoms are written as formal `Ni_up` and `Ni_down` species with duplicated Ni
POTCAR data so that opposite magnetic moments remain explicit during the elastic calculation.
The DFT+U parameters match Tasks A-D: `U(Ni) = 7.2 eV`, `J(Ni) = 1.0 eV`.

Shared scripts live in `../../common/E/`. Outputs are written under `../../outputs/E/`.
