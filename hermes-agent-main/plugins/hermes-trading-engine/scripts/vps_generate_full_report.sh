#!/usr/bin/env bash
# Canonical VPS FULL diagnostic report (PAPER ONLY) for the Hermes Trading Engine.
#
#   bash scripts/vps_generate_full_report.sh
#
# This is the superset of the light report: it runs the canonical, self-bootstrapping
# light-report runner (which uses a dedicated .report_venv — NEVER system `python`), then
# captures the operational diagnostics an inspector needs (docker compose config/ps,
# the running container's 100X paper-profile env proof, and a git commit/status proof),
# and packages everything — including the complete light bundle — into ONE timestamped
# zip plus vps_full_report_latest.zip.
#
# WHY THIS SCRIPT EXISTS: ad-hoc "full report" commands invoked bare `python`, which does
# not exist on a python3-only VPS ("Command 'python' not found"), so the full-report and
# full-validation steps silently produced nothing. This script ONLY ever uses the report
# venv's python (or python3) — never bare `python` — so it cannot hit that failure.
#
# It does NOT change trading flags, gates, paper-realism, Docker topology, or live-trading
# behavior, never places an order, and never prints secret VALUES (only key presence).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PLUGIN_DIR}"

CONTAINER="${HERMES_TRAINING_CONTAINER:-hermes-training}"
VENV="${PLUGIN_DIR}/.report_venv"
VPY="${VENV}/bin/python"
TS="$(date -u +%Y%m%d_%H%M%S)"
OUT_DIR="${PLUGIN_DIR}/vps_full_report_${TS}"
ZIP_NAME="vps_full_report_${TS}.zip"
ZIP_LATEST="vps_full_report_latest.zip"
LIGHT_ZIP="vps_light_report_latest.zip"

# Delete the stale latest BEFORE generation so a FAILED run can never leave a stale full
# report for an inspector to grab; a fresh latest is written only after success.
rm -f "${ZIP_LATEST}"
mkdir -p "${OUT_DIR}/runtime_metrics"

echo "==> Hermes VPS FULL diagnostic report"
echo "    plugin   : ${PLUGIN_DIR}"
echo "    container: ${CONTAINER}"
echo "    out      : ${OUT_DIR}"

# --- 1) canonical light bundle (self-bootstraps .report_venv; venv python ONLY) -----
# This is the authoritative, complete bundle. It exits nonzero (and ships NO thin zip)
# if the bundle is incomplete; we propagate that failure.
echo "==> running canonical light-report runner (scripts/vps_generate_light_report.sh)"
set +e
bash "${SCRIPT_DIR}/vps_generate_light_report.sh" 2>&1 | tee "${OUT_DIR}/generate_full_report.txt"
LIGHT_RC=${PIPESTATUS[0]}
set -e
echo "light_report_rc=${LIGHT_RC}" | tee -a "${OUT_DIR}/generate_full_report.txt"

# pick the venv python the light runner just created; fall back to python3 (NEVER python).
if [[ ! -x "${VPY}" ]]; then
  VPY="$(command -v python3 || true)"
fi
if [[ -z "${VPY}" ]]; then
  echo "FATAL: no python3 / report venv available for full-report validation." >&2
  exit 3
fi

# --- 2) full validation (venv python ONLY — this is what the broken ad-hoc missed) --
echo "==> training-runtime validation (venv python: ${VPY})"
set +e
"${VPY}" scripts/validate_training_runtime.py --data-dir runtime_data \
    2>&1 | tee "${OUT_DIR}/validation_full.txt"
VALIDATE_RC=${PIPESTATUS[0]}
set -e
echo "validate_rc=${VALIDATE_RC}" | tee -a "${OUT_DIR}/validation_full.txt"

# --- 3) operational diagnostics (read-only; no flag/topology changes) ---------------
echo "==> docker compose config -q"
docker compose config -q > "${OUT_DIR}/docker_compose_config_check.txt" 2>&1 || true
echo "==> docker compose ps"
docker compose ps > "${OUT_DIR}/docker_compose_ps.txt" 2>&1 || true

echo "==> git commit + status proof"
git rev-parse HEAD > "${OUT_DIR}/git_commit.txt" 2>&1 || true
git status --porcelain > "${OUT_DIR}/git_status.txt" 2>&1 || true

# --- 4) running-container 100X paper-profile env PROOF (presence only, no secrets) --
# Prove the effective container env carries the aggressive 100X paper profile and that
# every live/real-money flag is OFF. XAI_API_KEY is reported as presence ONLY.
echo "==> ${CONTAINER} env proof (100X paper profile + live-off; secret values masked)"
{
  CENV="$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${CONTAINER}" 2>/dev/null || true)"
  for K in AGGRESSIVE_PAPER_TRAINING PAPER_PROFIT_DISCOVERY_PROFILE HERMES_ACCELERATED_DISCOVERY \
           FEEDBACK_ACCELERATOR_ENABLED FEEDBACK_ACCELERATOR_TARGET_MULTIPLIER \
           POLYMARKET_ACTIVE_LEARNING_ENABLED POLYMARKET_EXPLORATION_ENABLED \
           EXPLORATION_TINY_SIZE_ENABLED NEWS_SCANNER_ENABLED NEWS_PROVIDER_MODE \
           MICRO_LIVE_ENABLED POLYMARKET_MICRO_LIVE_ENABLED GUARDED_LIVE_ENABLED \
           BTC_AUTOTRADE_ENABLED LIVE_TRADING_ENABLED POLYMARKET_LIVE_ENABLED; do
    VAL="$(printf '%s\n' "${CENV}" | grep -E "^${K}=" | head -1 | cut -d= -f2- || true)"
    echo "${K}=${VAL}"
  done
  # secret: presence only, never the value
  if printf '%s\n' "${CENV}" | grep -qE '^XAI_API_KEY=.+'; then
    echo "XAI_API_KEY_PRESENT=true"
  else
    echo "XAI_API_KEY_PRESENT=false"
  fi
} > "${OUT_DIR}/hermes_training_env_proof.txt" 2>&1 || true

# --- 5) collect the durable runtime metrics the report is built from ----------------
echo "==> copying runtime_data/metrics into the full report"
if [[ -d runtime_data/metrics ]]; then
  cp -f runtime_data/metrics/*.json runtime_data/metrics/*.jsonl "${OUT_DIR}/runtime_metrics/" 2>/dev/null || true
fi
cp -f validation_light_latest.txt "${OUT_DIR}/" 2>/dev/null || true

# --- 6) embed the complete light bundle + record its size/listing -------------------
if [[ -s "${LIGHT_ZIP}" ]]; then
  cp -f "${LIGHT_ZIP}" "${OUT_DIR}/"
  wc -c < "${LIGHT_ZIP}" | sed 's/^/light_zip_size_bytes=/' > "${OUT_DIR}/latest_zip_size.txt"
  "${VPY}" - "${LIGHT_ZIP}" > "${OUT_DIR}/latest_zip_listing.txt" 2>&1 <<'PYZIP' || true
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    for n in z.namelist():
        print(n)
PYZIP
else
  echo "WARNING: ${LIGHT_ZIP} missing (light report failed rc=${LIGHT_RC}) — full report is" \
       "incomplete." | tee -a "${OUT_DIR}/generate_full_report.txt"
fi

# --- 7) package the full report -----------------------------------------------------
echo "==> packaging ${ZIP_NAME}"
rm -f "${ZIP_NAME}"
if command -v zip >/dev/null 2>&1; then
  ( cd "${PLUGIN_DIR}" && zip -qr "${ZIP_NAME}" "$(basename "${OUT_DIR}")" )
else
  "${VPY}" - "${OUT_DIR}" "${ZIP_NAME}" <<'PYPACK'
import sys, zipfile, os
src, dest = sys.argv[1], sys.argv[2]
root = os.path.dirname(src.rstrip("/"))
with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
    for dp, _dn, fns in os.walk(src):
        for fn in fns:
            p = os.path.join(dp, fn)
            z.write(p, os.path.relpath(p, root))
PYPACK
fi

# Refuse a full report whose embedded light bundle is missing/thin (so a degraded export
# is never shipped as success). The light runner already refuses thin bundles (exit 13).
if [[ "${LIGHT_RC}" -ne 0 || ! -s "${OUT_DIR}/${LIGHT_ZIP}" ]]; then
  echo "FATAL: full report incomplete — light bundle failed (rc=${LIGHT_RC}) or missing." >&2
  exit 13
fi
cp -f "${ZIP_NAME}" "${ZIP_LATEST}"

echo "==> DONE"
echo "    light_report_rc=${LIGHT_RC} validate_rc=${VALIDATE_RC}"
echo "    full report : ${PLUGIN_DIR}/${ZIP_NAME}"
echo "    latest      : ${PLUGIN_DIR}/${ZIP_LATEST}"
echo "    upload ${ZIP_LATEST} to ChatGPT for inspection."
exit "${LIGHT_RC}"
