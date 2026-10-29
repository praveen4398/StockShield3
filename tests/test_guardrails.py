"""Unit tests verifying Guardrails defenses across all 8 personas."""

import json

import pytest

from stockshield.guardrails.guardrails import GuardrailsEngine


@pytest.fixture
def personas():
    with open("config/personas.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_neutral_analyst_persona(personas):
    engine = GuardrailsEngine()
    data = personas["neutral_analyst"]
    result, req = engine.evaluate_request(
        {
            "ticker": data["ticker"],
            "user_prompt": data["user_prompt"],
            "lookback_days": data["parameters"]["lookback_days"],
        }
    )
    assert result.passed is True
    assert result.action == "PASS"
    assert result.security_flag == "NONE"
    assert req is not None


def test_rude_customer_persona(personas):
    """Rude language should be flagged for toxicity but allowed through if non-exploitative."""
    engine = GuardrailsEngine()
    data = personas["rude_customer"]
    result, req = engine.evaluate_request(
        {
            "ticker": data["ticker"],
            "user_prompt": data["user_prompt"],
            "lookback_days": data["parameters"]["lookback_days"],
        }
    )
    assert result.passed is True
    assert result.action == "PASS_WITH_FLAG"
    assert result.security_flag == "LOW_TOXICITY_FLAG"
    assert req is not None


def test_prompt_injection_persona(personas):
    engine = GuardrailsEngine()
    data = personas["prompt_injection_user"]
    result, req = engine.evaluate_request(
        {
            "ticker": data["ticker"],
            "user_prompt": data["user_prompt"],
            "lookback_days": data["parameters"]["lookback_days"],
        }
    )
    assert result.passed is False
    assert result.action == "BLOCK"
    assert result.security_flag == "PROMPT_INJECTION_ATTEMPT"
    assert req is None


def test_oversized_request_persona(personas):
    engine = GuardrailsEngine()
    data = personas["oversized_request"]
    result, req = engine.evaluate_request(
        {
            "ticker": data["ticker"],
            "user_prompt": data["user_prompt"],
            "lookback_days": data["parameters"]["lookback_days"],
        }
    )
    assert result.passed is False
    assert result.action == "BLOCK"
    assert result.security_flag == "RESOURCE_EXHAUSTION"


def test_malformed_input_persona(personas):
    engine = GuardrailsEngine()
    data = personas["malformed_input"]
    result, req = engine.evaluate_request(
        {
            "ticker": data["ticker"],
            "user_prompt": data["user_prompt"],
            "lookback_days": data["parameters"]["lookback_days"],
        }
    )
    assert result.passed is False
    assert result.action == "BLOCK"
    assert result.security_flag in {"SCHEMA_VIOLATION", "UNSUPPORTED_TICKER"}


def test_document_injection_isolation(personas):
    engine = GuardrailsEngine()
    data = personas["document_injection"]
    isolated = engine.isolate_untrusted_document(data["document_snippet"])
    assert "<UNTRUSTED_DOCUMENT_DATA>" in isolated
    assert "[FILTERED_OVERRIDE_TOKEN]" in isolated
