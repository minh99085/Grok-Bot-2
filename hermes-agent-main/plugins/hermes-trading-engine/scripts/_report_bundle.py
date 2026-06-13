#!/usr/bin/env python3
"""Build the COMPLETE VPS light-report zip (testable, no shell globbing).

The thin-zip bug was caused by zipping only the top-level ``inspection_reports`` dir
(which can end up as empty skeleton folders) and never including a git-commit proof.
This module collects the FULL generated light bundle — report.json / report.md, all
inspection metric files, logs + samples tail files, validation output,
runtime_data/metrics, final_validation.json / validation_contract.json, and a written
git commit proof — and VERIFIES the bundle is complete before writing the zip. If the
report bundle is missing its core artifacts it FAILS (rc 13) so a thin/broken zip is
never shipped as success.

Pure/IO-only; never touches trading logic. Importable for tests + runnable as a CLI from
the VPS runner.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

# Core artifacts the bundle MUST contain to count as a complete light report. These are
# all written UNCONDITIONALLY by scripts/generate_bot_inspection_report.py into the
# bundle dir, so a bundle missing any of them is a thin/broken zip and must be REFUSED
# (this is what catches the repeated ~39 KB thin zip).
REQUIRED_BUNDLE_FILES = ("report.json", "report.md", "final_validation.json",
                         "algorithmic_edge_audit.json", "validation_contract.json")
# Extra report artifacts to include wherever they are found (best-effort).
EXTRA_REPORT_FILES = ("validation_contract.json", "final_validation.json",
                      "algorithmic_edge_audit.json")
GIT_PROOF_NAME = "git_commit_proof.txt"


def latest_bundle_dir(inspection_reports: Path):
    """The most-recent ``bot_inspection_*`` bundle dir under inspection_reports (or the
    dir itself if it directly holds report.json). None if nothing usable."""
    if not inspection_reports.is_dir():
        return None
    subs = [p for p in inspection_reports.iterdir() if p.is_dir()]
    if subs:
        return max(subs, key=lambda p: p.stat().st_mtime)
    if (inspection_reports / "report.json").is_file():
        return inspection_reports
    return None


def verify_bundle_complete(bundle_dir):
    """Return (ok, missing[]). A complete light bundle has every REQUIRED_BUNDLE_FILES
    artifact AND at least one samples tail file AND at least one inspection metrics file
    (so a thin 4-file zip can never pass as complete)."""
    if bundle_dir is None or not Path(bundle_dir).is_dir():
        return False, ["<no bundle dir>", *REQUIRED_BUNDLE_FILES]
    bd = Path(bundle_dir)
    missing = [f for f in REQUIRED_BUNDLE_FILES if not (bd / f).is_file()]
    samples = bd / "samples"
    if not (samples.is_dir() and any(p.is_file() for p in samples.rglob("*"))):
        missing.append("samples/<tail sample>")
    metrics = bd / "metrics"
    if not (metrics.is_dir() and any(p.suffix == ".json" for p in metrics.rglob("*"))):
        missing.append("metrics/<inspection metric>")
    return (not missing), missing


def write_git_proof(plugin_dir: Path, dest: Path, *, runner=None) -> bool:
    """Write a git commit proof (HEAD, branch, status, last commit, origin/main) so the
    uploaded report proves exactly which code produced it. Never raises."""
    run = runner or (lambda args: subprocess.run(
        args, cwd=str(plugin_dir), capture_output=True, text=True, timeout=30))
    lines = ["# Hermes git commit proof"]
    for label, args in (("HEAD", ["git", "rev-parse", "HEAD"]),
                        ("branch", ["git", "rev-parse", "--abbrev-ref", "HEAD"]),
                        ("last_commit", ["git", "log", "-1", "--oneline"]),
                        ("status_porcelain", ["git", "status", "--porcelain"]),
                        ("origin_main", ["git", "ls-remote", "origin", "refs/heads/main"])):
        try:
            res = run(args)
            out = (getattr(res, "stdout", "") or "").strip()
            lines.append(f"{label}: {out}")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"{label}: <error: {type(exc).__name__}>")
    try:
        dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


def collect_bundle_files(plugin_dir: Path, bundle_dir: Path, *, extra_paths=()) -> list:
    """Collect every file that belongs in the complete light-report zip. Returns a list
    of (abs_path, arcname) — arcname is relative to plugin_dir so the zip is portable."""
    plugin_dir = Path(plugin_dir)
    seen = set()
    out = []

    def _add(p: Path):
        p = Path(p)
        if not p.is_file():
            return
        rp = p.resolve()
        if rp in seen:
            return
        seen.add(rp)
        try:
            arc = str(p.resolve().relative_to(plugin_dir.resolve()))
        except ValueError:
            arc = p.name
        out.append((str(p), arc))

    def _add_tree(d: Path):
        d = Path(d)
        if d.is_dir():
            for f in sorted(d.rglob("*")):
                if f.is_file():
                    _add(f)

    # 1) the FULL generated bundle (report.json/md, logs, samples, metric files, …)
    _add_tree(bundle_dir)
    # 2) runtime metrics the report is built from
    _add_tree(plugin_dir / "runtime_data" / "metrics")
    _add(plugin_dir / "runtime_data" / "inspection_summary.json")
    # 3) validation output + report logs
    _add(plugin_dir / "validation_light_latest.txt")
    _add_tree(plugin_dir / "report_logs")
    # 4) top-level metrics dir (if the engine writes there)
    _add_tree(plugin_dir / "metrics")
    # 5) extra report artifacts wherever they exist (best-effort, skip the venv)
    for name in EXTRA_REPORT_FILES:
        for f in plugin_dir.rglob(name):
            if ".report_venv" not in f.parts and ".venv" not in f.parts:
                _add(f)
    # 6) caller-supplied extras (e.g. the git proof)
    for p in extra_paths:
        _add(Path(p))
    return out


def build_report_bundle_zip(plugin_dir, dest_zip, *, runner=None) -> dict:
    """Write the complete light-report zip. Writes a git proof, VERIFIES the bundle is
    complete (report.json + report.md), then zips everything. Returns a result dict;
    ``ok=False`` (and an empty/partial zip is NOT declared success) when the bundle is
    incomplete so a thin zip is never shipped silently."""
    plugin_dir = Path(plugin_dir)
    dest_zip = Path(dest_zip)
    bundle_dir = latest_bundle_dir(plugin_dir / "inspection_reports")
    proof = plugin_dir / GIT_PROOF_NAME
    write_git_proof(plugin_dir, proof, runner=runner)

    ok, missing = verify_bundle_complete(bundle_dir)
    files = collect_bundle_files(plugin_dir, bundle_dir, extra_paths=[proof])
    arcnames = [a for _p, a in files]
    if not ok:
        return {"ok": False, "reason": "incomplete_bundle", "missing": missing,
                "bundle_dir": (str(bundle_dir) if bundle_dir else None),
                "file_count": len(files), "arcnames": arcnames, "zip": None}
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, arc in files:
            zf.write(p, arcname=arc)
    has_report = any(a.endswith("report.json") for a in arcnames)
    return {"ok": True, "bundle_dir": str(bundle_dir), "file_count": len(files),
            "arcnames": arcnames, "zip": str(dest_zip),
            "size_bytes": dest_zip.stat().st_size, "has_report_json": has_report}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="_report_bundle",
                                 description="Build the complete VPS light-report zip.")
    ap.add_argument("--plugin", default=".", help="plugin dir (default: cwd)")
    ap.add_argument("--out", required=True, help="destination zip path")
    args = ap.parse_args(argv)
    res = build_report_bundle_zip(Path(args.plugin), Path(args.out))
    if not res["ok"]:
        print(f"FATAL: report bundle incomplete (missing={res.get('missing')}); "
              f"refusing to ship a thin zip.", file=sys.stderr)
        return 13
    print(f"report bundle OK: {res['file_count']} files, "
          f"{res['size_bytes']} bytes -> {res['zip']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
