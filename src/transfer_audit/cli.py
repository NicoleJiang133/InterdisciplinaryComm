"""T6 — typer entry point.

Two operations only: a live `run --claim-file` and an offline `run --replay`.
`--replay` is the demo safety net. It re-renders HTML and Markdown from a saved
run and must not call Paperclip or Anthropic. `score` and `answer` are not built.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from transfer_audit.align import score_alignment, write_alignment
from transfer_audit.ingest import build_context_from_file, write_context
from transfer_audit.ledger import run_map, write_ledger
from transfer_audit.report import (
    load_alignment,
    load_context,
    load_entries,
    render_report,
    write_report,
)
from transfer_audit.retrieve import retrieve, write_search

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Generate an assumption ledger for a claim borrowed across disciplines.",
)


@app.callback()
def _root() -> None:
    """Generate an assumption ledger for a claim borrowed across disciplines."""
    return None


def default_out() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("runs") / stamp


def replay_run(run_dir: Path) -> tuple[Path, Path]:
    """Re-render both reports from a saved run. No network."""
    run_dir = Path(run_dir)
    ledger_path = run_dir / "ledger.json"
    if not ledger_path.is_file():
        typer.echo(f"no ledger.json in {run_dir}", err=True)
        raise typer.Exit(code=2)

    entries = load_entries(ledger_path)
    context = None
    alignment = None
    ctx_path = run_dir / "context.json"
    align_path = run_dir / "alignment.json"
    if ctx_path.is_file():
        context = load_context(ctx_path)
    if align_path.is_file():
        alignment = load_alignment(align_path)

    rendered = render_report(entries, alignment=alignment, context=context)
    return write_report(rendered, run_dir / "report.html", run_dir / "report.md")


def execute_run(
    claim_file: Path,
    out: Path,
    source_discipline: str | None = None,
) -> Path:
    """Ingest → retrieve → align → ledger → report. Writes into `out`."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    claim_file = Path(claim_file)
    (out / "claim.txt").write_text(claim_file.read_text(encoding="utf-8"), encoding="utf-8")

    ctx = build_context_from_file(claim_file)
    if source_discipline:
        ctx = ctx.model_copy(update={"source_discipline_hint": source_discipline})
    write_context(ctx, out / "context.json")

    found = retrieve(ctx, source_discipline=source_discipline, workdir=out)
    write_search(found, out / "search.json")

    alignment = score_alignment(ctx, found, workdir=out)
    write_alignment(alignment, out / "alignment.json")

    entries = []
    if alignment.admitted_ids:
        entries = run_map(
            ctx, alignment.admitted_ids, found.search_ids, workdir=out
        ).entries
    write_ledger(entries, out / "ledger.json")

    rendered = render_report(entries, alignment=alignment, context=ctx)
    write_report(rendered, out / "report.html", out / "report.md")
    return out


@app.command()
def run(
    claim_file: Optional[Path] = typer.Option(
        None,
        "--claim-file",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to the claim text.",
    ),
    replay: Optional[Path] = typer.Option(
        None,
        "--replay",
        exists=True,
        file_okay=False,
        help="Re-render reports from a saved run. No network call.",
    ),
    source_discipline: Optional[str] = typer.Option(
        None,
        "--source-discipline",
        help="Pin the T3 source-leg discipline.",
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        help="Run directory. Defaults to runs/<UTC timestamp>.",
    ),
) -> None:
    if claim_file is not None and replay is not None:
        typer.echo("provide exactly one of --claim-file or --replay", err=True)
        raise typer.Exit(code=2)
    if claim_file is None and replay is None:
        typer.echo("provide --claim-file or --replay", err=True)
        raise typer.Exit(code=2)

    if replay is not None:
        if source_discipline:
            typer.echo("--source-discipline does not apply to --replay", err=True)
            raise typer.Exit(code=2)
        html, md = replay_run(replay)
        typer.echo(f"replay (offline): wrote {html}")
        typer.echo(f"replay (offline): wrote {md}")
        return

    dest = execute_run(claim_file, out or default_out(), source_discipline=source_discipline)
    typer.echo(f"wrote {dest / 'report.html'}")
    typer.echo(f"wrote {dest / 'report.md'}")


if __name__ == "__main__":
    app()
