"""Paperclip access layer.

Every Paperclip call in the codebase goes through `pc()`. No exceptions.
Auth comes from the ambient OAuth session — never pass an API key as an argument.

Behaviour notes that callers depend on are recorded in NOTES.md; the two that
bite hardest: the CLI prints errors to stdout and still exits 0, and no command
probed so far emits JSON on stdout, so `pc()` returns a string in practice.
"""

from __future__ import annotations

import json
import subprocess

BIN = "paperclip"


def pc(*args: str, timeout: int = 300) -> dict | str:
    """Run `paperclip <args>` and return parsed JSON if stdout is a JSON object, else raw stdout.

    stderr is ignored entirely — the CLI emits a NotOpenSSLWarning there on every call.
    """
    proc = subprocess.run(
        [BIN, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    stdout = proc.stdout
    try:
        parsed = json.loads(stdout)
    except ValueError:
        return stdout
    return parsed if isinstance(parsed, dict) else stdout
