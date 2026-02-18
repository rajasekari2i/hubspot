"""OpenAI LLM integration for intent classification."""

from __future__ import annotations

import json
import time
from typing import Any

import openai
import structlog

from app.integrations.llm.base import ClassificationResult, LLMProvider
from app.utils.circuit_breaker import circuit_breaker

logger = structlog.get_logger(__name__)


class OpenAIClient(LLMProvider):
    """LLM provider implementation using the OpenAI async SDK."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
    ) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._model = model
        logger.info("openai_client_initialized", model=model)

    @circuit_breaker(name="llm_openai", failure_threshold=3, reset_timeout=30)
    async def classify_intent(
        self,
        email_content: str,
        context: dict[str, Any],
        system_prompt: str,
        prompt_template: str,
        intent_categories: list[str],
    ) -> ClassificationResult:
        """Classify the intent of an email using OpenAI.

        Formats the prompt template with the provided email content, context,
        and intent categories, then sends it to the OpenAI chat completions
        API with JSON response format. The response is parsed to extract
        structured classification fields.

        Args:
            email_content: The raw email text to classify.
            context: Additional context about the deal/contact.
            system_prompt: The system-level instruction for the model.
            prompt_template: A template string with placeholders for
                {email_content}, {context}, and {intent_categories}.
            intent_categories: The list of valid intent category labels.

        Returns:
            A ClassificationResult with the parsed intent, confidence score,
            reasoning, key phrases, direction, token usage, and latency.

        Raises:
            openai.APIError: If the OpenAI API returns an error.
            json.JSONDecodeError: If the model response is not valid JSON.
            KeyError: If required fields are missing from the parsed response.
        """
        user_prompt = prompt_template.format(
            email_content=email_content,
            context=json.dumps(context, default=str),
            intent_categories=", ".join(intent_categories),
        )

        logger.debug(
            "openai_classify_intent_request",
            model=self._model,
            content_length=len(email_content),
            categories=intent_categories,
        )

        start = time.monotonic()

        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=1024,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        latency_ms = (time.monotonic() - start) * 1000

        raw_text = response.choices[0].message.content
        parsed = json.loads(raw_text)

        result = ClassificationResult(
            intent=parsed["intent"],
            confidence_score=float(parsed["confidence_score"]),
            reasoning=parsed["reasoning"],
            key_phrases=parsed.get("key_phrases", []),
            direction=parsed.get("direction", "unknown"),
            model=self._model,
            latency_ms=round(latency_ms, 2),
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            raw_response=raw_text,
        )

        logger.info(
            "openai_classify_intent_success",
            intent=result.intent,
            confidence=result.confidence_score,
            latency_ms=result.latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )

        return result

    @circuit_breaker(name="llm_openai", failure_threshold=3, reset_timeout=30)
    async def health_check(self) -> bool:
        """Check connectivity to the OpenAI API.

        Sends a minimal chat completion request to verify that the API key is
        valid and the service is reachable.

        Returns:
            True if the API responds successfully, False otherwise.
        """
        try:
            await self._client.chat.completions.create(
                model=self._model,
                max_tokens=16,
                messages=[
                    {"role": "user", "content": "ping"},
                ],
            )
            logger.debug("openai_health_check_ok")
            return True
        except Exception as exc:
            logger.warning("openai_health_check_failed", error=str(exc))
            return False
