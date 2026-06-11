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

## Everyday workflow

Everything defaults to a **safe dry-run**. Add `--execute` only when the tool tells
you to. Run these from the plugin folder
(`...\hermes-agent-main\plugins\hermes-trading-engine`):

1. **Check where you stand** (read-only, always safe):
   ```powershell
   python scripts/laptop_agent.py status
   ```
   Read the bottom three lines: `DECISION:`, `NEXT COMMAND:`, and
   `UPLOAD REPORT TO CHATGPT:`. If it says **STOP**, follow the next command (usually
   `git pull origin main`) until `status` says **SAFE TO CONTINUE**.

2. **Confirm you match GitHub main:**
   ```powershell
   python scripts/laptop_agent.py verify-sync
   ```

3. **(Optional) check your tooling:**
   ```powershell
   python scripts/laptop_agent.py check-docker
   python scripts/laptop_agent.py check-vps --execute
   ```

4. **Bring runtime data over from the VPS** (replaces local `runtime_data`):
   ```powershell
   python scripts/laptop_agent.py collect            # dry-run: shows the command
   python scripts/laptop_agent.py collect --execute  # actually copies
   ```

5. **Build the light-mode inspection report:**
   ```powershell
   python scripts/laptop_agent.py report --execute
   ```
   This runs exactly:
   `python scripts/generate_bot_inspection_report.py --output inspection_reports --data-dir runtime_data --bundle-mode light`

6. **Validate the runtime (never hides a failure):**
   ```powershell
   python scripts/laptop_agent.py validate --execute
   ```
   This runs exactly:
   `python scripts/validate_training_runtime.py --data-dir runtime_data`
   If it says **STOP**, do not proceed — share the output with Cursor.

7. **Package the report and upload it to ChatGPT:**
   ```powershell
   python scripts/laptop_agent.py package --execute
   ```
   Upload the resulting `hermes_inspection_package_<timestamp>.zip` to ChatGPT for an
   independent review.

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
