"""LLMProvider ABC - Interface for LLM classification integrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ClassificationResult:
    """Structured result from intent classification."""

    intent: str
    confidence_score: float
    reasoning: str
    key_phrases: list[str]
    direction: str  # forward, backward, neutral
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_response: dict[str, Any] | None = None


class LLMProvider(ABC):
    """Abstract base class for LLM provider integrations."""

    @abstractmethod
    async def classify_intent(
        self,
        email_content: str,
        context: dict[str, Any],
        system_prompt: str,
        prompt_template: str,
        intent_categories: list[str],
    ) -> ClassificationResult:
        """Classify deal progression intent from email content.

        Args:
            email_content: PII-redacted email text.
            context: Dict with deal_stage, thread_summary, etc.
            system_prompt: System instructions for the LLM.
            prompt_template: User prompt template with {placeholders}.
            intent_categories: Valid intent category list.

        Returns:
            ClassificationResult with intent, confidence, reasoning.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the LLM provider is reachable."""
        ...
