"""T6 — typer entry point.

Live `run --claim-file`, offline `run --replay`, `sync --run` for markdown
corrections, and `serve` for the local UI. `--replay` re-renders HTML and
Markdown from a saved run and must not call Paperclip or Anthropic.
`--report-out` copies report.md into a Sundial workspace folder.
`score` and `answer` are not built.
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
from transfer_audit.sync import format_sync_summary, sync_run

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


def _write_report_out(markdown: str, report_out: Path | None) -> Path | None:
    """Copy report.md into a Sundial workspace folder. No-op when unset."""
    if report_out is None:
        return None
    dest_dir = Path(report_out)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "report.md"
    dest.write_text(markdown, encoding="utf-8")
    return dest


def replay_run(
    run_dir: Path, report_out: Path | None = None
) -> tuple[Path, Path, Path | None]:
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
    html, md = write_report(rendered, run_dir / "report.html", run_dir / "report.md")
    handed = _write_report_out(rendered.markdown, report_out)
    return html, md, handed


def execute_run(
    claim_file: Path,
    out: Path,
    source_discipline: str | None = None,
    report_out: Path | None = None,
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
    _write_report_out(rendered.markdown, report_out)
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
    report_out: Optional[Path] = typer.Option(
        None,
        "--report-out",
        help="Also write report.md into this folder (a Sundial workspace).",
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
        html, md, handed = replay_run(replay, report_out=report_out)
        typer.echo(f"replay (offline): wrote {html}")
        typer.echo(f"replay (offline): wrote {md}")
        if handed is not None:
            typer.echo(f"replay (offline): wrote {handed}")
        return

    dest = execute_run(
        claim_file,
        out or default_out(),
        source_discipline=source_discipline,
        report_out=report_out,
    )
    typer.echo(f"wrote {dest / 'report.html'}")
    typer.echo(f"wrote {dest / 'report.md'}")
    if report_out is not None:
        typer.echo(f"wrote {Path(report_out) / 'report.md'}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address. Localhost only."),
    port: int = typer.Option(8000, help="Port."),
    open_browser: bool = typer.Option(True, "--open/--no-open"),
) -> None:
    """Open the local product UI at http://localhost:8000."""
    import os

    try:
        import uvicorn
    except ImportError:
        typer.echo("install the web extra: pip install -e '.[web]'", err=True)
        raise typer.Exit(code=1)
    if host not in {"127.0.0.1", "localhost"}:
        typer.echo("bind to 127.0.0.1 only", err=True)
        raise typer.Exit(code=2)

    from transfer_audit.models import REPO_ROOT

    os.chdir(REPO_ROOT)
    env_path = REPO_ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))

    url = f"http://{host}:{port}"
    if open_browser:
        import webbrowser

        webbrowser.open(url)
    typer.echo(url)
    uvicorn.run("transfer_audit.server:app", host=host, port=port, log_level="info")


@app.command()
def sync(
    run: Path = typer.Option(
        ...,
        "--run",
        exists=True,
        file_okay=False,
        help="Run directory containing ledger.json and report.md.",
    ),
    report: Optional[Path] = typer.Option(
        None,
        "--report",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Markdown to read. Defaults to <run>/report.md.",
    ),
) -> None:
    """Read target-restatement edits out of report.md into corrections.json."""
    try:
        result = sync_run(run, report=report)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(format_sync_summary(result), nl=False)


if __name__ == "__main__":
    app()
