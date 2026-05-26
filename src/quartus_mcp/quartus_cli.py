from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .templates import (
    DEFAULT_PROJECT_NAME,
    DEFAULT_TOP_ENTITY,
    QUARTUS_BIN_ENV_VAR,
    render_counter_project_files,
)


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PROJECTS_DIR = ROOT_DIR / "projects"


@dataclass
class CommandResult:
    command: list[str]
    cwd: str
    returncode: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _exe(quartus_bin: str | Path, name: str) -> Path:
    return Path(quartus_bin) / f"{name}.exe"


def _resolve_quartus_bin(quartus_bin: str | Path | None = None) -> Path:
    configured = quartus_bin or os.environ.get(QUARTUS_BIN_ENV_VAR)
    if not configured:
        raise ValueError(
            f"Quartus bin directory is not configured. Pass quartus_bin or set the {QUARTUS_BIN_ENV_VAR} environment variable."
        )
    return Path(configured).expanduser()


def _run(command: list[str], cwd: str | Path | None = None, timeout_sec: int = 600) -> CommandResult:
    workdir = str(cwd or ROOT_DIR)
    env = os.environ.copy()
    try:
        process = subprocess.run(
            command,
            cwd=workdir,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            check=False,
        )
        return CommandResult(command=command, cwd=workdir, returncode=process.returncode, stdout=process.stdout, stderr=process.stderr)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr = (stderr + f"\nCommand timed out after {timeout_sec} seconds.").strip()
        return CommandResult(command=command, cwd=workdir, returncode=124, stdout=stdout, stderr=stderr)


def _first_version_line(text: str) -> str | None:
    for line in text.splitlines():
        if "Version" in line and "Quartus" not in line:
            return line.strip()
        if line.startswith("Version "):
            return line.strip()
    return None


def detect_quartus_installation(quartus_bin: str | None = None) -> dict[str, Any]:
    resolved_bin = _resolve_quartus_bin(quartus_bin)
    tools = ["quartus_sh", "quartus_map", "quartus_fit", "quartus_asm", "quartus_sta", "quartus_tan", "quartus_sim"]
    tool_status: dict[str, Any] = {}
    for tool in tools:
        path = _exe(resolved_bin, tool)
        entry: dict[str, Any] = {"path": str(path), "exists": path.exists()}
        if path.exists() and tool == "quartus_sh":
            result = _run([str(path), "--help"], timeout_sec=15)
            entry["returncode"] = result.returncode
            entry["version_line"] = _first_version_line(result.stdout + result.stderr)
        tool_status[tool] = entry

    shell = tool_status["quartus_sh"]
    return {
        "quartus_bin": str(resolved_bin),
        "ok": all(item["exists"] for item in tool_status.values()),
        "quartus_sh_version": shell.get("version_line"),
        "tools": tool_status,
    }


def _project_dir(project_name: str, output_dir: str | None) -> Path:
    if output_dir:
        return Path(output_dir)
    return DEFAULT_PROJECTS_DIR / project_name


def create_counter_project(
    project_name: str = DEFAULT_PROJECT_NAME,
    output_dir: str | None = None,
    top_entity: str = DEFAULT_TOP_ENTITY,
    simulation_time_ns: int = 50000,
    grid_period_ns: int = 100,
    overwrite: bool = False,
) -> dict[str, Any]:
    project_dir = _project_dir(project_name, output_dir)
    if project_dir.exists() and any(project_dir.iterdir()) and not overwrite:
        return {
            "ok": False,
            "error": "Project directory already exists and is not empty. Pass overwrite=true to replace generated files.",
            "project_dir": str(project_dir),
        }

    project_dir.mkdir(parents=True, exist_ok=True)
    files = render_counter_project_files(project_name, top_entity, simulation_time_ns, grid_period_ns)
    paths = {
        "qpf": project_dir / f"{project_name}.qpf",
        "qsf": project_dir / f"{top_entity}.qsf",
        "vhdl": project_dir / f"{top_entity}.vhd",
        "vwf": project_dir / f"{top_entity}.vwf",
    }
    paths["qpf"].write_text(files.qpf, encoding="utf-8", newline="\n")
    paths["qsf"].write_text(files.qsf, encoding="utf-8", newline="\n")
    paths["vhdl"].write_text(files.vhdl, encoding="utf-8", newline="\n")
    paths["vwf"].write_text(files.vwf, encoding="utf-8", newline="\n")

    return {
        "ok": True,
        "project_name": project_name,
        "top_entity": top_entity,
        "project_dir": str(project_dir),
        "files": {key: str(value) for key, value in paths.items()},
        "simulation_time_ns": simulation_time_ns,
        "grid_period_ns": grid_period_ns,
    }


def _find_project_file(project_dir: Path, project_name: str) -> Path:
    direct = project_dir / f"{project_name}.qpf"
    if direct.exists():
        return direct
    matches = sorted(project_dir.glob("*.qpf"))
    if not matches:
        raise FileNotFoundError(f"No .qpf file found in {project_dir}")
    return matches[0]


def _latest_files(project_dir: Path, patterns: list[str]) -> list[str]:
    found: list[Path] = []
    for pattern in patterns:
        found.extend(project_dir.rglob(pattern))
    return [str(path) for path in sorted(found, key=lambda item: item.stat().st_mtime, reverse=True)]


def _programming_files(project_dir: Path) -> list[str]:
    return _latest_files(project_dir, ["*.sof", "*.pof", "*.jic", "*.jam", "*.jbc"])


def _copy_cvwf_to_project_root(project_dir: Path, cvwf_files: list[str]) -> list[str]:
    copied: list[str] = []
    for source_text in cvwf_files:
        source = Path(source_text)
        if not source.exists() or source.parent == project_dir:
            continue
        target = project_dir / source.name
        shutil.copy2(source, target)
        copied.append(str(target))
    return copied


def _read_text_if_exists(path: Path, max_chars: int = 12000) -> str | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]


def _extract_messages(text: str) -> dict[str, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.search(r"\bError\b", stripped, re.IGNORECASE):
            errors.append(stripped)
        elif re.search(r"\bWarning\b", stripped, re.IGNORECASE):
            warnings.append(stripped)
    return {"errors": errors[-50:], "warnings": warnings[-50:]}


def compile_project(project_dir: str, project_name: str = DEFAULT_PROJECT_NAME, quartus_bin: str | None = None, timeout_sec: int = 600) -> dict[str, Any]:
    root = Path(project_dir)
    qpf = _find_project_file(root, project_name)
    resolved_bin = _resolve_quartus_bin(quartus_bin)
    command = [str(_exe(resolved_bin, "quartus_sh")), "--flow", "compile", qpf.stem]
    result = _run(command, cwd=root, timeout_sec=timeout_sec)
    combined = result.stdout + "\n" + result.stderr
    messages = _extract_messages(combined)
    reports = _latest_files(root, ["*.rpt", "*.summary"])
    sofs = _latest_files(root, ["*.sof"])
    programming_files = _programming_files(root)
    return {
        "ok": result.returncode == 0,
        "project_dir": str(root),
        "project_name": qpf.stem,
        "command": result.to_dict(),
        "errors": messages["errors"],
        "warnings": messages["warnings"],
        "sof_files": sofs,
        "programming_files": programming_files,
        "report_files": reports[:20],
    }


def run_vwf_simulation(project_dir: str, project_name: str = DEFAULT_PROJECT_NAME, quartus_bin: str | None = None, timeout_sec: int = 600) -> dict[str, Any]:
    root = Path(project_dir)
    qpf = _find_project_file(root, project_name)
    before = set(_latest_files(root, ["*.cvwf"]))
    resolved_bin = _resolve_quartus_bin(quartus_bin)
    command = [str(_exe(resolved_bin, "quartus_sh")), "--flow", "compile_and_simulate", qpf.stem]
    result = _run(command, cwd=root, timeout_sec=timeout_sec)
    after = _latest_files(root, ["*.cvwf"])
    new_cvwf = [path for path in after if path not in before]
    copied_cvwf = _copy_cvwf_to_project_root(root, new_cvwf or after)
    root_cvwf = sorted(str(path) for path in root.glob("*.cvwf"))
    combined = result.stdout + "\n" + result.stderr
    messages = _extract_messages(combined)
    ok = result.returncode == 0 and bool(after)
    response: dict[str, Any] = {
        "ok": ok,
        "project_dir": str(root),
        "project_name": qpf.stem,
        "command": result.to_dict(),
        "cvwf_files": after,
        "new_cvwf_files": new_cvwf,
        "copied_cvwf_files": copied_cvwf,
        "root_cvwf_files": root_cvwf,
        "errors": messages["errors"],
        "warnings": messages["warnings"],
    }
    if not after:
        response["note"] = (
            "Quartus did not produce a .cvwf file. If the hand-written VWF was rejected, "
            "open the .vwf in Quartus GUI, save it once, then rerun simulation."
        )
    return response


def summarize_quartus_reports(project_dir: str, max_chars_per_file: int = 4000) -> dict[str, Any]:
    root = Path(project_dir)
    files = [Path(path) for path in _latest_files(root, ["*.rpt", "*.summary", "*.log"])]
    summaries: list[dict[str, Any]] = []
    all_text = ""
    for path in files[:20]:
        text = _read_text_if_exists(path, max_chars=max_chars_per_file) or ""
        all_text += "\n" + text
        summaries.append(
            {
                "path": str(path),
                "size": path.stat().st_size,
                "tail": text,
            }
        )
    messages = _extract_messages(all_text)
    return {
        "ok": root.exists(),
        "project_dir": str(root),
        "report_count": len(files),
        "reports": summaries,
        "errors": messages["errors"],
        "warnings": messages["warnings"],
        "sof_files": _latest_files(root, ["*.sof"]),
        "programming_files": _programming_files(root),
        "cvwf_files": _latest_files(root, ["*.cvwf"]),
        "root_cvwf_files": sorted(str(path) for path in root.glob("*.cvwf")),
    }
