from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Callable

if __package__ in (None, ""):
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quartus_mcp.quartus_cli import (
    compile_project,
    create_counter_project,
    detect_quartus_installation,
    run_vwf_simulation,
    summarize_quartus_reports,
)


ToolHandler = Callable[..., dict[str, Any]]


TOOLS: dict[str, dict[str, Any]] = {
    "detect_quartus_installation": {
        "description": "Detect the configured Quartus II 9.1 installation and command-line tools.",
        "handler": detect_quartus_installation,
        "schema": {
            "type": "object",
            "properties": {
                "quartus_bin": {
                    "type": "string",
                    "description": "Path to the Quartus bin or bin64 directory. If omitted, the server reads the QUARTUS_BIN environment variable.",
                }
            },
        },
    },
    "create_counter_project": {
        "description": "Create a MAX II EPM1270T144C5 counter demo project with QPF, QSF, VHDL, and VWF files.",
        "handler": create_counter_project,
        "schema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "default": "counter_demo"},
                "output_dir": {"type": "string", "description": "Optional output directory for the generated project."},
                "top_entity": {"type": "string", "default": "counter_demo"},
                "simulation_time_ns": {"type": "integer", "default": 50000},
                "grid_period_ns": {"type": "integer", "default": 100},
                "overwrite": {"type": "boolean", "default": False},
            },
        },
    },
    "compile_project": {
        "description": "Run quartus_sh --flow compile for an existing Quartus project.",
        "handler": compile_project,
        "schema": {
            "type": "object",
            "required": ["project_dir"],
            "properties": {
                "project_dir": {"type": "string"},
                "project_name": {"type": "string", "default": "counter_demo"},
                "quartus_bin": {
                    "type": "string",
                    "description": "Path to the Quartus bin or bin64 directory. If omitted, the server reads the QUARTUS_BIN environment variable.",
                },
                "timeout_sec": {"type": "integer", "default": 600},
            },
        },
    },
    "run_vwf_simulation": {
        "description": "Run quartus_sim with a VWF input source, CVWF output format, and waveform overwrite disabled.",
        "handler": run_vwf_simulation,
        "schema": {
            "type": "object",
            "required": ["project_dir"],
            "properties": {
                "project_dir": {"type": "string"},
                "project_name": {"type": "string", "default": "counter_demo"},
                "quartus_bin": {
                    "type": "string",
                    "description": "Path to the Quartus bin or bin64 directory. If omitted, the server reads the QUARTUS_BIN environment variable.",
                },
                "timeout_sec": {"type": "integer", "default": 600},
            },
        },
    },
    "summarize_quartus_reports": {
        "description": "Summarize Quartus report, log, SOF, and CVWF files in a project directory.",
        "handler": summarize_quartus_reports,
        "schema": {
            "type": "object",
            "required": ["project_dir"],
            "properties": {
                "project_dir": {"type": "string"},
                "max_chars_per_file": {"type": "integer", "default": 4000},
            },
        },
    },
}


def _tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": meta["description"],
            "inputSchema": meta["schema"],
        }
        for name, meta in TOOLS.items()
    ]


def _success(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
    if data is not None:
        payload["error"]["data"] = data
    return payload


def _text_content(data: Any) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(data, ensure_ascii=False, indent=2),
            }
        ]
    }


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")

    if request_id is None and method and method.startswith("notifications/"):
        return None

    if method == "initialize":
        return _success(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "quartus-mcp-server", "version": "0.1.0"},
            },
        )

    if method == "tools/list":
        return _success(request_id, {"tools": _tool_definitions()})

    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in TOOLS:
            return _error(request_id, -32602, f"Unknown tool: {name}")
        try:
            handler: ToolHandler = TOOLS[name]["handler"]
            result = handler(**arguments)
            return _success(request_id, _text_content(result))
        except Exception as exc:  # MCP needs structured errors instead of stderr-only crashes.
            return _success(
                request_id,
                _text_content(
                    {
                        "ok": False,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    }
                ),
            )

    if method == "ping":
        return _success(request_id, {})

    return _error(request_id, -32601, f"Method not found: {method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            response = handle_request(message)
        except Exception as exc:
            response = _error(None, -32700, str(exc), traceback.format_exc())
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
