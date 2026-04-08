"""Tests for the false-positive validator.

These tests cover the three gates of the validator:
  1. pattern-based FP filter
  2. dual-source confirmation for high/critical
  3. evidence-quality scoring
plus the rabbit-hole detector.
"""
from __future__ import annotations


def test_waf_response_is_not_sqli():
    from backend.agents.validator import get_validator
    v = get_validator()
    r = v.validate(
        title="SQLi on /login",
        severity="high",
        evidence_text="Cloudflare blocked your request. Please try again.",
        sources=["sqlmap"],
        category="web",
    )
    # either the WAF rule or the generic-sql-error rule must fire
    assert r.fp_rules_hit, "WAF/generic error pattern was not caught"
    assert r.severity in {"info", "low"}
    assert r.status in {"suspected", "possible"}


def test_encoded_xss_rejected():
    from backend.agents.validator import get_validator
    v = get_validator()
    r = v.validate(
        title="Reflected XSS on q=",
        severity="high",
        evidence_text="Body contained &lt;script&gt;alert(1)&lt;/script&gt;",
        sources=["nuclei"],
        category="web",
    )
    assert "xss_reflected_not_executed" in r.fp_rules_hit
    assert r.severity == "info"


def test_dual_source_real_high_is_confirmed():
    from backend.agents.validator import get_validator
    v = get_validator()
    r = v.validate(
        title="SSRF to cloud metadata",
        severity="high",
        evidence_text=(
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
            " returned ami-1234 role=ec2-instance-profile expiry=..."
        ),
        sources=["nuclei", "curl"],
        category="web",
        confirmed_by_poc=True,
    )
    assert r.accepted
    assert r.severity == "high"
    assert r.status in {"confirmed", "exploited"}
    assert r.quality_score >= 0.6


def test_single_source_high_demoted_to_possible():
    from backend.agents.validator import get_validator
    v = get_validator()
    r = v.validate(
        title="CVE-2023-XXXX RCE in service X",
        severity="high",
        evidence_text="Banner says: service/1.2.3 — probably vulnerable to CVE-2023-XXXX",
        sources=["nmap"],
        category="network",
    )
    # Single-source high must be demoted
    assert r.severity == "medium"
    assert r.status == "possible"


def test_kerberoast_disabled_account_rejected():
    from backend.agents.validator import get_validator
    v = get_validator()
    r = v.validate(
        title="Kerberoastable account found",
        severity="high",
        evidence_text="User svc_sql SPN=MSSQLSvc/... STATUS_ACCOUNT_DISABLED",
        sources=["impacket", "crackmapexec"],
        category="active_directory",
    )
    assert "kerberoast_disabled_account" in r.fp_rules_hit
    assert r.severity == "info"


def test_quality_score_bounds():
    from backend.agents.validator import get_validator
    v = get_validator()
    r = v.validate(
        title="anything",
        severity="low",
        evidence_text="x" * 500,
        sources=["nmap", "nuclei"],
        category="web",
        confirmed_by_poc=True,
    )
    assert 0.0 <= r.quality_score <= 1.0


def test_rabbit_hole_waf_loop():
    from backend.agents.validator import FindingValidator
    text = "WAF block\nWAF block\nWAF block\nWAF block\nWAF block\nWAF block"
    warnings = FindingValidator.detect_rabbit_hole(text)
    assert any("Stop" in w or "Rotate" in w for w in warnings)


def test_rabbit_hole_placeholder_target():
    from backend.agents.validator import FindingValidator
    text = "Scanning example.com for vulnerabilities..."
    warnings = FindingValidator.detect_rabbit_hole(text)
    assert any("escalate" in w.lower() or "halt" in w.lower() for w in warnings)


def test_info_noise_is_dropped():
    from backend.agents.validator import get_validator
    v = get_validator()
    r = v.validate(
        title="trivia",
        severity="info",
        evidence_text="",
        sources=[],
        category="web",
    )
    assert r.accepted is False
