"""Judge Evaluation Service orchestrating end-to-end evaluation flow."""

import asyncio
import os
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

from stockshield.judge.client import GeminiJudgeClient
from stockshield.judge.prompt import PROMPT_VERSION, JudgePromptBuilder

if TYPE_CHECKING:
    pass


class JudgeEvaluationService:
    """Coordinates prompt construction, Gemini API execution, and Blackboard state publishing."""

    def __init__(
        self,
        name: str = "GeminiJudgeService",
        client: Optional[GeminiJudgeClient] = None,
        enabled: Optional[bool] = None,
    ):
        self.name = name
        self.client = client or GeminiJudgeClient()
        self._enabled_override: Optional[bool] = enabled

    @property
    def is_enabled(self) -> bool:
        """Dynamically evaluate whether judge is globally enabled via environment or override."""
        if self._enabled_override is not None:
            return self._enabled_override
        return os.getenv("LLM_JUDGE_ENABLED", "false").lower() in ("true", "1", "yes")

    @property
    def enabled(self) -> bool:
        return self.is_enabled

    @enabled.setter
    def enabled(self, val: Optional[bool]) -> None:
        self._enabled_override = val

    async def execute(
        self,
        blackboard: Any,
        force_enable: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Execute Gemini LLM-as-a-Judge evaluation on the Blackboard state."""
        from stockshield.blackboard.models import FindingStatus

        start_time = time.perf_counter()
        is_active = self.is_enabled if force_enable is None else force_enable

        if not is_active:
            await blackboard.update_judge_evaluation(
                producer=self.name,
                status=FindingStatus.SKIPPED,
                notes="LLM-as-a-Judge evaluation disabled by configuration or request flag.",
            )
            return {"status": "skipped", "reason": "judge_disabled"}

        if not self.client.is_configured:
            await blackboard.update_judge_evaluation(
                producer=self.name,
                status=FindingStatus.NOT_CONFIGURED,
                notes="GEMINI_API_KEY environment variable is not configured. Live evaluation unavailable.",
            )
            return {"status": "not_configured", "reason": "api_key_missing"}

        configured_model = self.client.model_name
        fallback_candidates = getattr(self.client, "fallback_models", [])
        await blackboard.log_event(
            component=self.name,
            event_type="agent_start",
            status="running",
            details={
                "configured_model": configured_model,
                "model": configured_model,
                "prompt_version": PROMPT_VERSION,
                "fallback_candidates": fallback_candidates,
            },
        )

        state = await blackboard.get_state_snapshot()

        # Check prerequisite: report must be synthesized
        if not state.final_report.markdown_content and not state.final_report.executive_summary:
            await blackboard.update_judge_evaluation(
                producer=self.name,
                status=FindingStatus.UNAVAILABLE,
                notes="Final report not synthesized yet; cannot evaluate empty state.",
            )
            return {"status": "unavailable", "reason": "report_empty"}

        # Construct evaluation prompt
        eval_prompt = JudgePromptBuilder.build_evaluation_prompt(state)

        # Execute Gemini API call in background thread to avoid blocking asyncio event loop
        try:
            eval_output, meta = await asyncio.to_thread(self.client.evaluate, eval_prompt)
        except Exception as e:
            eval_output = None
            meta = {
                "status": "failed",
                "error": f"Exception during judge execution thread: {str(e)}",
                "latency_ms": (time.perf_counter() - start_time) * 1000,
                "configured_model": configured_model,
                "actual_model": None,
                "model_name": configured_model,
                "fallback_triggered": False,
                "attempt_history": [],
            }

        total_latency_ms = (time.perf_counter() - start_time) * 1000
        actual_model = meta.get("actual_model") or meta.get("model_name")
        configured_model = meta.get("configured_model") or self.client.model_name
        fallback_triggered = meta.get("fallback_triggered", False)
        attempt_history = meta.get("attempt_history", [])

        if eval_output and meta.get("status") == "completed":
            dim_dict = {d.dimension.value: d for d in eval_output.dimensions}
            await blackboard.update_judge_evaluation(
                producer=self.name,
                status=FindingStatus.AVAILABLE,
                model_name=actual_model,
                configured_model=configured_model,
                actual_model=actual_model,
                fallback_triggered=fallback_triggered,
                prompt_version=PROMPT_VERSION,
                has_sufficient_evidence=eval_output.has_sufficient_evidence,
                overall_score=eval_output.overall_score,
                verdict=eval_output.verdict.value,
                dimensions=dim_dict,
                critical_findings=eval_output.critical_findings,
                warnings=eval_output.warnings,
                strengths=eval_output.strengths,
                limitations=eval_output.limitations,
                evaluation_summary=eval_output.evaluation_summary,
                latency_ms=meta.get("latency_ms"),
                input_tokens=meta.get("input_tokens"),
                output_tokens=meta.get("output_tokens"),
                total_tokens=meta.get("total_tokens"),
                estimated_cost_usd=meta.get("estimated_cost_usd"),
                cost_status=meta.get("cost_status", "unavailable"),
                attempt_history=attempt_history,
                notes=f"Gemini evaluation completed (Score: {eval_output.overall_score}/10, Verdict: {eval_output.verdict.value}, Model: {actual_model})",
            )
            await blackboard.log_event(
                component=self.name,
                event_type="agent_complete",
                status="completed",
                details={
                    "overall_score": eval_output.overall_score,
                    "verdict": eval_output.verdict.value,
                    "duration_ms": total_latency_ms,
                    "configured_model": configured_model,
                    "actual_model": actual_model,
                    "model": actual_model,
                    "fallback_triggered": fallback_triggered,
                    "attempt_history": attempt_history,
                    "input_tokens": meta.get("input_tokens"),
                    "output_tokens": meta.get("output_tokens"),
                    "total_tokens": meta.get("total_tokens"),
                    "estimated_cost_usd": meta.get("estimated_cost_usd"),
                    "cost_status": meta.get("cost_status", "unavailable"),
                },
            )
            return {
                "status": "completed",
                "overall_score": eval_output.overall_score,
                "verdict": eval_output.verdict.value,
                "duration_ms": total_latency_ms,
                "configured_model": configured_model,
                "actual_model": actual_model,
                "fallback_triggered": fallback_triggered,
            }
        else:
            err_msg = meta.get("error", "Evaluation failed without error details")
            await blackboard.update_judge_evaluation(
                producer=self.name,
                status=FindingStatus.FAILED,
                model_name=actual_model or configured_model,
                configured_model=configured_model,
                actual_model=actual_model,
                fallback_triggered=fallback_triggered,
                error_message=err_msg,
                latency_ms=meta.get("latency_ms"),
                attempt_history=attempt_history,
                notes=f"Gemini evaluation failed: {err_msg}",
            )
            await blackboard.log_event(
                component=self.name,
                event_type="agent_complete",
                status="failed",
                details={
                    "error": err_msg,
                    "duration_ms": total_latency_ms,
                    "configured_model": configured_model,
                    "actual_model": actual_model,
                    "fallback_triggered": fallback_triggered,
                    "attempt_history": attempt_history,
                },
            )
            return {
                "status": "failed",
                "reason": err_msg,
                "duration_ms": total_latency_ms,
                "configured_model": configured_model,
                "actual_model": actual_model,
                "fallback_triggered": fallback_triggered,
            }
            return {"status": "failed", "error": err_msg, "duration_ms": total_latency_ms}
