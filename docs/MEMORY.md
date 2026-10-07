# Project Memory

## Current status (2026-10-07)
Week 1 in progress. Structure, docs and ingest pipeline written; pipeline tested on synthetic data only.
Real DDL data not downloaded yet.

## Next step
Download keys + cases_2010 from the DDL Dropbox (docs/DATA.md), run ingest for 2010, and fix any
column-name mismatches in `src/court_delay/config.py`.

## Open questions
- Exact raw column names: `config.py` follows DDL's documented schema, which still needs checking against the real files.
- Cutoff date for censoring: currently the max date seen in the data. Check it is plausible (≈ late 2018/2019).

## Archive
Unrelated "Agent Action Firewall" planning docs moved to `_archive/agent-action-firewall/`.
