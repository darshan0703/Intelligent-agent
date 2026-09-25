"""Prompt registry — loads YAML prompt files and composes prompts with variable substitution."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from app.observability.logging import get_logger

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent


class PromptRegistry:
    """Loads YAML prompt definitions and renders them with variable substitution.

    Prompt YAML files live under ``app/prompts/v1/`` (or whichever *version*
    directory is configured).  Each file may declare ``inherits: '<name>'``
    which causes the parent prompt''s instructions to be prepended.

    Variable substitution uses ``{{ variable_name }}`` placeholders — the same
    style as Jinja2 but performed with a simple regex, keeping this module
    framework-free.
    """

    def __init__(self, version: str = "v1", domain: str = "qsr_india") -> None:
        self._version = version
        self._domain = domain
        self._cache: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, prompt_name: str, variables: dict[str, Any] | None = None) -> str:
        """Return the rendered instruction string for *prompt_name*.

        If the prompt declares ``inherits``, the parent is automatically
        prepended.  Domain-specific additions are appended when
        ``domain`` was provided at construction time.
        """
        variables = variables or {}
        raw = self._load(prompt_name)
        instructions = self._resolve_inheritance(raw, visited=set())
        rendered = self._substitute(instructions, variables)
        logger.debug(
            "prompt.rendered",
            prompt=prompt_name,
            variables=list(variables.keys()),
            length=len(rendered),
        )
        return rendered

    def compose(self, *prompt_names: str, variables: dict[str, Any] | None = None) -> str:
        """Concatenate multiple prompt sections in order, separated by blank lines."""
        variables = variables or {}
        parts: list[str] = []
        for name in prompt_names:
            parts.append(self.get(name, variables))
        return "\n\n".join(p.strip() for p in parts if p.strip())

    def get_domain_meta(self) -> dict[str, Any]:
        """Return raw domain YAML metadata (non-instruction fields)."""
        raw = self._load_domain()
        return {k: v for k, v in raw.items() if k != "instructions"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self, name: str) -> dict[str, Any]:
        """Load and cache a prompt YAML by name."""
        if name in self._cache:
            return self._cache[name]
        path = _PROMPTS_DIR / self._version / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Prompt not found: {path}")
        with path.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = yaml.safe_load(fh) or {}
        self._cache[name] = data
        return data

    def _load_domain(self) -> dict[str, Any]:
        """Load the current domain YAML."""
        domain_path = _PROMPTS_DIR / self._version / "domains" / f"{self._domain}.yaml"
        key = f"domains/{self._domain}"
        if key in self._cache:
            return self._cache[key]
        if not domain_path.exists():
            return {}
        with domain_path.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = yaml.safe_load(fh) or {}
        self._cache[key] = data
        return data

    def _resolve_inheritance(self, raw: dict[str, Any], visited: set[str]) -> str:
        """Recursively resolve ``inherits`` chains and return combined instructions."""
        instructions: str = raw.get("instructions", "")
        parent_name: str | None = raw.get("inherits")
        if parent_name:
            if parent_name in visited:
                raise ValueError(f"Circular prompt inheritance detected: {parent_name}")
            visited = visited | {parent_name}
            parent_raw = self._load(parent_name)
            parent_instructions = self._resolve_inheritance(parent_raw, visited)
            instructions = f"{parent_instructions}\n\n{instructions}"

        # Append domain locale notes if available
        domain = self._load_domain()
        locale_notes: str = domain.get("locale_notes", "")
        if locale_notes:
            instructions = f"{instructions}\n\nDOMAIN LOCALE NOTES:\n{locale_notes}"

        return instructions

    @staticmethod
    def _substitute(template: str, variables: dict[str, Any]) -> str:
        """Replace ``{{ key }}`` placeholders with values from *variables*."""

        def replacer(match: re.Match) -> str:  # type: ignore[type-arg]
            key = match.group(1).strip()
            value = variables.get(key, "")
            return str(value) if value is not None else ""

        return re.sub(r"\{\{\s*(\w+)\s*\}\}", replacer, template)

from functools import lru_cache

@lru_cache(maxsize=1)
def get_prompt_registry(version: str = 'v1', domain: str = 'qsr_india') -> PromptRegistry:
    return PromptRegistry(version=version, domain=domain)
