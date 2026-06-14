"""Tests for the inspection secret redactor."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import inspection_redactor as r  # noqa: E402

REDACTED = r.REDACTED


def test_large_artifact_redaction_is_capped_and_fast():
    # a multi-MB JSONL artifact must NOT make redaction hang (the observed Ctrl+C).
    import time
    big = ("{\"event\":\"decision\",\"x\":1}\n" * 400_000) + "leaked xai-" + ("a" * 50) + "\n"
    assert len(big) > 5_000_000
    t0 = time.time()
    out = r.redact_text(big)
    assert time.time() - t0 < 5.0                      # bounded (cap), never hangs
    assert "REDACTION-CAP" in out                      # middle dropped with a marker
    assert "xai-aaaa" not in out                       # tail secret still scrubbed


def test_cap_for_redaction_keeps_small_text_unchanged():
    small = "hello world\nxai-" + ("b" * 40)
    assert r.cap_for_redaction(small) == small         # small text untouched
    assert "xai-bbbb" not in r.redact_text(small)      # still scrubbed


def test_sensitive_key_detection():
    for key in ("GROK_API_KEY", "XAI_API_KEY", "POLYMARKET_PRIVATE_KEY",
                "POLYMARKET_API_SECRET", "KALSHI_PRIVATE_KEY_PEM",
                "SOME_TOKEN", "DB_PASSWORD", "WALLET_FUNDER", "SIGNER_ADDRESS"):
        assert r.is_sensitive_key(key), key
    for key in ("HTE_MODE", "CHAINLINK_RPC_URL", "POLYMARKET_SCAN_LIMIT"):
        assert not r.is_sensitive_key(key), key


def test_redact_value_redacts_sensitive_nonempty():
    assert r.redact_value("GROK_API_KEY", "xai-abc123def456ghi") == REDACTED
    # Empty stays empty so reviewers can see it's unset.
    assert r.redact_value("GROK_API_KEY", "") == ""
    assert r.redact_value("HTE_MODE", "paper") == "paper"


def test_redact_text_catches_xai_keys():
    text = "starting grok with key xai-ABCDEFGHIJ1234567890 done"
    out = r.redact_text(text)
    assert "xai-ABCDEFGHIJ1234567890" not in out
    assert REDACTED in out


def test_redact_text_catches_sk_keys():
    text = "OPENROUTER sk-or-v1-aaaaaaaaaaaaaaaaaaaaaaaa used"
    out = r.redact_text(text)
    assert "sk-or-v1-aaaaaaaaaaaaaaaaaaaaaaaa" not in out


def test_redact_text_catches_pem_block():
    pem = ("-----BEGIN EC PRIVATE KEY-----\n"
           "MHcCAQEEIabcdefghijklmnop\nqrstuvwxyz0123456789\n"
           "-----END EC PRIVATE KEY-----")
    out = r.redact_text(f"key:\n{pem}\nend")
    assert "BEGIN EC PRIVATE KEY" not in out
    assert "MHcCAQEEIabcdefghijklmnop" not in out


def test_redact_text_catches_hex_private_key():
    text = "priv 0x" + "ab" * 32 + " end"  # 64 hex chars
    out = r.redact_text(text)
    assert "ab" * 32 not in out


def test_redact_text_preserves_short_git_sha():
    # 40-char git SHAs must remain readable in logs/diffs.
    sha = "5464737cf131fb39cb1d38e8fba21c5d91f456fd"
    out = r.redact_text(f"commit {sha} message")
    assert sha in out


def test_redact_env_text_redacts_assignment_values():
    text = ("HTE_MODE=paper\n"
            "GROK_API_KEY=xai-secretsecretsecret123\n"
            "XAI_API_KEY=\n"
            "# comment\n")
    out = r.redact_env_text(text)
    assert "xai-secretsecretsecret123" not in out
    assert f"GROK_API_KEY={REDACTED}" in out
    assert "HTE_MODE=paper" in out
    # Empty sensitive value preserved as-is (unset).
    assert "XAI_API_KEY=\n" in out or "XAI_API_KEY=" in out
    assert "# comment" in out


def test_redact_obj_recursive():
    obj = {"GROK_API_KEY": "xai-zzzzzzzzzzzz", "nested": {"TOKEN": "abc123def456ghi",
           "mode": "paper"}, "note": "key xai-AAAAAAAAAAAA leaked"}
    out = r.redact_obj(obj)
    assert out["GROK_API_KEY"] == REDACTED
    assert out["nested"]["TOKEN"] == REDACTED
    assert out["nested"]["mode"] == "paper"
    assert "xai-AAAAAAAAAAAA" not in out["note"]


def test_redact_obj_keeps_boolean_indicators():
    # ``grok_has_api_key: true`` proves a key is present WITHOUT revealing it and
    # must survive redaction; only string secret values are redacted by key name.
    obj = {"grok_has_api_key": True, "count": 5,
           "GROK_API_KEY": "xai-zzzzzzzzzzzzzz"}
    out = r.redact_obj(obj)
    assert out["grok_has_api_key"] is True
    assert out["count"] == 5
    assert out["GROK_API_KEY"] == REDACTED


def test_scan_for_secrets_counts_without_leaking():
    text = "xai-ABCDEFGHIJ1234 and sk-or-v1-bbbbbbbbbbbbbbbbbbbb"
    hits = r.scan_for_secrets(text)
    labels = {h["pattern"] for h in hits}
    assert "xai_key" in labels
    assert "sk_key" in labels


def test_assert_clean_finds_no_residual_after_redaction():
    text = "xai-ABCDEFGHIJ1234567890 sk-or-v1-cccccccccccccccccccc"
    redacted = r.redact_text(text)
    assert r.assert_clean(redacted) == []
