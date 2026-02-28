from __future__ import annotations

import json
from typing import Any, Callable

from .interfaces import LLMProvider


DECISION_SCHEMA_KEYS = {
    "thought_summary",
    "current_screen_hypothesis",
    "next_actions",
    "expected_observation_after_actions",
    "assertions_to_check",
    "stop_condition",
    "risk_flags",
}

CONCLUSION_SCHEMA_KEYS = {
    "step_result",
    "confidence",
    "evidence",
    "failure_category",
    "improvement_suggestions",
}


class StructuredLLMProvider(LLMProvider):
    """Adapter around chat backends with strict JSON contract enforcement."""

    def __init__(self, responder: Callable[[list[dict[str, Any]], str], str], max_repair_attempts: int = 2) -> None:
        self._responder = responder
        self._max_repair_attempts = max_repair_attempts

    def chat_with_tools(self, messages: list[dict[str, Any]], schema_name: str) -> dict[str, Any]:
        prompt = schema_name
        raw = None
        for attempt in range(self._max_repair_attempts + 1):
            raw = self._responder(messages, prompt)
            try:
                payload = json.loads(raw)
                self._validate(payload, schema_name)
                return payload
            except Exception as exc:  # noqa: BLE001
                if attempt < self._max_repair_attempts:
                    messages = messages + [{"role": "system", "content": f"Return valid JSON for {schema_name}: {exc}"}]
        raise ValueError(f"Unable to parse valid {schema_name} payload from model")

    @staticmethod
    def _validate(payload: dict[str, Any], schema_name: str) -> None:
        required = DECISION_SCHEMA_KEYS if schema_name == "agent_decision" else CONCLUSION_SCHEMA_KEYS
        missing = [k for k in required if k not in payload]
        if missing:
            raise ValueError(f"Missing keys: {missing}")
