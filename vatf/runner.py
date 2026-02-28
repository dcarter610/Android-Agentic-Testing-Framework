from __future__ import annotations

import subprocess
import time
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any

from .interfaces import ArtifactStore, LLMProvider, MCPToolClient
from .models import (
    AgentDecision,
    Guardrails,
    RunIndexRecord,
    Scenario,
    ScenarioResult,
    StepConclusion,
    StepResult,
    now_iso,
)


class AgenticScenarioRunner:
    def __init__(
        self,
        llm: LLMProvider,
        tools: MCPToolClient,
        artifacts: ArtifactStore,
        guardrails: Guardrails | None = None,
        device_name: str = "android-emulator",
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.artifacts = artifacts
        self.guardrails = guardrails or Guardrails()
        self.device_name = device_name

    def run(self, scenario: Scenario) -> ScenarioResult:
        run_id = datetime.utcnow().strftime("run_%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
        started = time.time()
        started_at = now_iso()
        step_results: list[StepResult] = []

        self._apply_preconditions(run_id, scenario)

        for idx, step in enumerate(scenario.steps, start=1):
            result = self._run_step(run_id, scenario, idx, step.goal, step.inputs, step.expected, step.tool_calls)
            step_results.append(result)
            if result.status != "PASS":
                break

        finished = time.time()
        final_status = "PASS" if all(s.status == "PASS" for s in step_results) else "FAIL"
        scenario_result = ScenarioResult(
            run_id=run_id,
            scenario_id=scenario.id,
            status=final_status,
            started_at=started_at,
            finished_at=now_iso(),
            duration_s=round(finished - started, 2),
            git_commit=self._git_commit(),
            device_name=self.device_name,
            step_results=step_results,
        )

        self.artifacts.write_json(run_id, scenario.id, "scenario_result.json", asdict(scenario_result))
        self._update_run_index(scenario_result)
        return scenario_result

    def _apply_preconditions(self, run_id: str, scenario: Scenario) -> None:
        logs: list[str] = []
        for p in scenario.preconditions:
            if p.get("reset_app_data"):
                self.tools.call("device.clear_app_data", {"package": p.get("package", "")})
                logs.append("Applied reset_app_data")

            if p.get("install_apk"):
                self.tools.call("device.install_apk", {"path": p.get("install_apk")})
                logs.append(f"Installed APK: {p.get('install_apk')}")

            if p.get("force_stop"):
                self.tools.call("device.force_stop", {"package": p.get("force_stop")})
                logs.append(f"Force-stopped package: {p.get('force_stop')}")

            if p.get("launch_app"):
                launch_cfg = p.get("launch_app") or {}
                self.tools.call(
                    "device.launch_app",
                    {
                        "package": launch_cfg.get("package", ""),
                        "activity": launch_cfg.get("activity", ""),
                    },
                )
                logs.append(
                    f"Launched app: {launch_cfg.get('package', '')}/{launch_cfg.get('activity', '')}"
                )

        if logs:
            self.artifacts.write_text(run_id, scenario.id, "preconditions.log", "\n".join(logs) + "\n")

    def _run_step(
        self,
        run_id: str,
        scenario: Scenario,
        step_index: int,
        goal: str,
        inputs: dict[str, Any],
        expected: list[str],
        tool_calls: list[dict[str, Any]],
    ) -> StepResult:
        retries = 0
        while retries <= self.guardrails.max_retries_per_step:
            started = time.time()
            timeline: list[dict[str, Any]] = []
            action_count = 0
            passed = False
            while time.time() - started <= self.guardrails.max_time_per_step_s and action_count < self.guardrails.max_actions_per_step:
                obs = self._observe()
                timeline.append({"phase": "observe", "payload": obs, "ts": now_iso()})

                decision = self._decide(goal, inputs, expected, obs)
                timeline.append({"phase": "decide", "payload": asdict(decision), "ts": now_iso()})

                for call in tool_calls:
                    timeline.append({"phase": "act", "payload": {"tool_call": call}, "ts": now_iso()})
                    # support explicit audio shorthand from scenarios
                    if "mcp_audio_play" in call:
                        audio_args = call["mcp_audio_play"] if isinstance(call["mcp_audio_play"], dict) else {}
                        self._run_audio_flow(audio_args, timeline)
                        action_count += 1
                        continue
                    # Expect one-key dict: {tool_name: args}
                    for name, args in call.items():
                        self.tools.call(name, args if isinstance(args, dict) else {})
                        action_count += 1

                for action in decision.next_actions:
                    resp = self.tools.call(action["tool"], action.get("args", {}))
                    timeline.append({"phase": "act", "payload": {"action": action, "response": resp}, "ts": now_iso()})
                    action_count += 1
                    if action_count >= self.guardrails.max_actions_per_step:
                        break

                if self._has_crash(obs):
                    conclusion = StepConclusion(
                        step_result="FAIL",
                        confidence=0.99,
                        evidence=["Crash signature detected in logcat"],
                        failure_category="CRASH",
                        improvement_suggestions=["Collect tombstone and inspect recent UI actions"],
                    )
                    return self._step_result(run_id, scenario.id, step_index, goal, retries, started, timeline, action_count, conclusion)

                verify_obs = self._observe()
                timeline.append({"phase": "verify", "payload": verify_obs, "ts": now_iso()})

                conclusion = self._conclude(goal, expected, verify_obs, decision)
                timeline.append({"phase": "conclude", "payload": asdict(conclusion), "ts": now_iso()})

                if conclusion.step_result == "PASS" or decision.stop_condition:
                    passed = conclusion.step_result == "PASS"
                    break

            if passed:
                return self._step_result(run_id, scenario.id, step_index, goal, retries, started, timeline, action_count, conclusion)
            retries += 1

        fail = StepConclusion(
            step_result="FAIL",
            confidence=0.7,
            evidence=["Step exceeded retries or guardrail limits"],
            failure_category="TIMEOUT_OR_BUDGET",
            improvement_suggestions=["Refine selectors and assertions for this screen"],
        )
        return self._step_result(run_id, scenario.id, step_index, goal, retries, time.time(), [], 0, fail)

    def _observe(self) -> dict[str, Any]:
        screenshot = self.tools.call("device.screenshot", {})
        tree = self.tools.call("device.dump_ui_tree", {})
        activity = self.tools.call("device.current_activity", {})
        logcat = self.tools.call("device.get_logcat", {"since_timestamp": now_iso()})
        return {"screenshot": screenshot, "ui_tree": tree, "activity": activity, "logcat": logcat}

    def _decide(self, goal: str, inputs: dict[str, Any], expected: list[str], observation: dict[str, Any]) -> AgentDecision:
        messages = [
            {"role": "system", "content": "You are an Android test agent. Return strict JSON."},
            {
                "role": "user",
                "content": {
                    "goal": goal,
                    "inputs": inputs,
                    "expected": expected,
                    "observation": observation,
                },
            },
        ]
        raw = self.llm.chat_with_tools(messages, schema_name="agent_decision")
        return AgentDecision(**raw)

    def _conclude(self, goal: str, expected: list[str], observation: dict[str, Any], decision: AgentDecision) -> StepConclusion:
        messages = [
            {"role": "system", "content": "Conclude if step has passed. Return strict JSON."},
            {
                "role": "user",
                "content": {
                    "goal": goal,
                    "expected": expected,
                    "observation": observation,
                    "assertions": decision.assertions_to_check,
                },
            },
        ]
        raw = self.llm.chat_with_tools(messages, schema_name="step_conclusion")
        return StepConclusion(**raw)

    @staticmethod
    def _has_crash(observation: dict[str, Any]) -> bool:
        log_text = str(observation.get("logcat", ""))
        crash_signatures = ["FATAL EXCEPTION", "ANR in", "Process .* has died"]
        return any(sig in log_text for sig in crash_signatures)

    def _run_audio_flow(self, audio_args: dict[str, Any], timeline: list[dict[str, Any]]) -> None:
        filename = audio_args.get("filename")
        self.tools.call("audio_playback", {"action": "play", "filename": filename, "loop": False})
        timeline.append({"phase": "audio", "payload": {"event": "play", "filename": filename}, "ts": now_iso()})
        for _ in range(120):
            status = self.tools.call("audio_playback", {"action": "status"})
            timeline.append({"phase": "audio", "payload": {"event": "status", "status": status}, "ts": now_iso()})
            if status.get("state") in {"stopped", "idle", "completed"} or status.get("is_playing") is False:
                break
            time.sleep(0.5)
        time.sleep(1.5)

    def _step_result(
        self,
        run_id: str,
        scenario_id: str,
        index: int,
        goal: str,
        retries: int,
        started: float,
        timeline: list[dict[str, Any]],
        action_count: int,
        conclusion: StepConclusion,
    ) -> StepResult:
        timeline_path = self.artifacts.write_json(run_id, scenario_id, f"step_{index:02d}_timeline.json", timeline)
        self.artifacts.write_json(run_id, scenario_id, f"step_{index:02d}_evaluation.json", asdict(conclusion))
        return StepResult(
            index=index,
            goal=goal,
            status=conclusion.step_result,
            retries=retries,
            duration_s=round(time.time() - started, 2),
            conclusion=conclusion,
            action_count=action_count,
            timeline_path=str(timeline_path),
        )

    @staticmethod
    def _git_commit() -> str:
        try:
            return (
                subprocess.check_output(["git", "rev-parse", "HEAD"], text=True)
                .strip()
            )
        except Exception:  # noqa: BLE001
            return "unknown"

    def _update_run_index(self, result: ScenarioResult) -> None:
        index_path = self.artifacts.out_root / "run_index.json"
        records = []
        if index_path.exists():
            import json

            records = json.loads(index_path.read_text(encoding="utf-8"))

        rec = RunIndexRecord(
            run_id=result.run_id,
            scenario_id=result.scenario_id,
            status=result.status,
            duration_s=result.duration_s,
            git_commit=result.git_commit,
            device_name=result.device_name,
            started_at=result.started_at,
            finished_at=result.finished_at,
        )
        records.append(asdict(rec))
        self.artifacts.write_json(result.run_id, result.scenario_id, "run_record.json", asdict(rec))
        index_path.write_text(__import__("json").dumps(records, indent=2), encoding="utf-8")
