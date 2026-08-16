"""Local product UI. Localhost only. Orchestrates existing pipeline modules."""

from __future__ import annotations

import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from transfer_audit.align import score_alignment, write_alignment
from transfer_audit.cli import default_out
from transfer_audit.ingest import build_context, write_context
from transfer_audit.ledger import run_map, write_ledger
from transfer_audit.models import ALIGNMENT_SLOTS, REPO_ROOT, TransferContext
from transfer_audit.report import load_alignment, load_context, load_entries, render_report, write_report
from transfer_audit.retrieve import retrieve, write_search

WEB = REPO_ROOT / "web"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
RUNS = REPO_ROOT / "runs"
_RUN_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z$")

app = FastAPI()


class RunRequest(BaseModel):
    claim: str
    source_discipline: str | None = None
    live: bool = True


class Correction(BaseModel):
    source_doc_id: str
    axis: str
    target_restatement: str
    source: str = "web"
    timestamp: str | None = None


def _sse(event: str, data: dict) -> str:
    # Padding so uvicorn flushes a stage-start before a long Paperclip call.
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n:{' ' * 2048}\n\n"


def _slots(ctx: TransferContext) -> list[dict]:
    raw = {
        "system": ctx.target_system,
        "state_variable": ctx.state_variable,
        "perturbation": ctx.perturbation,
        "readout": ctx.readout,
        "constraints": "; ".join(ctx.constraints) if ctx.constraints else None,
        "failure_mode": ctx.failure_mode,
        "isolation_unit": ctx.isolation_unit,
    }
    return [{"slot": name, "value": raw[name]} for name in ALIGNMENT_SLOTS]


def _docs(align) -> list[dict]:
    src = {"arx": "arXiv", "bio": "bioRxiv", "PMC": "PMC"}
    return [
        {"doc_id": p.doc_id, "title": p.title, "source": src.get(p.doc_id.split("_")[0], p.doc_id), "label": None}
        for p in align.papers
    ]


def _align(report) -> dict:
    papers = [{"doc_id": p.doc_id, "mapped": p.mapped, "unmapped": p.unmapped, "extraction_quality": p.extraction_quality, "admitted": p.admitted} for p in report.papers]
    breaks = [{"slot": b.slot, "papers_stating": b.papers_stating, "extracted": b.extracted, "target_states_it": b.target_states_it} for b in report.break_points]
    return {"papers": papers, "break_points": breaks, "admitted": len(report.admitted_ids), "held_out": len(report.held_out_ids)}


def replay_saved(out: Path, reason: str) -> Iterator[str]:
    """Emit the committed fixture. Always labelled saved — never as live."""
    out.mkdir(parents=True, exist_ok=True)
    for name in ("context.json", "alignment.json", "ledger.json"):
        shutil.copy(FIXTURES / name, out / name)
    ctx = load_context(out / "context.json")
    align = load_alignment(out / "alignment.json")
    entries = load_entries(out / "ledger.json")
    write_report(render_report(entries, alignment=align, context=ctx), out / "report.html", out / "report.md")
    yield _sse("ingest", {"mode": "saved", "seconds": 0, "slots": _slots(ctx), "reason": reason})
    for doc in _docs(align):
        yield _sse("doc", {"mode": "saved", "doc": doc})
    yield _sse("retrieve", {"mode": "saved", "seconds": 0, "n": len(align.papers), "check": None})
    yield _sse("align", {"mode": "saved", "seconds": 0, **_align(align)})
    for entry in entries:
        yield _sse("entry", {"mode": "saved", "entry": json.loads(entry.model_dump_json())})
    yield _sse("ledger", {"mode": "saved", "seconds": 0, "n": len(entries)})
    yield _sse("report", {"mode": "saved", "seconds": 0, "url": f"/runs/{out.name}/report.html"})


def run_live(req: RunRequest, out: Path) -> Iterator[str]:
    out.mkdir(parents=True, exist_ok=True)
    (out / "claim.txt").write_text(req.claim, encoding="utf-8")
    pin = req.source_discipline or None

    t = time.monotonic()
    yield _sse("stage", {"name": "ingest", "status": "start"})
    ctx = build_context(req.claim)
    if pin:
        ctx = ctx.model_copy(update={"source_discipline_hint": pin})
    write_context(ctx, out / "context.json")
    yield _sse("ingest", {"mode": "live", "seconds": round(time.monotonic() - t, 1), "slots": _slots(ctx)})

    t = time.monotonic()
    yield _sse("stage", {"name": "retrieve", "status": "start"})
    found = retrieve(ctx, source_discipline=pin, workdir=out)
    write_search(found, out / "search.json")
    for doc in found.documents:
        yield _sse("doc", {"mode": "live", "doc": doc.model_dump()})
    check = found.source_leg_check.model_dump() if found.source_leg_check else None
    yield _sse("retrieve", {"mode": "live", "seconds": round(time.monotonic() - t, 1), "n": len(found.documents), "check": check})

    t = time.monotonic()
    yield _sse("stage", {"name": "align", "status": "start"})
    alignment = score_alignment(ctx, found, workdir=out)
    write_alignment(alignment, out / "alignment.json")
    yield _sse("align", {"mode": "live", "seconds": round(time.monotonic() - t, 1), **_align(alignment)})

    t = time.monotonic()
    yield _sse("stage", {"name": "ledger", "status": "start"})
    entries = run_map(ctx, alignment.admitted_ids, found.search_ids, workdir=out).entries if alignment.admitted_ids else []
    write_ledger(entries, out / "ledger.json")
    for entry in entries:
        yield _sse("entry", {"mode": "live", "entry": json.loads(entry.model_dump_json())})
    yield _sse("ledger", {"mode": "live", "seconds": round(time.monotonic() - t, 1), "n": len(entries)})

    t = time.monotonic()
    yield _sse("stage", {"name": "report", "status": "start"})
    write_report(render_report(entries, alignment=alignment, context=ctx), out / "report.html", out / "report.md")
    yield _sse("report", {"mode": "live", "seconds": round(time.monotonic() - t, 1), "url": f"/runs/{out.name}/report.html"})


def pipeline(req: RunRequest) -> Iterator[str]:
    out = default_out()
    saved = "Saved mode. This is a recorded fixture run, not a live pipeline."
    if not req.live:
        yield _sse("start", {"run_id": out.name, "mode": "saved", "reason": saved})
        yield from replay_saved(out, saved)
        return
    yield _sse("start", {"run_id": out.name, "mode": "live"})
    try:
        yield from run_live(req, out)
    except Exception as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        reason = f"Live run failed: {exc}".rstrip(".") + ". Showing a saved fixture run."
        yield _sse("fallback", {"reason": reason, "mode": "saved"})
        yield from replay_saved(out, reason)


@app.post("/api/run")
def api_run(req: RunRequest) -> StreamingResponse:
    return StreamingResponse(
        pipeline(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/runs/{run_id}/corrections")
def api_correct(run_id: str, body: Correction) -> dict:
    path = _run_dir(run_id) / "corrections.json"
    rows = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    row = body.model_dump()
    row["source"] = "web"
    row["timestamp"] = body.timestamp or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    rows.append(row)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "n": len(rows)}


@app.get("/runs/{run_id}/report.html")
def api_report(run_id: str) -> FileResponse:
    path = _run_dir(run_id) / "report.html"
    if not path.is_file():
        raise HTTPException(404, "no report")
    return FileResponse(path)


def _run_dir(run_id: str) -> Path:
    if not _RUN_ID.match(run_id):
        raise HTTPException(404, "unknown run")
    path = (RUNS / run_id).resolve()
    if path.parent != RUNS.resolve():
        raise HTTPException(404, "unknown run")
    return path


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
