"""Priority-ranked recommendations for the bot inspection report.

Inspection/reporting ONLY. Turns the safety audit + missing-feature findings +
test results + baseline comparison into an actionable, priority-ranked list.

Priorities:
* P0 — safety failure or broken runtime.
* P1 — missing critical data/feature.
* P2 — weak model/performance issue.
* P3 — observability/reporting improvement.
"""

from __future__ import annotations

_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

# Map missing-feature severities to recommendation text.
_FEATURE_RECS = {
    "chainlink": "Fix Chainlink anchor freshness / enable the read-only oracle.",
    "btc_fast_price": "Add / restore the BTC fast price feed.",
    "btc_pulse_oracle_gate": "Ensure BTC Pulse only trades behind the oracle freshness gate.",
    "bregman": "Enable paper-only Bregman scanner diagnostics.",
    "news_scanner": "Enable or tighten the market-news scanner quality filters.",
    "grok_evidence": "Confirm Grok receives the read-only news evidence packet.",
    "paper_attribution": "Surface paper strategy attribution metrics.",
    "fill_realism": "Enable realistic-fill modeling and fantasy-fill rejection.",
    "calibration": "Emit calibration metrics (Brier / ECE).",
    "tests": "Restore the test suite / make tests pass inside the container.",
    "api_endpoints": "Expose the missing inspection API endpoint(s).",
    "market_scan_limit": "Apply the configured market scan limit.",
}


def build_recommendations(safety: dict, missing_features: list, tests: dict,
                          comparison: dict | None, runtime_available: bool) -> list[dict]:
    """Return a sorted list of ``{priority, area, action}`` recommendations."""
    safety = safety or {}
    tests = tests or {}
    comparison = comparison or {}
    recs: list[dict] = []

    def add(priority: str, area: str, action: str):
        recs.append({"priority": priority, "area": area, "action": action})

    # P0 — safety / broken runtime.
    if safety.get("critical"):
        for f in safety.get("summary", {}).get("forbidden_enabled", []):
            add("P0", "safety", f"Disable forbidden live/prod flag: {f}.")
        for f in safety.get("summary", {}).get("credentials_present", []):
            add("P0", "safety", f"Remove live credential material from paper config: {f}.")
        for f in safety.get("summary", {}).get("protective_disabled", []):
            add("P0", "safety", f"Re-enable protective flag: {f}.")
        if not recs:
            add("P0", "safety", "Investigate critical safety finding (see safety_audit.json).")
    if not runtime_available:
        add("P0", "runtime", "Restore paper-training status collection (engine not reachable).")

    # P1/P2/P3 — feature gaps (severity carried from detector).
    for mf in missing_features or []:
        sev = mf.get("severity", "P2")
        area = mf.get("feature", "feature")
        action = _FEATURE_RECS.get(area, mf.get("detail", "Address missing feature."))
        add(sev, area, action)

    # Tests.
    if tests.get("present") is False:
        add("P1", "tests", "Add/ship the test suite so the bot can be validated.")
    elif tests.get("passing") is False:
        add("P1", "tests", "Fix failing tests before trusting paper metrics.")

    # Performance regressions.
    if comparison.get("available") and comparison.get("regression"):
        degraded = ", ".join(comparison.get("degraded", [])) or "key metrics"
        add("P2", "performance", f"Investigate regression vs baseline in: {degraded}.")

    # De-duplicate (priority, area, action) while preserving order.
    seen = set()
    deduped = []
    for r in recs:
        key = (r["priority"], r["area"], r["action"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    deduped.sort(key=lambda r: _PRIORITY_ORDER.get(r["priority"], 9))
    return deduped
