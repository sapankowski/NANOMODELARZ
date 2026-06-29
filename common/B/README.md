# Common Task B Scripts

Run these from the project root.

Prepare all Task B inputs:

```bash
python3 common/B/prepare_task_b.py
```

Check the generated inputs before submitting:

```bash
python3 common/B/check_task_b_inputs.py
```

Submit the VASP workflow:

```bash
sbatch run_task_b.slurm
```

After VASP finishes, summarize results:

```bash
python3 common/B/make_results_table.py
```

Outputs are written under `outputs/B/`.
