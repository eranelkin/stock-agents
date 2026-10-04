from __future__ import annotations

import pytest

from ai_service.agent import Agent
from ai_service.config import settings
from ai_service.models.llm_client import LLMClient
from ai_service.pipeline import Pipeline
from ai_service.schemas.run import ModelConfig

GEMINI_MODEL = ModelConfig(id="m1", name="gemini", model_id="gemini/gemini-2.5-pro")
GPT_MODEL = ModelConfig(id="m2", name="gpt", model_id="gpt-4o")


def _make_agent(*, env: str, llm_client: LLMClient, search_enabled: bool = True) -> Agent:
    return Agent(
        agent_id="news",
        prompt="p",
        llm_client=llm_client,
        env=env,
        search_enabled=search_enabled,
    )


@pytest.fixture(autouse=True)
def _reset_grounding_flag():
    original = settings.search_grounding_enabled_test
    yield
    settings.search_grounding_enabled_test = original


class TestAgentUseGrounding:
    def test_grounding_used_in_test_env_for_gemini_model(self):
        settings.search_grounding_enabled_test = True
        agent = _make_agent(env="test", llm_client=LLMClient(GEMINI_MODEL))
        assert agent._use_grounding is True

    def test_grounding_not_used_in_prod_env_even_for_gemini_model(self):
        settings.search_grounding_enabled_test = True
        agent = _make_agent(env="prod", llm_client=LLMClient(GEMINI_MODEL))
        assert agent._use_grounding is False

    def test_grounding_not_used_for_non_gemini_model_in_test_env(self):
        settings.search_grounding_enabled_test = True
        agent = _make_agent(env="test", llm_client=LLMClient(GPT_MODEL))
        assert agent._use_grounding is False

    def test_grounding_disabled_by_rollback_flag_even_in_test_env(self):
        settings.search_grounding_enabled_test = False
        agent = _make_agent(env="test", llm_client=LLMClient(GEMINI_MODEL))
        assert agent._use_grounding is False

    def test_grounding_not_used_when_search_not_enabled_for_prompt(self):
        settings.search_grounding_enabled_test = True
        agent = _make_agent(env="test", llm_client=LLMClient(GEMINI_MODEL), search_enabled=False)
        assert agent._use_grounding is False


class TestPipelineUseGrounding:
    def _make_pipeline(self, *, env: str, llm_client: LLMClient) -> Pipeline:
        import asyncio

        return Pipeline(
            entity=None,  # not touched by __init__
            entity_name="AAPL",
            prompts=[],
            pipeline_semaphore=asyncio.Semaphore(1),
            llm_client=llm_client,
            model_name=llm_client.model_id,
            env=env,
        )

    def test_pipeline_uses_grounding_in_test_env_for_gemini_model(self):
        settings.search_grounding_enabled_test = True
        pipeline = self._make_pipeline(env="test", llm_client=LLMClient(GEMINI_MODEL))
        assert pipeline._use_grounding is True

    def test_pipeline_does_not_use_grounding_in_prod_env(self):
        settings.search_grounding_enabled_test = True
        pipeline = self._make_pipeline(env="prod", llm_client=LLMClient(GEMINI_MODEL))
        assert pipeline._use_grounding is False

    def test_pipeline_respects_rollback_flag(self):
        settings.search_grounding_enabled_test = False
        pipeline = self._make_pipeline(env="test", llm_client=LLMClient(GEMINI_MODEL))
        assert pipeline._use_grounding is False
