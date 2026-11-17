"""Gemini LLM Client wrapper for StockShield 2.0 LLM-as-a-Judge.

Interfaces with Google GenAI SDK (google-genai) with structured output schema enforcement,
robust error handling, timeouts, and token/cost measurement.
"""

import json
import os
import time
from typing import Any, Dict, Optional, Tuple

from google import genai
from google.genai import types

from stockshield.judge.models import JudgeEvaluationOutput
from stockshield.judge.prompt import SYSTEM_INSTRUCTION
from stockshield.llm.cost_estimator import compute_cost

DEFAULT_JUDGE_MODEL = "gemini-3.8-flash"
FALLBACK_CANDIDATES = ["gemini-3.5-flash", "gemini-3-flash-preview"]


class GeminiJudgeClient:
    """Encapsulates interaction with Google Gemini API for post-hoc report evaluation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        fallback_models: Optional[list] = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = (
            model_name or os.getenv("GEMINI_JUDGE_MODEL") or os.getenv("LLM_MODEL_NAME") or DEFAULT_JUDGE_MODEL
        )
        self.timeout_seconds = timeout_seconds or int(os.getenv("LLM_JUDGE_TIMEOUT_SECONDS", "30"))
        self.fallback_models = list(fallback_models) if fallback_models is not None else list(FALLBACK_CANDIDATES)
        self._client: Optional[genai.Client] = None

        if self.api_key and self.api_key.strip():
            retry_opts = types.HttpRetryOptions(attempts=1)
            http_opts = types.HttpOptions(
                retry_options=retry_opts,
                timeout=self.timeout_seconds * 1000,
            )
            self._client = genai.Client(api_key=self.api_key.strip(), http_options=http_opts)

    @property
    def is_configured(self) -> bool:
        """Whether a valid API key is present."""
        return bool(self.api_key and self.api_key.strip())

    def evaluate(
        self,
        user_prompt: str,
        system_instruction: str = SYSTEM_INSTRUCTION,
    ) -> Tuple[Optional[JudgeEvaluationOutput], Dict[str, Any]]:
        """Call Gemini models.generate_content with structured Pydantic schema."""
        if not self.is_configured or self._client is None:
            return None, {
                "status": "not_configured",
                "error": "GEMINI_API_KEY environment variable is not configured.",
                "latency_ms": 0.0,
                "configured_model": self.model_name,
                "actual_model": None,
                "model_name": self.model_name,
                "fallback_triggered": False,
                "attempt_history": [],
            }

        start_time = time.perf_counter()
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.1,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            response_mime_type="application/json",
            response_schema=JudgeEvaluationOutput,
        )

        # Fallback candidates if the primary model is experiencing transient 503/504 spikes
        models_to_try = [self.model_name]
        for fb in self.fallback_models:
            if fb not in models_to_try:
                models_to_try.append(fb)

        attempt_history = []
        last_exception = None
        used_model = self.model_name
        response = None

        for target_model in models_to_try:
            attempt_start = time.perf_counter()
            try:
                response = self._client.models.generate_content(
                    model=target_model,
                    contents=user_prompt,
                    config=config,
                )
                attempt_latency_ms = round((time.perf_counter() - attempt_start) * 1000, 2)
                attempt_history.append({
                    "model": target_model,
                    "status": "success",
                    "latency_ms": attempt_latency_ms,
                    "http_status": 200,
                })
                used_model = target_model
                last_exception = None
                break
            except Exception as exc:
                attempt_latency_ms = round((time.perf_counter() - attempt_start) * 1000, 2)
                err_text = str(exc)
                err_lower = err_text.lower()
                status_code = "failed"
                if "timeout" in err_lower or "deadline" in err_lower:
                    status_code = "timeout"
                elif "429" in err_text or "quota" in err_lower or "resource_exhausted" in err_lower:
                    status_code = "rate_limited"
                elif "401" in err_text or "403" in err_text or "api_key" in err_lower:
                    status_code = "auth_failed"
                elif "unavailable" in err_lower or "503" in err_text or "504" in err_text:
                    status_code = "unavailable"

                attempt_history.append({
                    "model": target_model,
                    "status": status_code,
                    "latency_ms": attempt_latency_ms,
                    "error": err_text[:300],
                })
                last_exception = exc
                # Only retry with fallback model on 503 UNAVAILABLE, 504 DEADLINE_EXCEEDED, or transient timeout
                if "503" in err_text or "504" in err_text or "unavailable" in err_lower or "deadline" in err_lower:
                    continue
                else:
                    break

        if last_exception is not None or response is None:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_str = str(last_exception) if last_exception else "No response received"
            status_code = "failed"
            err_lower = err_str.lower()
            if "timeout" in err_lower or "deadline" in err_lower:
                status_code = "timeout"
            elif "429" in err_str or "quota" in err_lower or "resource_exhausted" in err_lower:
                status_code = "rate_limited"
            elif "401" in err_str or "403" in err_str or "api_key" in err_lower:
                status_code = "auth_failed"
            elif "unavailable" in err_lower or "503" in err_str:
                status_code = "unavailable"

            return None, {
                "status": status_code,
                "error": f"Gemini Judge execution failed: {err_str}",
                "latency_ms": round(duration_ms, 2),
                "configured_model": self.model_name,
                "actual_model": None,
                "model_name": self.model_name,
                "fallback_triggered": len(attempt_history) > 1,
                "attempt_history": attempt_history,
            }

        try:
            duration_ms = (time.perf_counter() - start_time) * 1000

            usage = getattr(response, "usage_metadata", None)
            in_tokens = getattr(usage, "prompt_token_count", None)
            out_tokens = getattr(usage, "candidates_token_count", None)
            tot_tokens = getattr(usage, "total_token_count", None)
            if tot_tokens is None and in_tokens is not None and out_tokens is not None:
                tot_tokens = in_tokens + out_tokens

            raw_text = response.text if hasattr(response, "text") and response.text else ""
            if not raw_text and hasattr(response, "candidates") and response.candidates:
                part = response.candidates[0].content.parts[0]
                raw_text = getattr(part, "text", "")

            if not raw_text:
                return None, {
                    "status": "failed",
                    "error": "Gemini returned empty response content.",
                    "latency_ms": round(duration_ms, 2),
                    "configured_model": self.model_name,
                    "actual_model": used_model,
                    "model_name": used_model,
                    "fallback_triggered": used_model != self.model_name,
                    "attempt_history": attempt_history,
                }

            data = json.loads(raw_text)
            parsed_output = JudgeEvaluationOutput.model_validate(data)

            cost_info = compute_cost(
                input_text=user_prompt,
                output_text=raw_text,
                model_name=used_model,
                is_stub=False,
                actual_input_tokens=in_tokens,
                actual_output_tokens=out_tokens,
            )

            meta = {
                "status": "completed",
                "latency_ms": round(duration_ms, 2),
                "configured_model": self.model_name,
                "actual_model": used_model,
                "model_name": used_model,
                "fallback_triggered": used_model != self.model_name,
                "attempt_history": attempt_history,
                "input_tokens": in_tokens if in_tokens is not None else cost_info.estimated_input_tokens,
                "output_tokens": out_tokens if out_tokens is not None else cost_info.estimated_output_tokens,
                "total_tokens": tot_tokens if tot_tokens is not None else cost_info.total_tokens,
                "estimated_cost_usd": cost_info.total_cost_usd,
                "cost_status": cost_info.cost_status,
                "raw_text_length": len(raw_text),
            }
            return parsed_output, meta

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_str = str(e)
            status_code = "failed"
            err_lower = err_str.lower()
            if "timeout" in err_lower or "deadline" in err_lower:
                status_code = "timeout"
            elif "429" in err_str or "quota" in err_lower or "resource_exhausted" in err_lower:
                status_code = "rate_limited"
            elif "401" in err_str or "403" in err_str or "api_key" in err_lower:
                status_code = "auth_failed"
            elif "unavailable" in err_lower or "connection" in err_lower:
                status_code = "unavailable"

            return None, {
                "status": status_code,
                "error": f"Gemini Judge execution failed: {err_str}",
                "latency_ms": round(duration_ms, 2),
                "configured_model": self.model_name,
                "actual_model": used_model if 'used_model' in locals() else None,
                "model_name": self.model_name,
                "fallback_triggered": len(attempt_history) > 1,
                "attempt_history": attempt_history,
            }
