"""Deterministic stub LLM for Google ADK Agent execution."""

from typing import AsyncGenerator

from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.genai.types import Content, Part


class ADKDeterministicStubLlm(BaseLlm):
    """Deterministic BaseLlm implementation allowing genuine Google ADK Runner execution offline."""

    model: str = "deterministic-stub"

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        part = Part.from_text(
            text="[Google ADK TechnicalAgent] Quantitative indicators and momentum signals verified deterministically."
        )
        content = Content(parts=[part], role="model")
        yield LlmResponse(content=content)
