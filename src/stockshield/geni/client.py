"""Gemini LLM Client wrapper for GENI (StockShield Analysis Assistant).

Integrates with the Google GenAI SDK (google-genai) with selective fallback logic,
strict quota exhaustion short-circuiting, timeouts, and multi-turn support.
"""

import os
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass

from google import genai
from google.genai import types

from stockshield.geni.models import GeniMessage, MessageRole
from stockshield.geni.prompt import GENI_SYSTEM_INSTRUCTION

DEFAULT_GENI_MODEL = "gemini-3.8-flash"
GENI_FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3-flash-preview"]


class GeniClient:
    """Encapsulates interaction with Google Gemini for conversational analysis explanation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        fallback_models: Optional[List[str]] = None,
    ):
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY")
        self.model_name = (
            model_name or os.getenv("GENI_MODEL") or os.getenv("LLM_MODEL_NAME") or DEFAULT_GENI_MODEL
        )
        self.timeout_seconds = timeout_seconds or int(os.getenv("GENI_TIMEOUT_SECONDS", "30"))
        self.fallback_models = (
            list(fallback_models) if fallback_models is not None else list(GENI_FALLBACK_MODELS)
        )
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
        """Check whether a non-empty API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    def generate_chat_reply(
        self,
        analysis_context: str,
        user_message: str,
        chat_history: Optional[List[GeniMessage]] = None,
        system_instruction: str = GENI_SYSTEM_INSTRUCTION,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Generate grounded conversational response using Google GenAI SDK.

        Args:
            analysis_context: Structured markdown evidence of the completed run.
            user_message: Latest user question.
            chat_history: Optional prior conversation turns.
            system_instruction: System prompt enforcing grounding and safety.

        Returns:
            Tuple[Optional[response_text], metadata_dict]
        """
        if not self.is_configured or self._client is None:
            return None, {
                "status": "not_configured",
                "error": "GEMINI_API_KEY environment variable is not configured.",
                "latency_ms": 0.0,
                "configured_model": self.model_name,
                "actual_model": None,
                "fallback_triggered": False,
                "attempt_history": [],
            }

        start_time = time.perf_counter()

        # Build multi-turn content sequence
        contents: List[types.Content] = []

        # Turn 1: Seed the conversation with the canonical analysis evidence
        initial_context_payload = (
            f"Here is the verified StockShield 2.0 analysis evidence you must ground all answers upon:\n\n"
            f"{analysis_context}\n\n"
            f"Acknowledge this evidence and answer the user's questions strictly according to these facts."
        )

        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=initial_context_payload)],
            )
        )
        contents.append(
            types.Content(
                role="model",
                parts=[
                    types.Part.from_text(
                        text="Understood. I have verified and loaded the StockShield 2.0 analysis evidence. "
                        "I am ready to explain the findings, technical indicators, risk ratings, and forecasts."
                    )
                ],
            )
        )

        # Append previous conversation history turns (if any)
        if chat_history:
            for turn in chat_history:
                gemini_role = "user" if turn.role == MessageRole.USER else "model"
                contents.append(
                    types.Content(
                        role=gemini_role,
                        parts=[types.Part.from_text(text=turn.content)],
                    )
                )

        # Append current user question
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_message)],
            )
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
            max_output_tokens=4096,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        models_to_try = [self.model_name]
        for fb in self.fallback_models:
            if fb not in models_to_try:
                models_to_try.append(fb)

        attempt_history: List[Dict[str, Any]] = []
        last_exception: Optional[Exception] = None
        used_model = self.model_name
        response = None

        for target_model in models_to_try:
            attempt_start = time.perf_counter()
            try:
                response = self._client.models.generate_content(
                    model=target_model,
                    contents=contents,
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

                # Categorize error
                if "429" in err_text or "quota" in err_lower or "resource_exhausted" in err_lower:
                    status_code = "rate_limited"
                elif "timeout" in err_lower or "deadline" in err_lower:
                    status_code = "timeout"
                elif "401" in err_text or "403" in err_text or "api_key" in err_lower:
                    status_code = "auth_failed"
                elif "503" in err_text or "504" in err_text or "unavailable" in err_lower:
                    status_code = "unavailable"

                attempt_history.append({
                    "model": target_model,
                    "status": status_code,
                    "latency_ms": attempt_latency_ms,
                    "error": err_text[:300],
                })
                last_exception = exc

                # Requirement 3: Avoid unnecessary retries on quota exhaustion (429) or auth errors (401/403)
                if status_code in {"rate_limited", "auth_failed"}:
                    break

                # Only attempt fallback on transient timeout, 503, or 504
                if status_code in {"timeout", "unavailable"}:
                    continue
                else:
                    break

        duration_ms = (time.perf_counter() - start_time) * 1000

        if last_exception is not None or response is None:
            err_str = str(last_exception) if last_exception else "No response returned from Gemini."
            err_lower = err_str.lower()
            final_status = "failed"
            if "429" in err_str or "quota" in err_lower or "resource_exhausted" in err_lower:
                final_status = "rate_limited"
            elif "timeout" in err_lower or "deadline" in err_lower:
                final_status = "timeout"
            elif "401" in err_str or "403" in err_str or "api_key" in err_lower:
                final_status = "auth_failed"
            elif "503" in err_str or "504" in err_str or "unavailable" in err_lower:
                final_status = "unavailable"

            return None, {
                "status": final_status,
                "error": f"GENI model generation error: {err_str}",
                "latency_ms": round(duration_ms, 2),
                "configured_model": self.model_name,
                "actual_model": None,
                "fallback_triggered": len(attempt_history) > 1,
                "attempt_history": attempt_history,
            }

        # Extract generated response text
        raw_text = response.text if hasattr(response, "text") and response.text else ""
        if not raw_text and hasattr(response, "candidates") and response.candidates:
            part = response.candidates[0].content.parts[0]
            raw_text = getattr(part, "text", "")

        if not raw_text:
            return None, {
                "status": "failed",
                "error": "Gemini returned empty response candidate content.",
                "latency_ms": round(duration_ms, 2),
                "configured_model": self.model_name,
                "actual_model": used_model,
                "fallback_triggered": used_model != self.model_name,
                "attempt_history": attempt_history,
            }

        usage = getattr(response, "usage_metadata", None)
        in_tokens = getattr(usage, "prompt_token_count", None)
        out_tokens = getattr(usage, "candidates_token_count", None)
        tot_tokens = getattr(usage, "total_token_count", None)

        return raw_text, {
            "status": "success",
            "latency_ms": round(duration_ms, 2),
            "configured_model": self.model_name,
            "actual_model": used_model,
            "fallback_triggered": used_model != self.model_name,
            "attempt_history": attempt_history,
            "tokens": {
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "total_tokens": tot_tokens,
            },
        }
