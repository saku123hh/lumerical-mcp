import os
import sys
import time
import json
import subprocess
import logging
from pathlib import Path
from typing import Any, Optional

from .config import Config

cfg = Config.load()

logging.basicConfig(level=cfg.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("lumerical-mcp")

for _directory in (cfg.lumerical_api_python, cfg.lumerical_bin):
    _directory_str = str(_directory)
    if _directory.exists():
        if _directory_str not in sys.path:
            sys.path.append(_directory_str)
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(_directory_str)
            except OSError:
                pass

import lumapi

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("lumerical")

fdtd = None
_gui_jobs: dict[str, dict[str, Any]] = {}


def _ensure_fdtd(hide: bool = False):
    global fdtd
    if fdtd is None:
        fdtd = lumapi.FDTD(hide=hide)
    return fdtd


def _jsonable(value: Any, max_array_items: int = 2000) -> Any:
    try:
        import numpy as np
    except Exception:
        np = None

    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}

    if np is not None:
        if isinstance(value, np.generic):
            return _jsonable(value.item(), max_array_items)
        if isinstance(value, np.ndarray):
            size = int(value.size)
            if size <= max_array_items:
                return {
                    "type": "ndarray",
                    "shape": list(value.shape),
                    "dtype": str(value.dtype),
                    "data": _jsonable(value.tolist(), max_array_items),
                }
            flat = value.ravel()
            return {
                "type": "ndarray",
                "shape": list(value.shape),
                "dtype": str(value.dtype),
                "size": size,
                "sample": _jsonable(flat[:20].tolist(), max_array_items),
                "truncated": True,
            }

    if isinstance(value, dict):
        return {str(k): _jsonable(v, max_array_items) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_jsonable(item, max_array_items) for item in value]

    return repr(value)


@mcp.tool()
def hello(name: str) -> str:
    return f"Hello {name}, MCP is working."


@mcp.tool()
def start_fdtd() -> str:
    global fdtd
    if fdtd is not None:
        return "FDTD is already running."
    fdtd = lumapi.FDTD()
    return "Lumerical FDTD started successfully."


@mcp.tool()
def end_fdtd() -> str:
    global fdtd
    if fdtd is None:
        return "No FDTD session is running."
    fdtd.close()
    fdtd = None
    return "Lumerical FDTD closed."


@mcp.tool()
def open_projects(path: str) -> str:
    session = _ensure_fdtd()
    session.load(str(cfg.work_dir / path) if not Path(path).is_absolute() else path)
    return f"Project opened: {path}"


@mcp.tool()
def set_parameter(object_name: str, property_name: str, value: float) -> str:
    if fdtd is None:
        return "FDTD is not running."
    fdtd.switchtolayout()
    fdtd.setnamed(object_name, property_name, value)
    return f"{object_name}: {property_name} = {value}"


@mcp.tool()
def run_simulation() -> str:
    if fdtd is None:
        return "FDTD is not running."
    fdtd.run()
    return "Simulation finished."


@mcp.tool()
def save_project(path: str) -> str:
    if fdtd is None:
        return "FDTD is not running."
    fdtd.save(str(cfg.work_dir / path) if not Path(path).is_absolute() else path)
    return f"Project saved: {path}"


@mcp.tool()
def get_transmission(monitor_name: str) -> dict:
    if fdtd is None:
        return {"error": "FDTD is not running."}
    result = fdtd.getresult(monitor_name, "T")
    wavelength = result["lambda"].flatten().flip()
    transmission = result["T"].flatten().flip()
    return {
        "wavelength_nm": (wavelength * 1e9).tolist(),
        "T": transmission.tolist(),
    }


@mcp.tool()
def fdtd_eval_script_tool(code: str) -> dict:
    session = _ensure_fdtd()
    session.eval(code)
    return {"ok": True, "executed": True}


@mcp.tool()
def fdtd_eval_script_get_tool(code: str, return_var: str, max_array_items: int = 2000) -> dict:
    session = _ensure_fdtd()
    session.eval(code)
    value = session.getv(return_var)
    return {
        "ok": True,
        "variable": return_var,
        "value": _jsonable(value, max_array_items),
    }


@mcp.tool()
def fdtd_run_script_file_tool(script_path: str) -> dict:
    session = _ensure_fdtd()
    path = str(cfg.work_dir / script_path) if not Path(script_path).is_absolute() else script_path
    if path.lower().endswith(".lsfx"):
        session.eval(path[:-5] + ";")
    else:
        session.feval(path)
    return {"ok": True, "script_path": path}


@mcp.tool()
def fdtd_get_variable_tool(name: str, max_array_items: int = 2000) -> dict:
    session = _ensure_fdtd()
    value = session.getv(name)
    return {
        "ok": True,
        "variable": name,
        "value": _jsonable(value, max_array_items),
    }


@mcp.tool()
def fdtd_put_variable_tool(name: str, value: Any) -> dict:
    session = _ensure_fdtd()
    session.putv(name, value)
    return {"ok": True, "variable": name}


@mcp.tool()
def fdtd_load_project_tool(project_path: str) -> dict:
    session = _ensure_fdtd()
    path = str(cfg.work_dir / project_path) if not Path(project_path).is_absolute() else project_path
    session.load(path)
    return {"ok": True, "project_path": path}


@mcp.tool()
def fdtd_save_project_tool(project_path: Optional[str] = None) -> dict:
    session = _ensure_fdtd()
    if project_path:
        path = str(cfg.work_dir / project_path) if not Path(project_path).is_absolute() else project_path
        session.save(path)
    else:
        session.save()
        path = None
    return {"ok": True, "project_path": path}


@mcp.tool()
def fdtd_run_simulation_tool() -> dict:
    session = _ensure_fdtd()
    started_at = time.time()
    session.eval("run;")
    return {"ok": True, "elapsed_seconds": time.time() - started_at}


@mcp.tool()
def fdtd_launch_gui_tool(target: str = "launcher", project_path: Optional[str] = None) -> dict:
    if target.lower() in {"fdtd", "fdtd-solutions", "solutions"}:
        exe = cfg.lumerical_bin / "fdtd-solutions.exe"
    else:
        exe = cfg.lumerical_bin / "launcher.exe"

    if not exe.exists():
        return {"ok": False, "error": f"Executable not found: {exe}"}

    args = [str(exe)]
    if project_path:
        path = str(cfg.work_dir / project_path) if not Path(project_path).is_absolute() else project_path
        args.append(path)

    try:
        process = subprocess.Popen(
            args,
            cwd=str(cfg.lumerical_bin) if cfg.lumerical_bin.exists() else None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    except OSError as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    job_id = f"fdtd-gui-{int(time.time())}-{process.pid}"
    _gui_jobs[job_id] = {
        "job_id": job_id,
        "pid": process.pid,
        "target": target,
        "args": args,
        "started_at": time.time(),
    }
    return {"ok": True, **_gui_jobs[job_id]}


@mcp.tool()
def fdtd_command_docs_tool(query: str = "", limit: int = 50) -> dict:
    docs_path = cfg.lumerical_api_python / "docs.json"
    if not docs_path.exists():
        return {"ok": False, "error": f"docs.json not found: {docs_path}"}

    docs = json.loads(docs_path.read_text(encoding="utf-8", errors="replace"))
    needle = query.lower() if query else None
    items = []

    for name, entry in docs.items():
        if isinstance(entry, dict):
            text = entry.get("text", "")
            link = entry.get("link", "")
        else:
            text = str(entry)
            link = ""

        if needle:
            haystack = f"{name}\n{text}".lower()
            if needle not in haystack:
                continue

        items.append({"name": name, "text": text, "link": link})
        if len(items) >= limit:
            break

    return {"ok": True, "count": len(items), "commands": items}


def main():
    logger.info(f"Starting Lumerical MCP server on {cfg.host}:{cfg.port} ({cfg.transport})")
    logger.info(f"Lumerical root: {cfg.lumerical_root}")
    logger.info(f"Work directory: {cfg.work_dir}")
    mcp.run(transport=cfg.transport, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()