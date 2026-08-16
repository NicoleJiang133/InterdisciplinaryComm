"""Read scientist edits out of report.md and write them to corrections.json.

Sundial's integration surface is the file. This module re-reads the Markdown
handoff, attributes each restatement to a stable entry anchor, and records
diffs against ledger.json. It does not call Sundial, Sun, or any network API.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from transfer_audit.models import LedgerEntry
from transfer_audit.report import entry_anchor_id, load_entries

ANCHOR_RE = re.compile(r"<!--\s*crosswork:entry\s+id=([^\s>]+)\s*-->")
RESTATEMENT_RE = re.compile(
    r"\*\*Target restatement\*\*[ \t]*\n+(.*?)(?=\n\*\*[A-Za-z]|\n<!--\s*crosswork:entry|\n### |\Z)",
    re.DOTALL,
)


class SyncCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str
    source_doc_id: str
    axis: str
    previous: str | None
    target_restatement: str
    source: str = "markdown"
    timestamp: str


class SyncResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unchanged: int
    corrected: int
    corrections: list[SyncCorrection]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize(text: str | None) -> str:
    return (text or "").strip()


def parse_anchored_restatements(markdown: str) -> list[tuple[str, str]]:
    """Return (entry_id, restatement) for each crosswork anchor in the file."""
    matches = list(ANCHOR_RE.finditer(markdown))
    found: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        block = markdown[start:end]
        rest_match = RESTATEMENT_RE.search(block)
        restatement = rest_match.group(1).strip() if rest_match else ""
        if restatement == "—":
            restatement = ""
        found.append((match.group(1), restatement))
    return found


def _load_corrections(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"corrections.json in {path.parent} is not a list")
    return payload


def _already_recorded(rows: list[dict], correction: SyncCorrection) -> bool:
    return any(
        row.get("source") == "markdown"
        and row.get("entry_id") == correction.entry_id
        and row.get("target_restatement") == correction.target_restatement
        for row in rows
    )


def format_sync_summary(result: SyncResult) -> str:
    lines = [f"{result.unchanged} entries unchanged, {result.corrected} corrected"]
    for item in result.corrections:
        lines.append("")
        lines.append(item.entry_id)
        lines.append(f"  before: {_normalize(item.previous) or '—'}")
        lines.append(f"  → after: {item.target_restatement}")
    return "\n".join(lines) + "\n"


def sync_run(run_dir: Path, report: Path | None = None) -> SyncResult:
    """Diff report.md against ledger.json and append markdown corrections."""
    run_dir = Path(run_dir)
    ledger_path = run_dir / "ledger.json"
    report_path = Path(report) if report is not None else run_dir / "report.md"
    if not ledger_path.is_file():
        raise FileNotFoundError(f"no ledger.json in {run_dir}")
    if not report_path.is_file():
        raise FileNotFoundError(f"no report.md at {report_path}")

    entries = load_entries(ledger_path)
    by_id: dict[str, LedgerEntry] = {entry_anchor_id(entry): entry for entry in entries}
    markdown = report_path.read_text(encoding="utf-8")

    unchanged = 0
    corrections: list[SyncCorrection] = []
    stamp = _now()
    for entry_id, restatement in parse_anchored_restatements(markdown):
        entry = by_id.get(entry_id)
        if entry is None:
            continue
        previous = _normalize(entry.target_restatement)
        current = _normalize(restatement)
        if current == previous:
            unchanged += 1
            continue
        corrections.append(
            SyncCorrection(
                entry_id=entry_id,
                source_doc_id=entry.source_doc_id,
                axis=entry.axis,
                previous=entry.target_restatement,
                target_restatement=current,
                source="markdown",
                timestamp=stamp,
            )
        )

    dest = run_dir / "corrections.json"
    rows = _load_corrections(dest)
    for item in corrections:
        if _already_recorded(rows, item):
            continue
        rows.append(item.model_dump())
    dest.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    return SyncResult(
        unchanged=unchanged,
        corrected=len(corrections),
        corrections=corrections,
    )
