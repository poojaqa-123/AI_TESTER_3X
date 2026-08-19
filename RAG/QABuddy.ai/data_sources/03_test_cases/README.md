# 03 — Test cases

Drop the ~5,000-row test-case export here as `.csv` or `.xlsx` (e.g. `testdata.csv`),
then ingest from the **Sources** tab (choose which columns are text vs. metadata),
or via CLI:

```bash
python -m ingestion.test_cases data_sources/03_test_cases/testdata.csv \
  --text-cols title,steps,expected,preconditions,tags \
  --meta-cols id,jira_id,priority,module,status
```
