# Task B: NiO

Prepared cases:

- `PBE_FM`: ferromagnetic PBE relaxation followed by static energy.
- `PBE_AFM`: AFM-II PBE relaxation followed by static energy.
- `DFTU_FM`: ferromagnetic DFT+U relaxation followed by static energy.
- `DFTU_AFM`: AFM-II DFT+U relaxation followed by static energy.
- `ATOM_O`: isolated O atom reference for cohesive energy.

DFT+U uses `LDAUTYPE = 2`, `U(Ni) = 7.2 eV`, `J(Ni) = 1.0 eV`,
i.e. Dudarev `Ueff = U - J = 6.2 eV`.

Shared scripts live in `../../common/B/`. Outputs are written under `../../outputs/B/`.
