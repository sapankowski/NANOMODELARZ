# Common Task E Scripts

Run these from the project root.

Prepare elastic-tensor inputs:

```bash
python3 common/E/prepare_task_e.py
```

Submit the VASP workflow:

```bash
sbatch run_task_e.slurm
```

After VASP finishes, summarize elastic constants and derived mechanical properties:

```bash
python3 common/E/analyze_task_e.py
```

Outputs are written under `outputs/E/`.
