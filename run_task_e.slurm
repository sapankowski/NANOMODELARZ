#!/bin/bash -l
#SBATCH -J PROJECT_E
#SBATCH -p topola
#SBATCH -A g104-2685
#SBATCH --qos=hpc
#SBATCH -N 1
#SBATCH --ntasks-per-node=28
#SBATCH --mem-per-cpu=2G
#SBATCH -t 08:00:00
#SBATCH -o outputs/E/slurm/E.%A_%a.out
#SBATCH -e outputs/E/slurm/E.%A_%a.err
#SBATCH --array=0-1%1

set -euo pipefail

module purge
module use /apps/modulefiles
module use /apps/modulefiles/apps
module load vasp/6.5.0
export OMP_NUM_THREADS=1

CASES=(
  Ni/E/PBE_FM
  NiO/E/DFTU_AFM
)

if (( SLURM_ARRAY_TASK_ID >= ${#CASES[@]} )); then
  echo "Array index ${SLURM_ARRAY_TASK_ID} outside CASES length ${#CASES[@]}" >&2
  exit 1
fi

python3 "$SLURM_SUBMIT_DIR/common/E/check_task_e_inputs.py"

INPUT_CASE="$SLURM_SUBMIT_DIR/${CASES[$SLURM_ARRAY_TASK_ID]}"
OUTPUT_CASE="$SLURM_SUBMIT_DIR/outputs/E/calculations/${CASES[$SLURM_ARRAY_TASK_ID]}"

clean_vasp_outputs() {
  rm -f vasp.out CHG CHGCAR CONTCAR DOSCAR EIGENVAL IBZKPT OSZICAR OUTCAR PCDAT PROCAR REPORT WAVECAR XDATCAR vasprun.xml vaspin.h5 vaspout.h5
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
    for file in INCAR KPOINTS POSCAR POTCAR; do
      if [[ -e "$output_dir/$file" ]]; then
        stat -c "  %n size=%s" "$output_dir/$file"
        sha256sum "$output_dir/$file"
      else
        echo "  $file missing"
      fi
    done
    echo
    echo "selected INCAR tags:"
    grep -E '^(SYSTEM|ENCUT|EDIFF|IBRION|ISIF|NSW|NFREE|POTIM|ISYM|ISPIN|MAGMOM|LDAU|LDAUL|LDAUU|LDAUJ)' "$output_dir/INCAR" || true
    echo
    echo "POSCAR header:"
    sed -n '1,8p' "$output_dir/POSCAR"
    echo
    echo "POTCAR datasets:"
    grep -n 'TITEL\|VRHFIN' "$output_dir/POTCAR" || true
  } > "$output_dir/input_audit.txt"
}

run_elastic() {
  local input_dir="$INPUT_CASE/elastic"
  local output_dir="$OUTPUT_CASE/elastic"
  mkdir -p "$output_dir"
  cp -L "$input_dir"/INCAR "$input_dir"/KPOINTS "$input_dir"/POSCAR "$input_dir"/POTCAR "$output_dir"/
  cd "$output_dir"
  clean_vasp_outputs
  audit_inputs "$output_dir"
  srun vasp_std > vasp.out
}

run_elastic
