from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .models import AgentDecision, StepConclusion, Scenario, ScenarioResult


class LLMProvider(ABC):
    @abstractmethod
    def chat_with_tools(self, messages: list[dict[str, Any]], schema_name: str) -> dict[str, Any]:
        """Return machine-parseable JSON matching a requested schema."""


class MCPToolClient(ABC):
    @abstractmethod
    def call(self, tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call an MCP-style tool and return structured result payload."""


class ScenarioRunner(ABC):
    @abstractmethod
    def run(self, scenario: Scenario) -> ScenarioResult:
        """Execute a complete scenario."""


class ArtifactStore(ABC):
    @abstractmethod
    def scenario_dir(self, run_id: str, scenario_id: str) -> Path:
        ...

    @abstractmethod
    def write_json(self, run_id: str, scenario_id: str, name: str, payload: Any) -> Path:
        ...

    @abstractmethod
    def write_text(self, run_id: str, scenario_id: str, name: str, text: str) -> Path:
        ...


class DashboardServer(ABC):
    @abstractmethod
    def serve(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        ...
