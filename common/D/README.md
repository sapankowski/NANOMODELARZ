# Common Task D Scripts

Run these from the project root.

Prepare phonon inputs:

```bash
python3 common/D/prepare_task_d.py
```

Submit the VASP workflow:

```bash
sbatch run_task_d.slurm
```

After VASP finishes, summarize results and create SVG/PDF plots:

```bash
python3 common/D/analyze_task_d.py
```

Outputs are written under `outputs/D/`.
