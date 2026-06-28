import logging

import google.generativeai as genai

from app.config import get_settings

log = logging.getLogger("app.llm")

_configured = False


def ensure_configured() -> None:
    global _configured
    if not _configured:
        genai.configure(api_key=get_settings().gemini_api_key)
        _configured = True
        log.info("Gemini configured with model %s", get_settings().gemini_model)


def build_model(system_instruction: str, tools: list):
    """A GenerativeModel wired with the ERP tools and the role-aware system prompt.

    We keep automatic function calling off and drive the loop ourselves in the
    agent, so we can record the plan and the tools actually used.
    """
    ensure_configured()
    return genai.GenerativeModel(
        get_settings().gemini_model,
        system_instruction=system_instruction,
        tools=tools,
    )
