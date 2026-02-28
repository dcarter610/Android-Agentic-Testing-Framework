# Vetnovia Android Agentic Testing Framework (V-ATF)

An agent-driven Android regression framework where the LLM decides *what to do next* and MCP tools execute actions on a device/emulator.

## What this repository provides

- Goal-based YAML scenario loading.
- A runner that enforces guardrails (timeouts, action budgets, retries, crash fail-fast).
- Mandatory observe → decide → act → verify agent loop.
- MCP tool mediation for device/UI/audio interactions.
- Artifact-rich execution outputs at `out/<run_id>/<scenario_id>/`.
- Local dashboard server for run list/detail/failure analysis.

## Quick start

```bash
python -m vatf.main run --scenario scenarios/sample_record_case.yaml
python -m vatf.main dashboard --out out --port 8080
```

## Scenario model

Scenarios are goal-driven and not hard-coded UI scripts. See `scenarios/sample_record_case.yaml`.

## Architecture

```
Scenario YAML
     ↓
Test Runner
     ↓
LLM Agent  ⇄  MCP Tool Layer
                 ├── MCP UI Automator
                 ├── MCP Device Control (ADB)
                 └── MCP Audio Playback
     ↓
Android Emulator (Vetnovia app)
     ↓
Artifacts + Results
     ↓
Web Dashboard
```

## Notes

- The agent is the primary decision-maker.
- The runner never scripts deterministic UI steps; it only enforces control limits and persistence.
- Audio playback completion is determined through `audio_playback(status)` polling.

## Device/Emulator startup behavior

By default, V-ATF does **not** start an Android emulator process for you.

- You should start an emulator/device before running tests.
- You should make sure the Vetnovia app is installed and launchable, **or** provide scenario preconditions that call MCP device tools such as `device.install_apk` and `device.launch_app` via runner-managed setup logic.

In other words: the framework orchestrates through MCP tools once execution begins, but environment boot (emulator process lifecycle) is expected to be handled by your local/device infrastructure unless you add a dedicated device bootstrap MCP tool in your stack.

## LLM connection and account/auth model

Current scaffold behavior:
- The CLI is wired to a **mock LLM backend** for local development.
- The framework architecture supports plugging in a real provider via `LLMProvider` (`chat_with_tools`).

About using a ChatGPT Pro account directly:
- **Not currently supported in this repo out-of-the-box.**
- ChatGPT web/app subscription credits are typically separate from API usage; this framework does not implement ChatGPT session/login-based auth.

What to use for production:
- Implement a concrete `LLMProvider` adapter that calls your chosen provider endpoint and enforces the required structured JSON outputs.
- In most setups, that means API-based auth (provider API key or enterprise gateway token).
