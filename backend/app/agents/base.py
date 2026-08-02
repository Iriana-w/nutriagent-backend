"""
NutriAgent Backend — Base Agent.

Abstract base class providing LLM client setup, structured output parsing,
and common agent utilities. Uses httpx directly for OpenAI-compatible API calls
(works with DeepSeek, OpenAI, and any compatible endpoint).
"""

from __future__ import annotations

import json
import re
from abc import ABC
from typing import Any

import httpx

from app.config import settings


class BaseAgent(ABC):
    """Abstract base for all NutriAgent AI agents.

    Provides:
    - LLM client via httpx (OpenAI-compatible API, works with DeepSeek)
    - Structured JSON output parsing
    - Prompt template rendering
    """

    def __init__(
        self,
        model_name: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.model_name = model_name or settings.DEFAULT_LLM_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def invoke_llm(
        self,
        system_prompt: str,
        user_message: str,
        *,
        response_format: str = "text",  # "text" | "json"
    ) -> str:
        """Call the LLM via OpenAI-compatible API (DeepSeek, OpenAI, etc.)"""
        api_key = settings.OPENAI_API_KEY
        base_url = (settings.OPENAI_BASE_URL or "https://api.deepseek.com/v1").rstrip("/")
        url = f"{base_url}/chat/completions"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    @staticmethod
    def parse_json_response(response_text: str) -> dict[str, Any]:
        """Extract and parse JSON from an LLM response."""
        json_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?```",
            response_text,
            re.DOTALL,
        )
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response_text.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            cleaned = re.sub(r",\s*}", "}", json_str)
            cleaned = re.sub(r",\s*]", "]", cleaned)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                return {"error": "Failed to parse JSON", "raw": response_text}

    @staticmethod
    def render_template(template: str, variables: dict[str, Any]) -> str:
        """Simple variable substitution using {{variable}} syntax."""
        result = template
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            if isinstance(value, (list, dict)):
                value = json.dumps(value, ensure_ascii=False, indent=2)
            result = result.replace(placeholder, str(value))
        return result

    @classmethod
    def get_fast_model(cls) -> "BaseAgent":
        return cls(model_name=settings.FAST_LLM_MODEL, temperature=0.3, max_tokens=1024)

    @classmethod
    def get_deep_model(cls) -> "BaseAgent":
        return cls(model_name=settings.DEEP_LLM_MODEL, temperature=0.5, max_tokens=4096)
