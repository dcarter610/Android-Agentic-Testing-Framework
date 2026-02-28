from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any
import json


@dataclass
class Guardrails:
    max_actions_per_step: int = 50
    max_time_per_step_s: int = 300
    max_retries_per_step: int = 2


@dataclass
class ScenarioStep:
    goal: str
    inputs: dict[str, Any] = field(default_factory=dict)
    expected: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Scenario:
    id: str
    description: str
    preconditions: list[dict[str, Any]] = field(default_factory=list)
    steps: list[ScenarioStep] = field(default_factory=list)


@dataclass
class AgentDecision:
    thought_summary: str
    current_screen_hypothesis: str
    next_actions: list[dict[str, Any]]
    expected_observation_after_actions: str
    assertions_to_check: list[str]
    stop_condition: bool
    risk_flags: list[str] = field(default_factory=list)


@dataclass
class StepConclusion:
    step_result: str
    confidence: float
    evidence: list[str]
    failure_category: str | None
    improvement_suggestions: list[str]


@dataclass
class StepResult:
    index: int
    goal: str
    status: str
    retries: int
    duration_s: float
    conclusion: StepConclusion
    action_count: int
    timeline_path: str


@dataclass
class ScenarioResult:
    run_id: str
    scenario_id: str
    status: str
    started_at: str
    finished_at: str
    duration_s: float
    git_commit: str
    device_name: str
    step_results: list[StepResult]


@dataclass
class RunIndexRecord:
    run_id: str
    scenario_id: str
    status: str
    duration_s: float
    git_commit: str
    device_name: str
    started_at: str
    finished_at: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
