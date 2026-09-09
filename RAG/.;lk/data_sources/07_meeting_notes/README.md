# 07 — Meeting notes & recordings

Drop meeting transcripts here as `.txt` (or `.md`), then ingest from the
**Sources** tab, or:

```bash
python -m ingestion.transcripts --path data_sources/07_meeting_notes
```

If your transcripts have speaker/timestamp markers (e.g. `Speaker: ...` or
`[00:12:34]`), the chunker splits on those boundaries first before falling back
to a sliding window.
