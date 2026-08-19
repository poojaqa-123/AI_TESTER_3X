# 10 — Jenkins logs & results

Drop Jenkins console/log output here as `.log` or `.txt` (one file per build,
ideally named like `<job_name>_<build_number>.log`), then ingest from the
**Sources** tab, or:

```bash
python -m ingestion.jenkins_logs --path data_sources/10_jenkins_logs
```

Only failure/stack-trace blocks and a per-run summary are chunked and embedded —
verbose passing/INFO lines are skipped to keep token usage low.
