from __future__ import annotations

import argparse
import json
from typing import Any

from .artifact_store import FilesystemArtifactStore
from .dashboard import LocalDashboardServer
from .llm_provider import StructuredLLMProvider
from .mcp_client import GenericMCPToolClient
from .runner import AgenticScenarioRunner
from .scenario import load_scenario


def mock_transport(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool == "audio_playback" and args.get("action") == "status":
        return {"state": "completed", "is_playing": False}
    return {"ok": True, "tool": tool, "args": args}


def mock_responder(messages: list[dict[str, Any]], schema_name: str) -> str:
    if schema_name == "agent_decision":
        return json.dumps(
            {
                "thought_summary": "Performing a safe next UI action based on visible state.",
                "current_screen_hypothesis": "Unknown screen",
                "next_actions": [{"tool": "ui.wait_for", "args": {"selector_or_text": "Home", "timeout_ms": 1000}}],
                "expected_observation_after_actions": "Expected element visible",
                "assertions_to_check": ["Expected text appears"],
                "stop_condition": False,
                "risk_flags": [],
            }
        )
    return json.dumps(
        {
            "step_result": "PASS",
            "confidence": 0.8,
            "evidence": ["Mock conclusion generated"],
            "failure_category": None,
            "improvement_suggestions": ["Replace mock LLM with production provider"],
        }
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="V-ATF runner")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run a single scenario")
    run.add_argument("--scenario", required=True)
    run.add_argument("--out", default="out")
    run.add_argument("--llm-backend", default="mock", choices=["mock"], help="LLM backend (currently mock only)")

    dash = sub.add_parser("dashboard", help="Serve dashboard")
    dash.add_argument("--out", default="out")
    dash.add_argument("--host", default="127.0.0.1")
    dash.add_argument("--port", type=int, default=8080)
    return p


def main() -> None:
    args = build_parser().parse_args()
    if args.cmd == "dashboard":
        LocalDashboardServer(out_root=args.out).serve(args.host, args.port)
        return

    scenario = load_scenario(args.scenario)
    artifacts = FilesystemArtifactStore(out_root=args.out)
    tools = GenericMCPToolClient(mock_transport)
    if args.llm_backend != "mock":
        raise ValueError("Unsupported LLM backend. Only mock is currently wired in this scaffold.")
    llm = StructuredLLMProvider(mock_responder)
    runner = AgenticScenarioRunner(llm=llm, tools=tools, artifacts=artifacts)
    result = runner.run(scenario)
    print(json.dumps(result, default=lambda o: o.__dict__, indent=2))


if __name__ == "__main__":
    main()
