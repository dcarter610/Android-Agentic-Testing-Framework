from __future__ import annotations

import json
from pathlib import Path

from .models import Scenario, ScenarioStep


def load_scenario(path: str | Path) -> Scenario:
    p = Path(path)
    text = p.read_text(encoding="utf-8")

    data = None
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
    except Exception:
        # YAML parser not installed; accept JSON (valid YAML subset) for offline environments.
        data = json.loads(text)

    steps = [
        ScenarioStep(
            goal=s.get("goal", ""),
            inputs=s.get("inputs", {}) or {},
            expected=s.get("expected", []) or [],
            tool_calls=s.get("tool_calls", []) or [],
        )
        for s in data.get("steps", [])
    ]

    return Scenario(
        id=data["id"],
        description=data.get("description", ""),
        preconditions=data.get("preconditions", []) or [],
        steps=steps,
    )
