from __future__ import annotations

# Gemini's native "Google Search" grounding tool. litellm recognizes this exact
# shape for gemini/* and vertex_ai/gemini* models and transforms it into the
# provider's native Tools(googleSearch={}) request — the model searches live
# during its own generation and returns grounded text directly, with no
# client-side tool-call loop required (unlike Tavily's WEB_SEARCH_TOOL).
GOOGLE_GROUNDING_TOOL: list[dict] = [{"googleSearch": {}}]

_GEMINI_PREFIXES = ("gemini/", "vertex_ai/gemini")


def is_gemini_model(model_id: str) -> bool:
    """Return True if this litellm model_id string identifies a Gemini model."""
    return model_id.startswith(_GEMINI_PREFIXES)
