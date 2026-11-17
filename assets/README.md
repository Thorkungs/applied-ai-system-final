# Assets

- `sample_runs/` holds reproducible evidence: command output, agent traces and a log sample, saved as text.
  Each file starts with the command that produced it.
- The architecture diagram source is in [`../diagrams/architecture.mmd`](../diagrams/architecture.mmd). It is also embedded in the main README, where GitHub renders it.

| File | What it shows |
| --- | --- |
| `sample_runs/01_end_to_end.txt` | Three requests answered end to end, the first with a full agent trace |
| `sample_runs/02_retrieval_before_after.txt` | The same requests with retrieval off (`--baseline`) and on |
| `sample_runs/03_self_check_and_revision.txt` | The self-check revising a ranking, and two cases where it cannot |
| `sample_runs/04_guardrails.txt` | Rejected, clarified and crisis requests, and a negation |
| `sample_runs/05_human_in_the_loop.txt` | A person correcting what was understood with `--confirm` |
| `sample_runs/06_evaluation.txt` | Full output of `python -m src.evaluate` |
| `sample_runs/07_pytest.txt` | Full output of `pytest -v` |
| `sample_runs/08_agent_traces.md` | Saved agent reasoning traces (`--save-trace`) |
| `sample_runs/09_vibefinder_log_sample.txt` | A sample of `logs/vibefinder.log` |
