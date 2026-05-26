# Common Task C Scripts

Run these from the project root.

Prepare electronic-structure inputs:

```bash
python3 common/C/prepare_task_c.py
```

Submit the VASP workflow:

```bash
sbatch run_task_c.slurm
```

After VASP finishes, summarize results and create SVG plots:

```bash
python3 common/C/analyze_task_c.py
```

Outputs are written under `outputs/C/`.
