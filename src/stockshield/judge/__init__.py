"""StockShield 2.0 Gemini LLM-as-a-Judge Package."""

from stockshield.judge.client import DEFAULT_JUDGE_MODEL, GeminiJudgeClient
from stockshield.judge.models import (
    DimensionName,
    DimensionScore,
    JudgeEvaluationOutput,
    JudgeEvaluationState,
    JudgeVerdict,
)
from stockshield.judge.prompt import PROMPT_VERSION, SYSTEM_INSTRUCTION, JudgePromptBuilder
from stockshield.judge.service import JudgeEvaluationService

__all__ = [
    "DEFAULT_JUDGE_MODEL",
    "DimensionName",
    "DimensionScore",
    "GeminiJudgeClient",
    "JudgeEvaluationOutput",
    "JudgeEvaluationService",
    "JudgeEvaluationState",
    "JudgePromptBuilder",
    "JudgeVerdict",
    "PROMPT_VERSION",
    "SYSTEM_INSTRUCTION",
]
