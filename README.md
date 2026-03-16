# doc-diff-tracker
A project about tracking differences across documentation versions

## How to run
```bash
uv run python -m doc_diff_tracker.cli \ 
--old-root sample_data/html/v1 \
--new-root sample_data/html/v2 \
--old-version v1 \
--new-version v2 \
--output .example_report.json 
```