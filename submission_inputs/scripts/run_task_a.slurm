#!/bin/bash -l
#SBATCH -J PROJECT_A
#SBATCH -p topola
#SBATCH -A g104-2685
#SBATCH --qos=hpc
#SBATCH -N 1
#SBATCH --ntasks-per-node=28
#SBATCH --mem-per-cpu=2G
#SBATCH -t 02:00:00
#SBATCH -o outputs/A/slurm/A.%A_%a.out
#SBATCH -e outputs/A/slurm/A.%A_%a.err
#SBATCH --array=0-53%4

set -euo pipefail

module purge
module use /apps/modulefiles
module use /apps/modulefiles/apps
module load vasp/6.5.0
export OMP_NUM_THREADS=1

NI_ENCUTS=(270 300 320 340 360 380 400 420 440 460 480 500 520 560 600)
NI_KMESHES=(8 10 12 14 16 18 20 22 24 26 28 30 32)
NIO_ENCUTS=(400 425 450 475 500 520 550 575 600 625 650 675 700 725 750 775 800)
NIO_KMESHES=(4 6 8 10 12 14 16 18 20)

RUN_DIRS=()
for encut in "${NI_ENCUTS[@]}"; do
  RUN_DIRS+=("Ni/A/ENCUT/ENCUT_${encut}")
done
for mesh in "${NI_KMESHES[@]}"; do
  RUN_DIRS+=("Ni/A/KPOINTS/K_$(printf "%02d" "$mesh")x$(printf "%02d" "$mesh")x$(printf "%02d" "$mesh")")
done
for encut in "${NIO_ENCUTS[@]}"; do
  RUN_DIRS+=("NiO/A/ENCUT/ENCUT_${encut}")
done
for mesh in "${NIO_KMESHES[@]}"; do
  RUN_DIRS+=("NiO/A/KPOINTS/K_$(printf "%02d" "$mesh")x$(printf "%02d" "$mesh")x$(printf "%02d" "$mesh")")
done

if (( SLURM_ARRAY_TASK_ID >= ${#RUN_DIRS[@]} )); then
  echo "Array index ${SLURM_ARRAY_TASK_ID} outside RUN_DIRS length ${#RUN_DIRS[@]}" >&2
  exit 1
fi

INPUT_DIR="$SLURM_SUBMIT_DIR/${RUN_DIRS[$SLURM_ARRAY_TASK_ID]}"
OUTPUT_DIR="$SLURM_SUBMIT_DIR/outputs/A/calculations/${RUN_DIRS[$SLURM_ARRAY_TASK_ID]}"

mkdir -p "$OUTPUT_DIR"
cp -L "$INPUT_DIR"/INCAR "$INPUT_DIR"/KPOINTS "$INPUT_DIR"/POSCAR "$INPUT_DIR"/POTCAR "$OUTPUT_DIR"/

cd "$OUTPUT_DIR"
rm -f vasp.out CHG CHGCAR CONTCAR DOSCAR EIGENVAL IBZKPT OSZICAR OUTCAR PCDAT PROCAR REPORT WAVECAR XDATCAR vasprun.xml vaspout.h5
srun vasp_std > vasp.out
