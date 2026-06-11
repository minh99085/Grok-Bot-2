# Laptop Hermes Agent — Operator Workflow (Phase 1)

This guide is for the **human operator** running Hermes from a laptop. You do **not**
need to be a coder. The tool (`scripts/laptop_agent.py`) automates the boring,
repeatable chores and tells you, in plain language, whether it is **SAFE TO
CONTINUE** or you should **STOP**, plus the exact next command to run.

## Who does what

| Role | Responsibility |
| --- | --- |
| **GitHub `main`** | The single source of truth for code. |
| **Cursor** | The code engineer (makes changes, opens PRs). |
| **ChatGPT** | An independent judge that reviews the inspection report you upload. |
| **Vultr VPS** | The paper-trading runtime that produces `runtime_data`. |
| **This laptop tool** | Operator chores only — status, sync checks, collecting artifacts, building & packaging the report. |

> The laptop tool **never trades, never loosens any gate, never changes paper-realism
> or live-safety controls, and never auto-prompts Cursor/ChatGPT.** It cannot.

## One-time setup

1. Make a local config (it is **git-ignored** and never committed):
   ```powershell
   copy .laptop_agent.example.json .laptop_agent.local.json
   notepad .laptop_agent.local.json
   ```
   Fill in your VPS host, user, SSH key path, and the `runtime_source` path.
   (You can instead create `.env.laptop_agent` with `LAPTOP_AGENT_*` keys.)

2. Confirm the tool runs:
   ```powershell
   python scripts/laptop_agent.py --help
   ```

## Everyday workflow (the short version)

Everything defaults to a **safe dry-run**. Add `--execute` only when the tool tells
you to. Run these from the plugin folder
(`...\hermes-agent-main\plugins\hermes-trading-engine`):

1. **See where you stand** (read-only, always safe):
   ```powershell
   python scripts/laptop_agent.py status --dry-run
   ```
   If it says **STOP**, follow the `NEXT COMMAND:` (usually `git pull origin main`)
   until it says **SAFE TO CONTINUE**.

2. **Bring runtime data over from the VPS** (only when you need fresh data):
   ```powershell
   python scripts/laptop_agent.py collect --dry-run   # shows the method it will use
   python scripts/laptop_agent.py collect --execute
   ```

3. **Build a fresh, provenance-verified package** (the one command to remember):
   ```powershell
   python scripts/laptop_agent.py fresh-package --dry-run    # preview the steps
   python scripts/laptop_agent.py fresh-package --execute    # do it for real
   ```

4. **Upload the printed zip to ChatGPT** for an independent review. The exact path is
   printed on the `PACKAGE:` / `UPLOAD REPORT TO CHATGPT:` line.

> **Always use `fresh-package`, not `package`, to build an upload.** `fresh-package`
> refuses a dirty or behind/ahead repo, archives any old `inspection_reports`,
> regenerates the report, validates it, proves freshness, and writes a
> `laptop_agent_package_provenance.json` *inside* the zip so the upload can prove it
> came from the current clean `origin/main` state.

## What `fresh-package --execute` does (in order)

1. **Refuses** if the repo is dirty or your local HEAD ≠ `origin/main`.
2. **Archives** any existing `inspection_reports/` to a git-ignored
   `_stale_inspection_reports_<timestamp>/` (old evidence is never reused).
3. Runs the light-mode report:
   `python scripts/generate_bot_inspection_report.py --output inspection_reports --data-dir runtime_data --bundle-mode light`
4. Runs validation:
   `python scripts/validate_training_runtime.py --data-dir runtime_data`
5. Verifies the report/validation pair is fresh (validation ran *after* the report,
   git evidence matches the current HEAD).
6. Writes `laptop_agent_package_provenance.json` and creates a timestamped zip.
7. Prints the exact zip path to upload.

## Collecting runtime data on Windows (rsync vs scp)

`collect` copies `runtime_data` from the VPS and **replaces** your local copy. It
picks a transport automatically:

* **`rsync`** — used when it is on your `PATH` (Linux/macOS, or Windows with
  WSL/cwRsync). Mirrors the source with `--delete`.
* **`scp`** (the built-in Windows **OpenSSH client**) — used automatically when
  `rsync` is missing. This is the normal path on a stock Windows laptop in
  PowerShell — **no Git Bash, WSL, or cwRsync required**. Because `scp` has no
  `--delete`, the tool first **clears your local `runtime_data`**, then copies fresh
  (only with `--execute`; `--dry-run` deletes nothing).

`collect --dry-run` prints which method it selected and the exact (secret-redacted)
command it would run. If **neither** `rsync` nor `scp` exists, it **STOPs** and tells
you to enable the OpenSSH Client:
`Settings > Apps > Optional features > Add a feature > OpenSSH Client`.

It uses your configured `vps_ssh_key`, `vps_port`, and `runtime_source`, and never
prints the key path, host, or private-key contents.

## The lower-level commands (advanced)

`status`, `verify-sync`, `local-head`, `remote-head`, `check-docker`,
`check-vps --execute`, `collect --execute`, `report --execute`,
`validate --execute`, and `package --execute` are still available.

> **Do not use `package` on its own** unless `status` is **SAFE** and the report's
> provenance is fresh. By default `package --execute` **refuses** to zip a stale
> report — it STOPs if the report is missing, has no provenance, the repo is dirty,
> your HEAD differs from `origin/main`, the report's git evidence doesn't match your
> current HEAD, or validation didn't run after the report. (`--allow-stale-package`
> exists only as a deliberate, risky override.)

## Safety rules built into the tool

* **Dry-run is the default.** Nothing that touches the VPS or replaces `runtime_data`
  runs without `--execute`.
* **Secrets never printed, never committed.** VPS host/user/key and the runtime
  source are loaded from the git-ignored local config and are masked in all output.
* **Validation failures are never hidden** — a failed `validate` prints `STOP`.
* The tool has **no trading code path** and cannot change strategy, gates, or
  live-safety settings.

## Troubleshooting

* *"No local operator config found"* — you skipped one-time setup; copy the example
  file as shown above. (Read-only commands like `status`/`check-docker` still work.)
* *`remote-head` shows `unknown`* — no network or the remote is unreachable.
* *`check-vps` STOP* — verify the host/key in your local config and that the VPS is up.
