"""
NutriAgent Backend — Prompt Loader.

Loads and renders prompt templates from YAML files.
Used by the recommendation engine and agent nodes.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml


class PromptLoader:
    """
    Loads prompt templates from the prompts/templates/ directory.

    Templates use Jinja-like {{variable}} syntax and {{#optional}}...{{/optional}}
    conditional blocks.

    Usage:
        loader = PromptLoader()
        system, user = loader.render("meal", meal_type="lunch", ...)
    """

    TEMPLATES_DIR = Path(__file__).parent / "templates"

    def __init__(self):
        self._cache: dict[str, dict] = {}

    def load(self, template_name: str) -> dict:
        """Load a raw template by name (without .yaml extension)."""
        if template_name in self._cache:
            return self._cache[template_name]

        file_path = self.TEMPLATES_DIR / f"{template_name}.yaml"
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {file_path}")

        with open(file_path, encoding="utf-8") as f:
            template = yaml.safe_load(f)

        self._cache[template_name] = template
        return template

    def render(
        self,
        template_name: str,
        **variables,
    ) -> tuple[str, str]:
        """
        Render a template with the given variables.
        Returns (system_prompt, user_prompt).
        """
        template = self.load(template_name)

        system_prompt = template.get("system_prompt", "")
        user_prompt = template.get("user_prompt_template", "")

        # Process conditional blocks: {{#var}}...{{/var}}
        system_prompt = self._process_conditionals(system_prompt, variables)
        user_prompt = self._process_conditionals(user_prompt, variables)

        # Process variable substitution: {{var}}
        system_prompt = self._substitute(system_prompt, variables)
        user_prompt = self._substitute(user_prompt, variables)

        return system_prompt, user_prompt

    @staticmethod
    def _substitute(text: str, variables: dict) -> str:
        """Replace {{variable}} placeholders with values."""
        def replacer(match):
            key = match.group(1).strip()
            value = variables.get(key, "")
            if isinstance(value, (list, dict)):
                import json

                return json.dumps(value, ensure_ascii=False, indent=2)
            return str(value)

        return re.sub(r"\{\{(.*?)\}\}", replacer, text)

    @staticmethod
    def _process_conditionals(text: str, variables: dict) -> str:
        """
        Handle {{#var}}...{{/var}} conditional blocks.
        If `var` is truthy, keep the inner content (without tags).
        If falsy, remove the entire block including tags.
        """
        def replacer(match):
            var_name = match.group(1).strip()
            content = match.group(2)
            if variables.get(var_name):
                return content
            return ""

        # Match {{#var}}...{{/var}} across lines
        pattern = r"\{\{#(.*?)\}\}(.*?)\{\{/(.*?)\}\}"
        # Use DOTALL to match across newlines
        result = re.sub(pattern, replacer, text, flags=re.DOTALL)

        # Remove any remaining conditional tags (unmatched)
        result = re.sub(r"\{\{[#/].*?\}\}\n?", "", result)

        return result


# Singleton
prompt_loader = PromptLoader()
