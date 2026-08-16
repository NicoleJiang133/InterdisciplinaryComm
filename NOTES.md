# NOTES.md — probed Paperclip CLI behaviour

Everything below was run against the live CLI on 2026-08-15, authenticated as
`nicolejiang2324@gmail.com`, server `https://paperclip.gxl.ai`. No behaviour here
is inferred from documentation — each line is what the CLI actually did.

## 1. `paperclip search "data leakage" -s arxiv -n 3 --json`

`--json` is **silently ignored**. Exit code 0, human-readable text on stdout, no JSON:

```
Found 3 papers  [s_7463c7b8]

  1. Data Leakage in Visual Datasets
     Patrick Ramos, Ryan Ramos, Noa Garcia
     arx_2508.17416 · arXiv · 2025

  2. DLPFS: The Data Leakage Prevention FileSystem
     Stefano Braghin and Marco Simioni and Mathieu Sinn
     arx_2108.13785 · arXiv · 2021

  3. Information Leakage in Data Linkage
     Peter Christen and Rainer Schnell and Anushka Vidanage
     arx_2505.08596 · arXiv · 2025

[237ms, saved to s_7463c7b8]

💡 Extract data across these results with: map --from s_7463c7b8 "your question"
[237ms, saved to s_7463c7b8]  [repo: transfer-audit]
```

There is no `--json` in `paperclip search -s arxiv --help`. (`paperclip search --help`
does not even print help — it exits 1 with "Error: search requires a source flag (-s).";
you must run `paperclip search -s arxiv --help`.)

**Consequence for T3:** search output must be either text-parsed for `arx_`/`PMC`/`bio_`/
`med_` ids, or exported with `paperclip results <s_id> --save out.csv`, which writes a
real CSV with full ids:

```
title,authors,id,source,date,url,abstract
Data Leakage in Visual Datasets,"Patrick Ramos, Ryan Ramos, Noa Garcia",arx_2508.17416,arXiv,2025,,
```

## 2. Does `map` support `--json` and `--output-schema` together?

`--output-schema` works. `--json` is not a real flag on `map`, and it is worse than
ignored: **unrecognised flags get swallowed into the query string.** Running

```
paperclip map --from s_7463c7b8 -n 2 --json --output-schema "<schema>" "Identify one validity condition ..."
```

completed 2/2 papers, but `paperclip results m_6cdc3b5c --save` shows the query it
actually ran:

```
Query: --json Identify one validity condition the paper's central result depends on and audit whether it would still hold in a different target system. Use source_doc_id for this paper's id.
```

The `--json` landed inside the prompt. Byte-for-byte the same run without `--json`
produced the same output shape. So: never pass `--json` to `map`; it silently
contaminates the query.

## 3. Does `repo status` support `--json`?

No — and unlike `search`/`map` it fails loudly:

```
Usage: paperclip repo status [OPTIONS]
Try 'paperclip repo status --help' for help.

Error: No such option: --json
EXIT=2
```

`paperclip repo status --help` lists exactly one option: `--help`.

## 4. What does a `map` result look like with `--output-schema`?

### 4a. `--output-schema` takes inline JSON, NOT a file path

BUILD.md section 4 says to "pass that file to `paperclip map --output-schema`". That
does not work. Passing the path produces:

```
ERR: map: invalid output schema: Expecting value: line 1 column 1 (char 0)
[exit 1]
```

i.e. it tried to `json.loads()` the literal string `data/schema/ledger_entry.json`.
The working form is the schema contents inline:

```
paperclip map --from s_xxx --output-schema "$(cat data/schema/ledger_entry.json)" "query"
```

T4 must read `data/schema/ledger_entry.json` off disk and pass the text. The file
itself is still generated from the model and never hand-written.

### 4b. Our pydantic-generated schema is accepted as-is

`LedgerEntry.model_json_schema()` output was accepted without modification —
`additionalProperties: false`, `required`, `enum`, and nullable `anyOf [{type: string},
{type: null}]` all passed. Pydantic does not emit a `$schema` key and Paperclip did
not require one.

### 4c. Shape of stdout

Human-readable text with one JSON object per paper embedded in it. Not JSON overall:

```
Map complete: 2/2 papers
Results ID: m_6cdc3b5c

  ✓ Data Leakage in Visual Datasets
    arx_2508.174 · 2469ms
    {"axis": "C_domain_of_validity", "evidence_lines": "L99-L100", "rationale": "...", "source_assumption": "...", "source_doc_id": "Data Leakage in Visual Datasets", "status": "VIOLATED", "subtype": "C1", "target_restatement": "...", "what_would_resolve_it": "..."}

  ✓ DLPFS: The Data Leakage Prevention FileSystem
    arx_2108.137 · 2162ms
    {"axis":"C_domain_of_validity", ...}

Tip: These per-paper answers are ready to use — synthesize them to respond.
[4.0s, saved to m_6cdc3b5c]
```

Two traps in that display, both of which corrupt provenance if trusted:

1. **The doc ids on screen are truncated.** `arx_2508.174` is really `arx_2508.17416`;
   `arx_2108.137` is really `arx_2108.13785`.
2. **The model filled `source_doc_id` with the paper title**, not the id — it wrote
   `"source_doc_id": "Data Leakage in Visual Datasets"`. The schema cannot stop this.
   T4 should overwrite `source_doc_id` with the id it already knows from the search
   step rather than trusting the map output.

The clean route for both is `paperclip results <m_id> --save out.txt`, which writes
untruncated ids next to each JSON payload:

```
--- [1] [success] Data Leakage in Visual Datasets ---
doc_id: arx_2508.17416
{"axis": "C_domain_of_validity", ...}
```

Timing: 2 papers in ~4.0s wall, ~2.2-2.5s per paper. The 3-10 paper cap in BUILD.md
looks comfortable for the 4-minute demo budget.

## 5. Cross-cutting: errors go to stdout and the exit code is 0

This is the most dangerous finding for `pc()`. A failing `map`:

```
$ paperclip map --from s_7463c7b8 --output-schema data/schema/ledger_entry.json "x" 2>/dev/null; echo "EXIT=$?"
EXIT=0
ERR: map: invalid output schema: Expecting value: line 1 column 1 (char 0)
[exit 1]
```

The real failure is reported as the *text* `[exit 1]` on **stdout** while the process
exits **0**. `returncode` is therefore useless for detecting failure, and since
BUILD.md tells us to ignore stderr, callers must look for a leading `ERR:` in the
returned string. `pc()` deliberately does not do this itself — it is a transport, and
the spec gives it no error contract — so T3/T4 must check. (`repo status --json` is the
exception: Click-level argument errors do exit non-zero, with 2.)

## 6. No probed command emits JSON on stdout

`search`, `map`, and `repo status` all return prose. `pc()` therefore does no JSON
parsing at all: it returns `str` and raises `PaperclipError` on `ERR:` or a non-zero
exit. BUILD.md section 4 has been updated to match.

## 7. Pre-existing account state, left untouched

`paperclip repo status` shows a repo already active:

```
  On repo transfer-audit  branch main
  1 paper, 1 commit

  [?] 2207.07048
    claim: 17 fields, 329 papers affected by data leakage
```

That repo appears in the footer of every search (`[repo: transfer-audit]`). It looks
human-created around the ground-truth source paper, and the Paperclip skill says not to
add papers to a repo on the agent's own initiative, so nothing was written to it. Worth
knowing that repo state is sticky and global to the account, not per-directory.

## 8. There is no LLM-over-arbitrary-text primitive (blocks T2 as specified)

BUILD.md T2 asks for "one call that fills the slots" from a free-text target
description. No Paperclip command on this account can do that. Three routes probed,
all dead ends:

**8a. `generate-search-config` — disabled server-side.** It is the only command that
takes arbitrary proposal text (`.md`/`.txt`) as input:

```
$ paperclip generate-search-config tests/fixtures/target_claim.txt -o /tmp/gsc.yaml --force
...
gxl_paperclip.client.errors.ForbiddenError: Curation search is currently disabled.
EXIT=1
```

Note the shape of this failure: traceback on **stderr**, empty stdout, exit **1**. It is
caught by the `returncode != 0` half of the new `pc()` contract, not the `ERR:` half —
both halves are needed.

**8b. `map`/`filter`/`reduce` only accept corpus search-result sets.** `map --from`
requires an `s_*` id; `reduce --from` requires an `m_*` id. Neither accepts raw text.
The query string is free text, but the reader is grounded on whatever papers are in the
result set, so smuggling the claim into the query contaminates the extraction with an
unrelated paper. Not used.

**8c. Upload to `/clipboard/` is searchable but not map-readable.** The upload itself
works and the document is parsed:

```
$ paperclip upload /tmp/ta_probe_claim.md --into analyses/transfer-audit-probe
  ✓ ta_probe_claim.md → /clipboard/analyses/transfer-audit-probe/
$ paperclip search -s clipboard -t "ta_probe_claim" -n 1
Found 1 papers  [s_27f19c15]
  1. ta_probe_claim.md
     usr_d0c7e8bfbfad · clipboard · 2026-08-16
$ paperclip cat /clipboard/analyses/transfer-audit-probe/usr_d0c7e8bfbfad/content.lines
L1: A random-forest classifier trained on resting-state fMRI connectivity matrices
...
```

`-s clipboard` is a valid source even though it is absent from the `-s` list in
`--help`. But `map` refuses the document:

```
Map complete: 0/1 papers
  ✗ Untitled
    error: Stale or unavailable search result: usr_d0c7e8bfbfad has no loadable full text.
```

Retried 45s later against a fresh search id — identical failure, so this is not an
indexing lag. Clipboard uploads are readable by `cat`/`search` and invisible to the map
worker.

Consequence: `ingest.py` extracts deterministically from the text and calls no
Paperclip command. Every slot it emits is a verbatim span of the input; unmatched slots
are None. `build_context()` is the single seam to swap in a model if one appears.

**Side effect to clean up:** the 8c probe left `/clipboard/analyses/transfer-audit-probe/`
in the account. `rm` is blocked in the Paperclip sandbox (`ERR: vsh: cp: permission
denied` for `cp`, and there is no delete verb), so clipboard uploads accumulate. That is
a second reason not to build ingest on upload: one clipboard document per run, forever.

## 9. The live CLI depends on the real $HOME

Proven: `/Users/Nicole/.local/bin/paperclip` imports its library from
`$HOME/.paperclip/lib`, so anything that changes or hides the home directory kills it
before it reaches the network:

```
$ HOME=/var/empty paperclip search "x" -s arxiv -n 1
ModuleNotFoundError: No module named 'gxl_paperclip'
REAL_EXIT=1        stdout: 0 bytes        traceback on stderr
```

Empty stdout, non-zero exit — the returncode half of the `pc()` contract catches it.
Worth knowing that this failure mode writes nothing to stdout at all, so a transport
that only checked for `ERR:` would return an empty string and look successful.

Not proven: the integration test failed twice, both times in a restricted sandbox
(once with the filesystem confined to the repo, once with that plus a network
allowlist), and passed on eleven runs outside it. The error text was not captured at
the time, so the specific cause — blocked writes to `~/.paperclip` versus a blocked
route to paperclip.gxl.ai — is still a guess. Either way the CLI needs a real home
directory and unrestricted access to the server. The unit tests are hermetic
(subprocess is monkeypatched); only the `@pytest.mark.integration` test needs both.
