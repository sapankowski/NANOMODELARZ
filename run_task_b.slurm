#!/bin/bash -l
#SBATCH -J PROJECT_B
#SBATCH -p topola
#SBATCH -A g104-2685
#SBATCH --qos=hpc
#SBATCH -N 1
#SBATCH --ntasks-per-node=28
#SBATCH --mem-per-cpu=2G
#SBATCH -t 04:00:00
#SBATCH -o outputs/B/slurm/B.%A_%a.out
#SBATCH -e outputs/B/slurm/B.%A_%a.err
#SBATCH --array=0-7%2

set -euo pipefail

module purge
module use /apps/modulefiles
module use /apps/modulefiles/apps
module load vasp/6.5.0
export OMP_NUM_THREADS=1

CASES=(
  Ni/B/PBE_NM
  Ni/B/PBE_FM
  NiO/B/PBE_FM
  NiO/B/PBE_AFM
  NiO/B/DFTU_FM
  NiO/B/DFTU_AFM
  Ni/B/ATOM_Ni
  NiO/B/ATOM_O
)

if (( SLURM_ARRAY_TASK_ID >= ${#CASES[@]} )); then
  echo "Array index ${SLURM_ARRAY_TASK_ID} outside CASES length ${#CASES[@]}" >&2
  exit 1
fi

INPUT_CASE="$SLURM_SUBMIT_DIR/${CASES[$SLURM_ARRAY_TASK_ID]}"
OUTPUT_CASE="$SLURM_SUBMIT_DIR/outputs/B/calculations/${CASES[$SLURM_ARRAY_TASK_ID]}"

run_vasp_dir() {
  local input_dir="$1"
  local output_dir="$2"
  mkdir -p "$output_dir"
  cp -L "$input_dir"/INCAR "$input_dir"/KPOINTS "$input_dir"/POSCAR "$input_dir"/POTCAR "$output_dir"/
  cd "$output_dir"
  rm -f vasp.out CHG CHGCAR CONTCAR DOSCAR EIGENVAL IBZKPT OSZICAR OUTCAR PCDAT PROCAR REPORT WAVECAR XDATCAR vasprun.xml vaspout.h5
  srun vasp_std > vasp.out
}

if [[ -d "$INPUT_CASE/relax" ]]; then
  run_vasp_dir "$INPUT_CASE/relax" "$OUTPUT_CASE/relax"

  mkdir -p "$OUTPUT_CASE/static"
  cp -L "$INPUT_CASE/static"/INCAR "$INPUT_CASE/static"/KPOINTS "$INPUT_CASE/static"/POTCAR "$OUTPUT_CASE/static"/
  cp "$OUTPUT_CASE/relax/CONTCAR" "$OUTPUT_CASE/static/POSCAR"
  cd "$OUTPUT_CASE/static"
  rm -f vasp.out CHG CHGCAR CONTCAR DOSCAR EIGENVAL IBZKPT OSZICAR OUTCAR PCDAT PROCAR REPORT WAVECAR XDATCAR vasprun.xml vaspout.h5
  srun vasp_std > vasp.out
else
  run_vasp_dir "$INPUT_CASE" "$OUTPUT_CASE"
fi
