#!/bin/bash -l
#SBATCH -J PROJECT_C
#SBATCH -p topola
#SBATCH -A g104-2685
#SBATCH --qos=hpc
#SBATCH -N 1
#SBATCH --ntasks-per-node=28
#SBATCH --mem-per-cpu=2G
#SBATCH -t 04:00:00
#SBATCH -o outputs/C/slurm/C.%A_%a.out
#SBATCH -e outputs/C/slurm/C.%A_%a.err
#SBATCH --array=0-2%1

set -euo pipefail

module purge
module use /apps/modulefiles
module use /apps/modulefiles/apps
module load vasp/6.5.0
export OMP_NUM_THREADS=1

CASES=(
  Ni/C/PBE_FM
  NiO/C/PBE_AFM
  NiO/C/DFTU_AFM
)

if (( SLURM_ARRAY_TASK_ID >= ${#CASES[@]} )); then
  echo "Array index ${SLURM_ARRAY_TASK_ID} outside CASES length ${#CASES[@]}" >&2
  exit 1
fi

INPUT_CASE="$SLURM_SUBMIT_DIR/${CASES[$SLURM_ARRAY_TASK_ID]}"
OUTPUT_CASE="$SLURM_SUBMIT_DIR/outputs/C/calculations/${CASES[$SLURM_ARRAY_TASK_ID]}"

clean_vasp_outputs() {
  rm -f vasp.out CHG CHGCAR CONTCAR DOSCAR EIGENVAL IBZKPT OSZICAR OUTCAR PCDAT PROCAR REPORT WAVECAR XDATCAR vasprun.xml vaspout.h5
}

run_step() {
  local step="$1"
  local input_dir="$INPUT_CASE/$step"
  local output_dir="$OUTPUT_CASE/$step"
  mkdir -p "$output_dir"
  cp -L "$input_dir"/INCAR "$input_dir"/KPOINTS "$input_dir"/POSCAR "$input_dir"/POTCAR "$output_dir"/
  cd "$output_dir"
  clean_vasp_outputs
  srun vasp_std > vasp.out
}

run_fixed_charge_step() {
  local step="$1"
  local input_dir="$INPUT_CASE/$step"
  local output_dir="$OUTPUT_CASE/$step"
  mkdir -p "$output_dir"
  cp -L "$input_dir"/INCAR "$input_dir"/KPOINTS "$input_dir"/POSCAR "$input_dir"/POTCAR "$output_dir"/
  cp "$OUTPUT_CASE/scf/CHGCAR" "$output_dir/CHGCAR"
  cd "$output_dir"
  rm -f vasp.out CHG CONTCAR DOSCAR EIGENVAL IBZKPT OSZICAR OUTCAR PCDAT PROCAR REPORT WAVECAR XDATCAR vasprun.xml vaspout.h5
  srun vasp_std > vasp.out
}

run_step scf
run_fixed_charge_step dos
run_fixed_charge_step bands
