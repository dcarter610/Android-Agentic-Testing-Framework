from __future__ import annotations

from typing import Any, Callable

from .interfaces import MCPToolClient


class GenericMCPToolClient(MCPToolClient):
    """Thin MCP function-calling facade.

    transport should accept `(tool_name, args)` and return dict.
    """

    def __init__(self, transport: Callable[[str, dict[str, Any]], dict[str, Any]]) -> None:
        self._transport = transport

    def call(self, tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._transport(tool, args or {})
