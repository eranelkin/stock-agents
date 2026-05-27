from __future__ import annotations

import litellm
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ai_service.config import settings
from ai_service.utils.logger import get_logger

logger = get_logger(__name__)


class LLMError(Exception):
    """Raised when an LLM call fails after all retries."""


class LLMClient:
    """Provider-agnostic async LLM client backed by litellm.acompletion."""

    def __init__(self) -> None:
        self._model = settings.llm_model

    async def complete(self, system_prompt: str, user_message: str) -> str:
        """Send a chat completion and return the response text.

        Retries up to 3 times on rate-limit or timeout errors, then raises LLMError.

        Args:
            system_prompt: Content for the system role.
            user_message: Content for the user role.

        Returns:
            Raw response string from the model.
        """
        try:
            return await self._complete_with_retry(system_prompt, user_message)
        except Exception as exc:
            logger.error("LLM completion failed after retries", exc_info=True)
            raise LLMError(str(exc)) from exc

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((litellm.RateLimitError, litellm.Timeout)),
    )
    async def _complete_with_retry(self, system_prompt: str, user_message: str) -> str:
        response = await litellm.acompletion(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
        )
        return response.choices[0].message.content or ""
