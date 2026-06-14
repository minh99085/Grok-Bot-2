"""Secret redaction for the bot inspection report generator.

Inspection/reporting ONLY — this module never enables trading, never touches a
wallet, and never submits an order. Its sole job is to make sure no secret ever
reaches ``report.md`` / ``report.json`` / the zip bundle / copied logs.

Two complementary strategies:

1. **Key-based** — any config/env key whose name contains a sensitive substring
   (``KEY``, ``SECRET``, ``TOKEN``, ``PASSWORD``, ``PRIVATE``, ``PASSPHRASE``,
   ``FUNDER``, ``WALLET``, ``SIGNER``, ``ACCESS_KEY`` …) has its value replaced
   with ``<REDACTED>``.
2. **Value-based** — obvious secret-looking strings in free text / logs
   (``xai-…`` keys, ``sk-…`` keys, PEM private-key blocks, long hex private
   keys, bearer tokens) are scrubbed regardless of the surrounding key.

Empty values are left empty on purpose so a reviewer can still tell whether a
sensitive setting is configured at all without ever seeing the value.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "<REDACTED>"

# Hard cap on the text size any single redaction pass will scan. Huge JSONL artifacts
# (events/diagnostics streams) otherwise make the value-pattern regexes scan multiple
# MB repeatedly and the report appears to hang (the observed KeyboardInterrupt inside
# redaction). For oversized text we keep the HEAD + TAIL (where any secret-looking value
# would still be caught) and drop the middle with a marker — dropping text is always
# SAFE for secret-redaction (it only ever REMOVES output, never exposes more).
MAX_REDACT_BYTES = 1_000_000
_CAP_KEEP = 200_000          # head + tail bytes kept when capping


def cap_for_redaction(text: str, max_bytes: int = MAX_REDACT_BYTES) -> str:
    """Bound the text a redaction pass scans. Returns ``text`` unchanged when small;
    otherwise head + a truncation marker + tail so redaction stays O(cap)."""
    if not text or len(text) <= max_bytes:
        return text
    keep = min(_CAP_KEEP, max_bytes // 2)
    dropped = len(text) - 2 * keep
    return (text[:keep]
            + f"\n…[REDACTION-CAP: dropped {dropped} bytes of a large artifact]…\n"
            + text[-keep:])

# Substrings that mark a config/env KEY as sensitive (matched case-insensitively).
SENSITIVE_KEY_SUBSTRINGS = (
    "KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "PRIVATE",
    "PASSPHRASE",
    "FUNDER",
    "WALLET",
    "SIGNER",
    "ACCESS_KEY",
    "API_KEY",
    "CREDENTIAL",
    "MNEMONIC",
    "SEED_PHRASE",
)

# Value-pattern scrubbers for free text / logs. Ordered; applied sequentially.
# Each is (compiled_regex, replacement).
_VALUE_PATTERNS = [
    # PEM private-key blocks (multi-line) — scrub the whole block.
    (re.compile(r"-----BEGIN [^-\n]*PRIVATE KEY-----.*?-----END [^-\n]*PRIVATE KEY-----",
                re.DOTALL), REDACTED),
    # xAI / Grok keys.
    (re.compile(r"\bxai-[A-Za-z0-9_\-]{10,}"), REDACTED),
    # OpenAI / OpenRouter style keys.
    (re.compile(r"\bsk-(?:or-)?[A-Za-z0-9_\-]{16,}"), REDACTED),
    # Bearer tokens in headers / logs.
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-]{12,}"), r"\1 " + REDACTED),
    # 0x-prefixed hex private keys / signatures (>=40 hex chars).
    (re.compile(r"\b0x[0-9a-fA-F]{40,}\b"), REDACTED),
    # Bare hex blobs long enough to be a private key (>=56 avoids 40-char git SHAs).
    (re.compile(r"\b[0-9a-fA-F]{56,}\b"), REDACTED),
]

# KEY=VALUE / KEY: VALUE assignment scrubber (used for logs + free text where the
# key name itself signals a secret).
# Note: the separator must NOT span newlines (use [ \t] not \s) or a bare
# ``key:`` followed by a newline would swallow the next line's first token.
_ASSIGNMENT_RE = re.compile(
    r"(?P<key>[A-Za-z0-9_.\-]*(?:KEY|SECRET|TOKEN|PASSWORD|PRIVATE|PASSPHRASE|"
    r"FUNDER|WALLET|SIGNER|CREDENTIAL|MNEMONIC)[A-Za-z0-9_.\-]*)"
    r"(?P<sep>[ \t]*[:=][ \t]*)(?P<val>\"?[^\s\"#]+\"?)",
    re.IGNORECASE,
)


def is_sensitive_key(key: str) -> bool:
    """True if a config/env key name marks its value as a secret."""
    if not key:
        return False
    up = str(key).upper()
    return any(sub in up for sub in SENSITIVE_KEY_SUBSTRINGS)


def redact_value(key: str, value: Any) -> Any:
    """Redact ``value`` if ``key`` is sensitive. Empty values stay empty so a
    reviewer can still see *whether* something is configured."""
    if value is None:
        return None
    if not is_sensitive_key(key):
        return value
    s = str(value)
    if s.strip() == "":
        return value
    return REDACTED


def scrub_text(text: str) -> str:
    """Scrub secret-looking VALUES out of free text / logs (value-based only). Caps
    oversized input first so a multi-MB artifact can never make redaction hang."""
    if not text:
        return text
    out = cap_for_redaction(text)
    for rx, repl in _VALUE_PATTERNS:
        out = rx.sub(repl, out)
    return out


def redact_text(text: str) -> str:
    """Full text redaction for logs / free text: scrub sensitive assignments by
    key-name AND scrub secret-looking values. Caps oversized input first (no hang)."""
    if not text:
        return text

    def _assign_sub(m: "re.Match[str]") -> str:
        return f"{m.group('key')}{m.group('sep')}{REDACTED}"

    out = _ASSIGNMENT_RE.sub(_assign_sub, cap_for_redaction(text))
    out = scrub_text(out)
    return out


def redact_env_text(text: str) -> str:
    """Redact a ``.env`` / docker-compose-style text body line by line.

    Lines of the form ``KEY=VALUE`` (or ``KEY: VALUE``) with a sensitive key get
    their value replaced; everything else is value-scrubbed. Comments and blanks
    are preserved so the file stays readable for auditors.
    """
    if not text:
        return text
    lines = text.splitlines()
    out_lines = []
    kv_re = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z0-9_.\-]+)(?P<sep>\s*[:=]\s*)(?P<val>.*)$")
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#") or not stripped:
            out_lines.append(line)
            continue
        m = kv_re.match(line)
        if m and is_sensitive_key(m.group("key")):
            val = m.group("val")
            # Preserve an empty value and any trailing inline comment.
            comment = ""
            cidx = val.find("#")
            core = val
            if cidx > 0:
                core, comment = val[:cidx].rstrip(), " " + val[cidx:]
            if core.strip().strip('"').strip("'") == "":
                out_lines.append(line)  # unset → leave as-is
            else:
                out_lines.append(f"{m.group('indent')}{m.group('key')}{m.group('sep')}{REDACTED}{comment}")
        else:
            out_lines.append(scrub_text(line))
    return "\n".join(out_lines) + ("\n" if text.endswith("\n") else "")


def redact_obj(obj: Any) -> Any:
    """Recursively redact a JSON-like object: sensitive dict values by key name,
    and secret-looking strings everywhere else."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            # Only string values can be secrets; booleans/numbers under
            # sensitive-named keys (e.g. ``grok_has_api_key: true``) are safe
            # indicators and must stay visible. Embedded secrets in any string
            # are still caught by scrub_text below.
            if is_sensitive_key(str(k)) and isinstance(v, str) and v.strip() != "":
                out[k] = REDACTED
            else:
                out[k] = redact_obj(v)
        return out
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, str):
        return scrub_text(obj)
    return obj


def scan_for_secrets(text: str) -> list[dict]:
    """Return a list of secret-pattern hits found in ``text`` *before* redaction.

    Used by the redaction audit to prove the scrubber would have caught real
    secrets. Returns pattern label + match count only (never the secret value).
    """
    if not text:
        return []
    labels = [
        ("pem_private_key", _VALUE_PATTERNS[0][0]),
        ("xai_key", _VALUE_PATTERNS[1][0]),
        ("sk_key", _VALUE_PATTERNS[2][0]),
        ("bearer_token", _VALUE_PATTERNS[3][0]),
        ("hex_0x_key", _VALUE_PATTERNS[4][0]),
        ("hex_blob", _VALUE_PATTERNS[5][0]),
        ("sensitive_assignment", _ASSIGNMENT_RE),
    ]
    hits = []
    for label, rx in labels:
        n = len(rx.findall(text))
        if n:
            hits.append({"pattern": label, "count": n})
    return hits


def assert_clean(text: str) -> list[str]:
    """Return a list of residual secret patterns still present in ``text`` after
    redaction (should be empty). Used as a final guard before writing files."""
    residual = []
    for label, rx in (
        ("xai_key", _VALUE_PATTERNS[1][0]),
        ("sk_key", _VALUE_PATTERNS[2][0]),
        ("pem_private_key", _VALUE_PATTERNS[0][0]),
        ("hex_0x_key", _VALUE_PATTERNS[4][0]),
    ):
        if rx.search(text):
            residual.append(label)
    return residual
