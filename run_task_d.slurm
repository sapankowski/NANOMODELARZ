#!/bin/bash -l
#SBATCH -J PROJECT_D
#SBATCH -p topola
#SBATCH -A g104-2685
#SBATCH --qos=hpc
#SBATCH -N 1
#SBATCH --ntasks-per-node=28
#SBATCH --mem-per-cpu=2G
#SBATCH -t 08:00:00
#SBATCH -o outputs/D/slurm/D.%A_%a.out
#SBATCH -e outputs/D/slurm/D.%A_%a.err
#SBATCH --array=0-1%1

set -euo pipefail

module purge
module use /apps/modulefiles
module use /apps/modulefiles/apps
module load vasp/6.5.0
export OMP_NUM_THREADS=1

CASES=(
  Ni/D/PBE_FM
  NiO/D/DFTU_AFM
)

if (( SLURM_ARRAY_TASK_ID >= ${#CASES[@]} )); then
  echo "Array index ${SLURM_ARRAY_TASK_ID} outside CASES length ${#CASES[@]}" >&2
  exit 1
fi

INPUT_CASE="$SLURM_SUBMIT_DIR/${CASES[$SLURM_ARRAY_TASK_ID]}"
OUTPUT_CASE="$SLURM_SUBMIT_DIR/outputs/D/calculations/${CASES[$SLURM_ARRAY_TASK_ID]}"
POLAR_TAGS="$OUTPUT_CASE/polar_tags.inc"

clean_vasp_outputs() {
  rm -f vasp.out CHG CHGCAR CONTCAR DOSCAR EIGENVAL IBZKPT OSZICAR OUTCAR PCDAT PROCAR REPORT WAVECAR XDATCAR vasprun.xml vaspout.h5
}

copy_inputs() {
  local step="$1"
  local input_dir="$INPUT_CASE/$step"
  local output_dir="$OUTPUT_CASE/$step"
  mkdir -p "$output_dir"
  cp -L "$input_dir"/INCAR "$input_dir"/KPOINTS "$input_dir"/POSCAR "$input_dir"/POTCAR "$output_dir"/
  if [[ -f "$input_dir/QPOINTS" ]]; then
    cp -L "$input_dir/QPOINTS" "$output_dir"/
  fi
}

append_polar_tags_if_present() {
  local output_dir="$1"
  if [[ -f "$POLAR_TAGS" ]]; then
    {
      echo
      cat "$POLAR_TAGS"
    } >> "$output_dir/INCAR"
  fi
}

run_regular_step() {
  local step="$1"
  local output_dir="$OUTPUT_CASE/$step"
  copy_inputs "$step"
  cd "$output_dir"
  clean_vasp_outputs
  srun vasp_std > vasp.out
}

run_phonon_step() {
  local step="$1"
  local output_dir="$OUTPUT_CASE/$step"
  copy_inputs "$step"
  append_polar_tags_if_present "$output_dir"
  cd "$output_dir"
  clean_vasp_outputs
  srun vasp_std > vasp.out
}

run_postprocess_step() {
  local step="$1"
  local output_dir="$OUTPUT_CASE/$step"
  copy_inputs "$step"
  append_polar_tags_if_present "$output_dir"
  cp "$OUTPUT_CASE/force_constants/vaspout.h5" "$output_dir/vaspin.h5"
  cd "$output_dir"
  clean_vasp_outputs
  srun vasp_std > vasp.out
}

if [[ -d "$INPUT_CASE/dielectric" ]]; then
  run_regular_step dielectric
  python3 "$SLURM_SUBMIT_DIR/common/D/extract_polar_tags.py" \
    --outcar "$OUTPUT_CASE/dielectric/OUTCAR" \
    --output "$POLAR_TAGS"
fi

run_phonon_step force_constants
run_postprocess_step dispersion
run_postprocess_step dos
