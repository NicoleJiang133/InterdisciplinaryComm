# transfer-audit

Takes a scientific claim borrowed from another discipline and emits an assumption
ledger: a structured audit of whether the source result's validity conditions still
hold in the target system. It generates the questions, it does not issue verdicts.

Literature access is the `paperclip` CLI via subprocess; state is JSON files on disk.

Setup: `python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"`
Tests: `pytest -m "not integration"` (drop the marker filter to hit the live CLI).

See `BUILD.md` for the build spec and `NOTES.md` for probed CLI behaviour.
