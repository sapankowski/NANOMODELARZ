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

dump_failure_context() {
  local status="$?"
  local cwd
  cwd="$(pwd)"
  local log="$cwd/task_d_failure_context.log"
  {
    echo "Task D failure context"
    echo "timestamp = $(date -Is)"
    echo "exit_status = $status"
    echo "job = ${SLURM_JOB_ID:-unknown}"
    echo "array_task = ${SLURM_ARRAY_TASK_ID:-none}"
    echo "directory = $cwd"
    echo
    echo "directory listing:"
    ls -lh
    echo
    if [[ -f input_audit.txt ]]; then
      echo "input_audit.txt:"
      cat input_audit.txt
      echo
    fi
    if [[ -f vasp.out ]]; then
      echo "tail -n 120 vasp.out:"
      tail -n 120 vasp.out
      echo
    fi
    if [[ -f OUTCAR ]]; then
      echo "tail -n 160 OUTCAR:"
      tail -n 160 OUTCAR
      echo
    fi
  } > "$log" 2>&1 || true
  cat "$log" >&2 || true
  exit "$status"
}

trap dump_failure_context ERR

CASES=(
  Ni/D/PBE_FM
  NiO/D/DFTU_AFM
)

if (( SLURM_ARRAY_TASK_ID >= ${#CASES[@]} )); then
  echo "Array index ${SLURM_ARRAY_TASK_ID} outside CASES length ${#CASES[@]}" >&2
  exit 1
fi

python3 "$SLURM_SUBMIT_DIR/common/D/check_task_d_inputs.py"

INPUT_CASE="$SLURM_SUBMIT_DIR/${CASES[$SLURM_ARRAY_TASK_ID]}"
OUTPUT_CASE="$SLURM_SUBMIT_DIR/outputs/D/calculations/${CASES[$SLURM_ARRAY_TASK_ID]}"
POLAR_TAGS="$OUTPUT_CASE/polar_tags.inc"

clean_vasp_outputs() {
  rm -f vasp.out CHG CHGCAR CONTCAR DOSCAR EIGENVAL IBZKPT OSZICAR OUTCAR PCDAT PROCAR REPORT WAVECAR XDATCAR vasprun.xml vaspin.h5 vaspout.h5
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

audit_inputs() {
  local output_dir="$1"
  {
    echo "timestamp = $(date -Is)"
    echo "job = ${SLURM_JOB_ID:-unknown}"
    echo "array_task = ${SLURM_ARRAY_TASK_ID:-none}"
    echo "directory = $output_dir"
    echo
    echo "files:"
    for file in INCAR KPOINTS POSCAR POTCAR CHGCAR WAVECAR vaspin.h5; do
      if [[ -e "$output_dir/$file" ]]; then
        stat -c "  %n size=%s" "$output_dir/$file"
        sha256sum "$output_dir/$file"
      else
        echo "  $file missing"
      fi
    done
    echo
    echo "selected INCAR tags:"
    grep -E '^(SYSTEM|ISTART|ICHARG|IBRION|NSW|ISYM|LDAU|LDAUL|LDAUU|LDAUJ|MAGMOM|ADDGRID|LWAVE|LCHARG|LPHON|PHON_)' "$output_dir/INCAR" || true
    echo
    echo "POSCAR header:"
    sed -n '1,8p' "$output_dir/POSCAR"
    echo
    echo "POTCAR datasets:"
    grep -n 'TITEL\\|VRHFIN' "$output_dir/POTCAR" || true
  } > "$output_dir/input_audit.txt"
}

run_regular_step() {
  local step="$1"
  local output_dir="$OUTPUT_CASE/$step"
  copy_inputs "$step"
  cd "$output_dir"
  clean_vasp_outputs
  audit_inputs "$output_dir"
  srun vasp_std > vasp.out
}

run_force_constants_step() {
  local output_dir="$OUTPUT_CASE/force_constants"
  copy_inputs force_constants
  cd "$output_dir"
  clean_vasp_outputs
  if [[ -d "$INPUT_CASE/preconverge" ]]; then
    cp "$OUTPUT_CASE/preconverge/WAVECAR" "$OUTPUT_CASE/preconverge/CHGCAR" "$output_dir"/
  fi
  audit_inputs "$output_dir"
  srun vasp_std > vasp.out
}

run_postprocess_step() {
  local step="$1"
  local output_dir="$OUTPUT_CASE/$step"
  copy_inputs "$step"
  append_polar_tags_if_present "$output_dir"
  cd "$output_dir"
  clean_vasp_outputs
  cp "$OUTPUT_CASE/force_constants/vaspout.h5" vaspin.h5
  audit_inputs "$output_dir"
  srun vasp_std > vasp.out
}

if [[ -d "$INPUT_CASE/dielectric" ]]; then
  run_regular_step dielectric
  python3 "$SLURM_SUBMIT_DIR/common/D/extract_polar_tags.py" \
    --outcar "$OUTPUT_CASE/dielectric/OUTCAR" \
    --output "$POLAR_TAGS" \
    --target-poscar "$INPUT_CASE/force_constants/POSCAR"
fi

if [[ -d "$INPUT_CASE/preconverge" ]]; then
  run_regular_step preconverge
fi

run_force_constants_step
run_postprocess_step dispersion
run_postprocess_step dos
