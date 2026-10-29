"""Deterministic stub LLM for CrewAI Agent and Crew execution."""

from crewai.llms.base_llm import BaseLLM


class CrewAIDeterministicStubLLM(BaseLLM):
    """Deterministic BaseLLM implementation allowing genuine Crew.kickoff() execution offline."""

    model: str = "deterministic-stub"

    def call(self, messages, *args, **kwargs) -> str:
        return "[CrewAI Orchestrator] Multi-agent analysis workflow executed and synthesized successfully."

    async def acall(self, messages, *args, **kwargs) -> str:
        return "[CrewAI Orchestrator] Multi-agent analysis workflow executed and synthesized successfully."

    def get_context_window_size(self) -> int:
        return 8192
