"""Paperclip access layer.

Every Paperclip call in the codebase goes through `pc()`. No exceptions.
Auth comes from the ambient OAuth session — never pass an API key as an argument.

The CLI reports real failures as text on stdout while exiting 0 (see NOTES.md
section 5), so `pc()` inspects stdout as well as the return code.
"""

from __future__ import annotations

import subprocess

BIN = "paperclip"
ERROR_PREFIX = "ERR:"


class PaperclipError(RuntimeError):
    """A paperclip invocation failed, by exit code or by an ERR: line on stdout."""


def pc(*args: str, timeout: int = 300) -> str:
    """Run `paperclip <args>` and return stdout.

    stderr is ignored entirely — the CLI emits a NotOpenSSLWarning there on every call.
    Raises PaperclipError if stdout starts with 'ERR:' or the process exits non-zero.
    """
    proc = subprocess.run(
        [BIN, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    stdout = proc.stdout

    if stdout.lstrip().startswith(ERROR_PREFIX):
        raise PaperclipError(f"paperclip {' '.join(args)} failed: {stdout.strip()}")
    if proc.returncode != 0:
        raise PaperclipError(
            f"paperclip {' '.join(args)} exited {proc.returncode}: {stdout.strip()}"
        )
    return stdout
