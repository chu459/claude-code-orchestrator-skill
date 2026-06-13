#!/usr/bin/env python3
"""Claude Code orchestration helpers backed by CCSwitch profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def configure_stdio() -> None:
    """Keep JSON output readable on Windows consoles with non-ASCII text."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def force_utf8_env(env: dict[str, str]) -> dict[str, str]:
    """Make child Python/Node tools prefer UTF-8 without overwriting user choices."""
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    if os.name != "nt":
        env.setdefault("LANG", "C.UTF-8")
        env.setdefault("LC_ALL", "C.UTF-8")
    return env


def subprocess_text(value: Any) -> str:
    """Normalize subprocess output, including TimeoutExpired bytes payloads."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


configure_stdio()


ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
RUNS_DIR = ROOT / "runs"
TEAMS_DIR = RUNS_DIR / "teams"
REPORTS_DIR = ROOT / "reports"
DASHBOARD_DIR = ROOT / "dashboard"
POLICY_PATH = CONFIG_DIR / "model_policy.json"
AGENTS_PATH = CONFIG_DIR / "agents.json"
CALIBRATION_PATH = CONFIG_DIR / "model_calibration.json"
COST_GUARD_PATH = CONFIG_DIR / "cost_guard.json"
CLAUDE_MD_MARKER_BEGIN = "<!-- claude-code-orchestrator:begin -->"
CLAUDE_MD_MARKER_END = "<!-- claude-code-orchestrator:end -->"
SECRET_KEY_RE = re.compile(r"(key|token|secret|authorization|auth)", re.IGNORECASE)
SECRET_VALUE_RE = re.compile(
    r"("
    r"sk-[A-Za-z0-9_\-]{8,}|"
    r"ghp_[A-Za-z0-9_]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|"
    r"npm_[A-Za-z0-9]{20,}|"
    r"AKIA[0-9A-Z]{16}|"
    r"AIza[0-9A-Za-z_\-]{35}|"
    r"Bearer\s+[A-Za-z0-9._~+/=\-]{20,}|"
    r"[A-Za-z0-9]{20,}\.[A-Za-z0-9_\-]{8,}|"
    r"-----BEGIN (?:RSA|OPENSSH|PRIVATE) KEY-----"
    r")",
    re.IGNORECASE,
)
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
TEAM_ID_RE = re.compile(r"^team-\d{8}T\d{6}Z-[0-9a-f]{8}$")
PASSTHROUGH_ENV_KEYS = {
    "PATH",
    "Path",
    "PATHEXT",
    "SYSTEMROOT",
    "SystemRoot",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "TMPDIR",
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "PROGRAMDATA",
    "CLAUDE_CODE_BIN",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "SHELL",
    "TERM",
}
MODEL_ENV_KEYS = (
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
)
ROLE_ORDER = [
    "requirements",
    "architecture",
    "development",
    "testing",
    "review",
    "performance",
    "compatibility",
    "documentation",
    "automation",
    "security",
    "implementation",
    "ops",
    "multimodal",
]
SCORE_KEYS = ("code", "long_context", "reasoning", "speed", "stability", "cost", "tool_use", "multimodal")
ROLE_SCORE_WEIGHTS: dict[str, dict[str, float]] = {
    "requirements": {"reasoning": 0.20, "long_context": 0.20, "tool_use": 0.15, "stability": 0.15, "speed": 0.15, "code": 0.10, "cost": 0.05},
    "architecture": {"reasoning": 0.30, "code": 0.25, "long_context": 0.20, "tool_use": 0.15, "stability": 0.10},
    "development": {"code": 0.35, "reasoning": 0.25, "tool_use": 0.20, "long_context": 0.10, "stability": 0.10},
    "security": {"reasoning": 0.35, "code": 0.20, "long_context": 0.20, "stability": 0.15, "tool_use": 0.10},
    "testing": {"code": 0.25, "tool_use": 0.25, "stability": 0.20, "speed": 0.15, "reasoning": 0.10, "cost": 0.05},
    "implementation": {"code": 0.35, "reasoning": 0.25, "tool_use": 0.20, "long_context": 0.10, "stability": 0.10},
    "review": {"reasoning": 0.30, "code": 0.25, "long_context": 0.20, "stability": 0.15, "tool_use": 0.10},
    "performance": {"speed": 0.25, "code": 0.25, "stability": 0.20, "tool_use": 0.15, "reasoning": 0.15},
    "compatibility": {"stability": 0.25, "tool_use": 0.20, "code": 0.20, "long_context": 0.15, "reasoning": 0.15, "cost": 0.05},
    "documentation": {"long_context": 0.25, "reasoning": 0.20, "speed": 0.15, "tool_use": 0.15, "stability": 0.10, "code": 0.10, "cost": 0.05},
    "automation": {"tool_use": 0.25, "code": 0.25, "stability": 0.20, "reasoning": 0.15, "speed": 0.10, "cost": 0.05},
    "ops": {"stability": 0.25, "tool_use": 0.20, "speed": 0.20, "reasoning": 0.15, "long_context": 0.10, "cost": 0.10},
    "multimodal": {"multimodal": 0.40, "tool_use": 0.20, "reasoning": 0.15, "code": 0.10, "long_context": 0.10, "stability": 0.05},
}


class OrchestratorError(RuntimeError):
    """Raised for expected orchestration failures with actionable messages."""


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    app_type: str
    settings: dict[str, Any]
    category: str | None
    provider_type: str | None
    is_current: bool
    endpoints: list[str]

    @property
    def model_entries(self) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        seen: set[str] = set()
        for key in MODEL_ENV_KEYS:
            model = self.env.get(key)
            if model and model not in seen:
                entries.append({"name": model, "source": key})
                seen.add(model)
        model = self.settings.get("model")
        if model and str(model) not in seen:
            entries.append({"name": str(model), "source": "settings.model"})
        return entries

    @property
    def models(self) -> list[str]:
        return [item["name"] for item in self.model_entries]

    @property
    def env(self) -> dict[str, str]:
        raw = self.settings.get("env") or {}
        return {str(k): str(v) for k, v in raw.items() if v is not None}

    @property
    def model(self) -> str | None:
        models = self.models
        return models[0] if models else None


def user_home() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or (user_home() / ".codex"))


def resolve_ccswitch_home(explicit: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    for value in (explicit, os.environ.get("CCSWITCH_HOME")):
        if value:
            candidates.append(Path(value).expanduser())
    home = user_home()
    candidates.extend(
        [
            home / ".cc-switch",
            Path.home() / ".cc-switch",
            Path(os.environ.get("APPDATA", "")) / "cc-switch",
            Path(os.environ.get("LOCALAPPDATA", "")) / "cc-switch",
        ]
    )
    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in candidates:
        if not str(candidate) or str(candidate) in seen:
            continue
        seen.add(str(candidate))
        unique.append(candidate)
        if (candidate / "cc-switch.db").exists():
            return candidate
    return unique[0] if unique else home / ".cc-switch"


def cc_db_path(ccswitch_home: str | Path | None = None) -> Path:
    return resolve_ccswitch_home(ccswitch_home) / "cc-switch.db"


def cc_settings_path(ccswitch_home: str | Path | None = None) -> Path:
    return resolve_ccswitch_home(ccswitch_home) / "settings.json"


def _claude_candidate_rank(path: str) -> tuple[int, str]:
    lower = path.lower()
    if lower.endswith(r"\node_modules\@anthropic-ai\claude-code\bin\claude.exe"):
        return (0, lower)
    suffix = Path(path).suffix.lower()
    ranks = {".exe": 1, ".cmd": 2, ".bat": 3, "": 4, ".ps1": 5}
    return (ranks.get(suffix, 6), lower)


def _existing_claude_candidates() -> list[str]:
    candidates: list[str] = []
    explicit = os.environ.get("CLAUDE_CODE_BIN")
    if explicit:
        resolved = shutil.which(explicit) if not Path(explicit).is_absolute() else explicit
        if resolved and (Path(resolved).exists() or shutil.which(resolved)):
            candidates.append(resolved)
    try:
        proc = subprocess.run(["where.exe", "claude"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        if proc.returncode == 0:
            candidates.extend(line.strip() for line in proc.stdout.splitlines() if line.strip())
    except Exception:
        found = shutil.which("claude")
        if found:
            candidates.append(found)
    home = user_home()
    program_data = Path(os.environ.get("PROGRAMDATA", "")) / "WorkBuddy"
    direct_candidates = [home / ".local" / "bin" / "claude.exe"]
    for path in direct_candidates:
        if path.exists():
            candidates.append(str(path))
    glob_roots = [
        (home, ".workbuddy/binaries/node/versions/*/node_modules/@anthropic-ai/claude-code/bin/claude.exe"),
        (program_data, "chromium-env/*/.workbuddy/binaries/node/versions/*/node_modules/@anthropic-ai/claude-code/bin/claude.exe"),
    ]
    for root, pattern in glob_roots:
        if not str(root) or not root.exists():
            continue
        try:
            candidates.extend(str(path) for path in root.glob(pattern) if path.exists())
        except Exception:
            continue
    seen: set[str] = set()
    existing: list[str] = []
    for candidate in candidates:
        resolved = shutil.which(candidate) if not Path(candidate).is_absolute() else candidate
        if not resolved or resolved in seen:
            continue
        if Path(resolved).exists() or shutil.which(resolved):
            seen.add(resolved)
            existing.append(resolved)
    if explicit and existing:
        return existing[:1] + sorted(existing[1:], key=_claude_candidate_rank)
    return sorted(existing, key=_claude_candidate_rank)


def claude_bin_path() -> str:
    candidates = _existing_claude_candidates()
    return candidates[0] if candidates else "claude"


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OrchestratorError(f"Missing config file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise OrchestratorError(f"Invalid JSON in {path}: {exc}") from exc


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***REDACTED***" if SECRET_KEY_RE.search(str(k)) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return SECRET_VALUE_RE.sub(lambda match: match.group(0)[:6] + "..." + match.group(0)[-4:], value)
    return value


def validate_env_key(key: str) -> str:
    if not ENV_KEY_RE.match(key):
        raise OrchestratorError(f"Unsafe environment variable name from CCSwitch profile: {key!r}")
    return key


def build_worker_env(provider_env: dict[str, str], model_override: str | None = None) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key in PASSTHROUGH_ENV_KEYS}
    for key, value in provider_env.items():
        env[validate_env_key(str(key))] = str(value)
    if model_override:
        env["ANTHROPIC_MODEL"] = str(model_override)
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    return force_utf8_env(env)


def safe_run_dir(run_id: str) -> Path:
    if not RUN_ID_RE.match(run_id):
        raise OrchestratorError(f"Invalid run id: {run_id}")
    run_dir = (RUNS_DIR / run_id).resolve()
    root = RUNS_DIR.resolve()
    try:
        run_dir.relative_to(root)
    except ValueError as exc:
        raise OrchestratorError(f"Run id resolves outside run directory: {run_id}") from exc
    return run_dir


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


def read_metadata(run_dir: Path) -> dict[str, Any]:
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.exists():
        raise OrchestratorError(f"Run metadata not found: {run_dir.name}")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def write_metadata(run_dir: Path, metadata: dict[str, Any]) -> None:
    (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def update_metadata(run_dir: Path, **updates: Any) -> dict[str, Any]:
    metadata = read_metadata(run_dir)
    metadata.update(updates)
    write_metadata(run_dir, metadata)
    return metadata


def pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            return proc.returncode == 0 and re.search(rf'"[^"]+","{pid}"[,"]', proc.stdout or "") is not None
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def terminate_process_tree(pid: int, force: bool = False, wait_seconds: int = 5) -> dict[str, Any]:
    """Terminate a process and its children where the platform supports it."""
    if pid <= 0:
        return {"pid": pid, "attempted": False, "alive": False, "method": "invalid-pid"}
    if not pid_alive(pid):
        return {"pid": pid, "attempted": False, "alive": False, "method": "already-exited"}
    method = "os.kill"
    if os.name == "nt":
        cmd = ["taskkill", "/PID", str(pid), "/T"]
        if force:
            cmd.append("/F")
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=max(wait_seconds, 1) + 5)
        time.sleep(min(max(wait_seconds, 1), 5))
        alive = pid_alive(pid)
        return {
            "pid": pid,
            "attempted": True,
            "alive": alive,
            "method": "taskkill",
            "exit_code": proc.returncode,
            "stdout": str(redact(proc.stdout or ""))[-1000:],
            "stderr": str(redact(proc.stderr or ""))[-1000:],
        }
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        try:
            os.killpg(os.getpgid(pid), sig)
            method = "os.killpg"
        except Exception:
            os.kill(pid, sig)
        deadline = time.time() + max(wait_seconds, 1)
        while time.time() < deadline and pid_alive(pid):
            time.sleep(0.1)
        return {"pid": pid, "attempted": True, "alive": pid_alive(pid), "method": method, "signal": int(sig)}
    except OSError as exc:
        return {"pid": pid, "attempted": True, "alive": pid_alive(pid), "method": method, "error": str(exc)}


def read_file_delta(path: Path, offset: int = 0, max_bytes: int = 20000) -> dict[str, Any]:
    if offset < 0:
        raise OrchestratorError("Offset cannot be negative.")
    if max_bytes < 1:
        raise OrchestratorError("max_bytes must be positive.")
    if not path.exists():
        return {"path": str(path), "text": "", "offset": offset, "next_offset": offset, "size": 0, "truncated": False}
    size = path.stat().st_size
    if offset > size:
        offset = size
    with path.open("rb") as handle:
        handle.seek(offset)
        data = handle.read(max_bytes)
    next_offset = offset + len(data)
    text = data.decode("utf-8", errors="replace")
    return {
        "path": str(path),
        "text": str(redact(text)),
        "offset": offset,
        "next_offset": next_offset,
        "size": size,
        "truncated": next_offset < size,
    }


def tail_file(path: Path, chars: int = 4000) -> str:
    if chars <= 0 or not path.exists():
        return ""
    size = path.stat().st_size
    with path.open("rb") as handle:
        handle.seek(max(0, size - max(chars * 4, 4096)))
        data = handle.read()
    return str(redact(data.decode("utf-8", errors="replace")[-chars:]))


def last_nonempty_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        if line.strip():
            return line[-1000:]
    return ""


def extract_event_phase(payload: Any, source: str) -> str | None:
    if source == "stderr":
        return "stderr"
    if not isinstance(payload, dict):
        return None
    event_type = str(payload.get("type") or payload.get("event") or payload.get("subtype") or "").lower()
    if "tool" in event_type:
        return "tool"
    if event_type in {"system", "init", "started", "start"}:
        return "started"
    if event_type in {"assistant", "message", "content_block_delta", "content_block_start"}:
        return "responding"
    if event_type in {"result", "complete", "completed", "done"}:
        return "finished"
    content = payload.get("message", {}).get("content") if isinstance(payload.get("message"), dict) else payload.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and str(item.get("type", "")).lower() == "tool_use":
                return "tool"
    return None


def extract_tool_calls_from_payload(payload: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            value_type = str(value.get("type", "")).lower()
            if value_type == "tool_use" or "tool" in value_type and ("name" in value or "tool_name" in value):
                calls.append(
                    {
                        "id": value.get("id"),
                        "name": value.get("name") or value.get("tool_name"),
                        "type": value.get("type"),
                    }
                )
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    return calls


def append_event(run_dir: Path, event: dict[str, Any]) -> None:
    seq_path = run_dir / "event_seq.txt"
    try:
        seq = int(seq_path.read_text(encoding="utf-8").strip() or "0") + 1
    except (FileNotFoundError, ValueError):
        seq = 1
    event.setdefault("seq", seq)
    event.setdefault("ts", utc_now_iso())
    event.setdefault("run_id", run_dir.name)
    path = run_dir / "events.ndjson"
    with path.open("a", encoding="utf-8", errors="replace") as handle:
        handle.write(json.dumps(redact(event), ensure_ascii=False) + "\n")
    seq_path.write_text(str(seq), encoding="utf-8")


def parse_events_delta(path: Path, offset: int = 0, max_bytes: int = 20000) -> dict[str, Any]:
    delta = read_file_delta(path, offset=offset, max_bytes=max_bytes)
    events: list[dict[str, Any]] = []
    for line in delta["text"].splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"type": "unparsed", "text": line})
    return {**delta, "events": events}


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    phase = None
    tool_calls: list[dict[str, Any]] = []
    for event in events:
        payload = event.get("payload") if isinstance(event, dict) else None
        event_phase = extract_event_phase(payload, str(event.get("source", ""))) if isinstance(event, dict) else None
        if event_phase:
            phase = event_phase
        tool_calls.extend(extract_tool_calls_from_payload(payload))
    return {"latest_phase": phase, "tool_calls": tool_calls[-20:]}


def list_profiles(ccswitch_home: str | Path | None = None, include_secrets: bool = False) -> list[dict[str, Any]]:
    resolved_home = resolve_ccswitch_home(ccswitch_home)
    db_path = cc_db_path(resolved_home)
    if not db_path.exists():
        raise OrchestratorError(f"CCSwitch database not found: {db_path}")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            select id, app_type, name, settings_config, category, provider_type, is_current, sort_index
            from providers
            where app_type='claude'
            order by is_current desc, sort_index, lower(name)
            """
        ).fetchall()
        profiles: list[dict[str, Any]] = []
        for row in rows:
            endpoints = [
                r["url"]
                for r in con.execute(
                    "select url from provider_endpoints where provider_id=? and app_type='claude'",
                    (row["id"],),
                ).fetchall()
            ]
            settings = json.loads(row["settings_config"])
            provider = Provider(
                id=row["id"],
                name=row["name"],
                app_type=row["app_type"],
                settings=settings,
                category=row["category"],
                provider_type=row["provider_type"],
                is_current=bool(row["is_current"]),
                endpoints=endpoints,
            )
            payload = {
                "id": provider.id,
                "name": provider.name,
                "current": provider.is_current,
                "category": provider.category,
                "provider_type": provider.provider_type,
                "model": provider.model,
                "models": provider.models,
                "model_entries": provider.model_entries,
                "base_url": provider.env.get("ANTHROPIC_BASE_URL"),
                "endpoints": provider.endpoints,
                "settings": provider.settings if include_secrets else redact(provider.settings),
            }
            profiles.append(payload)
        return profiles
    finally:
        con.close()


def get_provider(profile: str | None = None, ccswitch_home: str | Path | None = None) -> Provider:
    profiles = list_profiles(ccswitch_home=ccswitch_home, include_secrets=True)
    if not profiles:
        raise OrchestratorError("No Claude providers found in CCSwitch.")
    selected: dict[str, Any] | None = None
    if profile:
        wanted = profile.strip().lower()
        for item in profiles:
            if item["id"].lower() == wanted or item["name"].lower() == wanted:
                selected = item
                break
        if not selected:
            names = ", ".join(p["name"] for p in profiles)
            raise OrchestratorError(f"Unknown profile '{profile}'. Available profiles: {names}")
    else:
        selected = next((p for p in profiles if p["current"]), profiles[0])
    return Provider(
        id=selected["id"],
        name=selected["name"],
        app_type="claude",
        settings=selected["settings"],
        category=selected.get("category"),
        provider_type=selected.get("provider_type"),
        is_current=bool(selected.get("current")),
        endpoints=selected.get("endpoints") or [],
    )


def _score_from_model_name(model: str) -> tuple[dict[str, int], list[str]]:
    name = model.lower()
    scores = {key: 6 for key in SCORE_KEYS}
    notes = ["local heuristic scoring; verify with real workloads before treating as benchmark data"]
    qwen_match = re.search(r"qwen[-_]?(\d+(?:\.\d+)?)", name)
    glm_match = re.search(r"glm[-_]?(\d+(?:\.\d+)?)", name)
    qwen_version = float(qwen_match.group(1)) if qwen_match else None
    glm_version = float(glm_match.group(1)) if glm_match else None
    if qwen_version is not None and qwen_version >= 3.7:
        scores.update(code=9, long_context=9, reasoning=8, speed=8, stability=7, cost=7, tool_use=9, multimodal=9)
        notes.append("Qwen docs describe Qwen as language plus multimodal models with tool use and agent capabilities.")
    elif qwen_version is not None and qwen_version >= 3.6:
        scores.update(code=8, long_context=8, reasoning=7, speed=8, stability=7, cost=7, tool_use=8, multimodal=7)
        notes.append("Qwen-family heuristic based on Qwen3 tool/agent and coding documentation.")
    elif "qwen" in name:
        scores.update(code=8, long_context=8, reasoning=7, speed=8, stability=7, cost=7, tool_use=8, multimodal=6)
        notes.append("Qwen-family heuristic based on Qwen3 tool/agent and coding documentation.")
    elif glm_version is not None and glm_version >= 5:
        scores.update(code=9, long_context=8, reasoning=9, speed=6, stability=7, cost=6, tool_use=8, multimodal=5)
        notes.append("Z.ai describes GLM-5 as focused on agentic engineering and coding workflows.")
    elif "claude" in name and "opus" in name:
        scores.update(code=9, long_context=8, reasoning=9, speed=6, stability=8, cost=5, tool_use=9, multimodal=7)
        notes.append("Claude Opus-family heuristic; exact proxy model quality depends on provider routing.")
    elif "claude" in name and "sonnet" in name:
        scores.update(code=8, long_context=8, reasoning=8, speed=8, stability=8, cost=7, tool_use=9, multimodal=7)
        notes.append("Claude Sonnet-family heuristic; exact proxy model quality depends on provider routing.")
    return scores, notes


def _weighted_score(scores: dict[str, int], weights: dict[str, float]) -> float:
    total_weight = sum(weights.values()) or 1.0
    return round(sum(scores.get(key, 0) * weight for key, weight in weights.items()) / total_weight, 2)


def score_models(ccswitch_home: str | Path | None = None) -> dict[str, Any]:
    profiles = list_profiles(ccswitch_home=ccswitch_home, include_secrets=True)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for profile in profiles:
        provider = get_provider(profile["id"], ccswitch_home=ccswitch_home)
        for entry in provider.model_entries:
            model = entry["name"]
            key = (provider.id, model)
            if key in seen:
                continue
            seen.add(key)
            scores, notes = _score_from_model_name(model)
            role_scores = {role: _weighted_score(scores, weights) for role, weights in ROLE_SCORE_WEIGHTS.items()}
            overall = round(sum(scores.values()) / len(scores), 2)
            rows.append(
                {
                    "profile_id": provider.id,
                    "profile_name": provider.name,
                    "current_profile": provider.is_current,
                    "model": model,
                    "source": entry["source"],
                    "scores": scores,
                    "overall": overall,
                    "role_scores": role_scores,
                    "basis": notes,
                }
            )
    rows.sort(key=lambda item: (not item["current_profile"], -item["overall"], item["profile_name"], item["model"]))
    return {
        "ok": True,
        "ccswitch_home": str(resolve_ccswitch_home(ccswitch_home)),
        "source_quality": "local heuristic plus public documentation signals; not a paid benchmark run",
        "score_keys": list(SCORE_KEYS),
        "models": rows,
    }


def select_model_for_role(role: str = "implementation", task_type: str | None = None, ccswitch_home: str | Path | None = None) -> dict[str, Any]:
    target = role if role in ROLE_SCORE_WEIGHTS else "implementation"
    if task_type == "multimodal":
        target = "multimodal"
    elif role not in ROLE_SCORE_WEIGHTS:
        if task_type == "simple":
            target = "testing"
        elif task_type == "development":
            target = "development"
        elif task_type == "review":
            target = "review"
        elif task_type == "security_review":
            target = "security"
        elif task_type == "architecture":
            target = "architecture"
        elif task_type == "performance_review":
            target = "performance"
        elif task_type == "compatibility_review":
            target = "compatibility"
        elif task_type == "documentation":
            target = "documentation"
        elif task_type == "automation":
            target = "automation"
        elif task_type == "ops":
            target = "ops"
    scored = score_models(ccswitch_home=ccswitch_home)["models"]
    if not scored:
        provider = get_provider(ccswitch_home=ccswitch_home)
        return {
            "profile": provider.name,
            "model": provider.model,
            "score": None,
            "reason": "No explicit models found; using current CCSwitch Claude profile.",
        }
    best = max(
        scored,
        key=lambda item: (
            item["role_scores"].get(target, item["overall"]),
            item["current_profile"],
            item["overall"],
        ),
    )
    return {
        "profile": best["profile_name"],
        "model": best["model"],
        "score": best["role_scores"].get(target, best["overall"]),
        "reason": f"Selected highest local score for {target}.",
        "scores": best["scores"],
    }


def resolve_route(role: str = "implementation", task_type: str | None = None, profile: str | None = None) -> dict[str, Any]:
    policy = load_json(POLICY_PATH)
    routes = policy.get("task_routes", {})
    role_defaults = policy.get("role_defaults", {})
    aliases = policy.get("profile_aliases", {})
    effective_task_type = task_type or role_defaults.get(role, "normal")
    route = routes.get(effective_task_type) or routes.get("normal") or {}
    alias = route.get("profile_alias")
    resolved_profile = profile or aliases.get(alias, alias) or policy.get("default_profile")
    selected_model: dict[str, Any] | None = None
    selection_role = role
    if isinstance(resolved_profile, str) and resolved_profile.startswith("auto"):
        _, _, explicit_role = resolved_profile.partition(":")
        if explicit_role:
            selection_role = explicit_role
        selected_model = select_model_for_role(role=selection_role, task_type=effective_task_type)
        resolved_profile = selected_model["profile"]
    if not resolved_profile:
        raise OrchestratorError("No profile could be resolved from policy.")
    model_override = route.get("model_override")
    if selected_model and selected_model.get("model"):
        model_override = selected_model["model"]
    provider = get_provider(str(resolved_profile))
    if model_override and model_override not in provider.models:
        fallback = select_model_for_role(role=selection_role, task_type=effective_task_type)
        resolved_profile = fallback["profile"]
        model_override = fallback["model"]
        selected_model = fallback
    max_timeout = int(policy.get("safety", {}).get("max_timeout_seconds", 1800))
    timeout = min(int(route.get("timeout_seconds", 420)), max_timeout)
    return {
        "role": role,
        "task_type": effective_task_type,
        "profile": resolved_profile,
        "model_override": model_override,
        "permission_mode": route.get("permission_mode", "plan"),
        "timeout_seconds": timeout,
        "reason": selected_model.get("reason") if selected_model else route.get("reason", ""),
        "route": route,
        "auto_selection": selected_model,
        "selection_role": selection_role,
    }


def healthcheck() -> dict[str, Any]:
    ccswitch_home = resolve_ccswitch_home()
    db_path = cc_db_path(ccswitch_home)
    settings_path = cc_settings_path(ccswitch_home)
    result: dict[str, Any] = {
        "ok": True,
        "claude_bin": claude_bin_path(),
        "claude_candidates": _existing_claude_candidates(),
        "ccswitch_home": str(ccswitch_home),
        "ccswitch_db_exists": db_path.exists(),
        "ccswitch_settings_exists": settings_path.exists(),
        "policy_exists": POLICY_PATH.exists(),
        "agents_exists": AGENTS_PATH.exists(),
    }
    try:
        profiles = list_profiles()
        result["profile_count"] = len(profiles)
        result["current_profile"] = next((p["name"] for p in profiles if p["current"]), None)
    except Exception as exc:
        result["ok"] = False
        result["profiles_error"] = str(exc)
    try:
        proc = subprocess.run(
            [claude_bin_path(), "--version"],
            env=build_worker_env({}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        result["claude_version_exit_code"] = proc.returncode
        result["claude_version"] = (proc.stdout or proc.stderr).strip()
        if proc.returncode != 0:
            result["ok"] = False
    except Exception as exc:
        result["ok"] = False
        result["claude_error"] = str(exc)
    return result


def build_prompt(role: str, task: str, context: str | None = None) -> str:
    agents = load_json(AGENTS_PATH)
    agent = agents.get(role) or agents.get("implementation") or {}
    pieces = [
        "Codex is the controller, reviewer, and final decision maker. You are a Claude Code worker.",
        "",
        agent.get("prompt", f"You are the {role} Agent."),
        "",
        "Follow these operating rules:",
        "- Keep output concise and structured.",
        "- Do not reveal API keys, tokens, secrets, or hidden configuration values.",
        "- Do not revert unrelated work.",
        "- If you edit files, list every changed file and why.",
        "",
        "Task:",
        task.strip(),
    ]
    if context and context.strip():
        pieces.extend(["", "Additional context:", context.strip()])
    return "\n".join(pieces)


def capture_git_snapshot(run_dir: Path, cwd: Path, label: str) -> dict[str, Any]:
    """Capture git diff/status for audit and conservative rollback."""
    result = {"ok": False, "label": label, "is_git_repo": False}
    if not (cwd / ".git").exists():
        return result
    try:
        diff_proc = subprocess.run(
            ["git", "diff", "--binary", "--", "."],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        status_proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        diff_path = run_dir / f"git_{label}.diff"
        status_path = run_dir / f"git_{label}_status.txt"
        diff_path.write_text(str(redact(diff_proc.stdout or diff_proc.stderr or "")), encoding="utf-8")
        status_path.write_text(str(redact(status_proc.stdout or status_proc.stderr or "")), encoding="utf-8")
        return {
            "ok": diff_proc.returncode == 0 and status_proc.returncode == 0,
            "label": label,
            "is_git_repo": True,
            "diff_path": str(diff_path),
            "status_path": str(status_path),
            "diff_bytes": diff_path.stat().st_size,
            "status_bytes": status_path.stat().st_size,
        }
    except Exception as exc:
        return {"ok": False, "label": label, "is_git_repo": True, "error": str(exc)}


def run_agent(
    task: str,
    role: str = "implementation",
    task_type: str | None = None,
    profile: str | None = None,
    allow_write: bool = False,
    timeout_seconds: int | None = None,
    cwd: Path | None = None,
    context: str | None = None,
    output_format: str = "json",
) -> dict[str, Any]:
    if not task.strip():
        raise OrchestratorError("Task cannot be empty.")
    route = resolve_route(role=role, task_type=task_type, profile=profile)
    provider = get_provider(route["profile"])
    policy = load_json(POLICY_PATH)
    default_write = bool(policy.get("safety", {}).get("default_write_enabled", False))
    write_enabled = allow_write or default_write
    permission_mode = route["permission_mode"] if not write_enabled else "acceptEdits"
    timeout = timeout_seconds or int(route["timeout_seconds"])
    timeout = min(timeout, int(policy.get("safety", {}).get("max_timeout_seconds", 1800)))
    timeout = enforce_cost_guard(route.get("model_override") or provider.model, timeout)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    prompt = build_prompt(role, task, context)
    safe_prompt = str(redact(prompt))
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    effective_cwd = cwd or Path.cwd()
    env = build_worker_env(provider.env, route.get("model_override"))
    cmd = [
        claude_bin_path(),
        "-p",
        "--output-format",
        output_format,
        "--permission-mode",
        permission_mode,
        "--no-session-persistence",
        safe_prompt,
    ]
    started = time.time()
    metadata: dict[str, Any] = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "cwd": str(effective_cwd),
        "role": role,
        "task_type": route["task_type"],
        "profile": {
            "id": provider.id,
            "name": provider.name,
            "model": route.get("model_override") or provider.model,
            "provider_default_model": provider.model,
            "base_url": provider.env.get("ANTHROPIC_BASE_URL"),
            "endpoints": provider.endpoints,
        },
        "permission_mode": permission_mode,
        "allow_write": write_enabled,
        "timeout_seconds": timeout,
        "prompt_sha256": prompt_hash,
        "route_reason": route.get("reason", ""),
        "command": redact(cmd),
    }
    metadata["git_before"] = capture_git_snapshot(run_dir, effective_cwd, "before")
    (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "prompt.txt").write_text(safe_prompt, encoding="utf-8")
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(effective_cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        timed_out = False
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        exit_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = subprocess_text(exc.stdout)
        stderr = subprocess_text(exc.stderr)
        exit_code = 124
    duration_ms = int((time.time() - started) * 1000)
    safe_stdout = redact(stdout)
    safe_stderr = redact(stderr)
    (run_dir / "stdout.txt").write_text(str(safe_stdout), encoding="utf-8")
    (run_dir / "stderr.txt").write_text(str(safe_stderr), encoding="utf-8")
    metadata.update(
        {
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "stdout_path": str(run_dir / "stdout.txt"),
            "stderr_path": str(run_dir / "stderr.txt"),
            "git_after": capture_git_snapshot(run_dir, effective_cwd, "after"),
        }
    )
    (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path = RUNS_DIR / "latest.txt"
    latest_path.write_text(run_id, encoding="utf-8")
    return {
        **metadata,
        "stdout_tail": str(safe_stdout)[-4000:],
        "stderr_tail": str(safe_stderr)[-2000:],
    }


def run_streaming_agent(
    task: str,
    role: str = "implementation",
    task_type: str | None = None,
    profile: str | None = None,
    allow_write: bool = False,
    timeout_seconds: int | None = None,
    cwd: Path | None = None,
    context: str | None = None,
    output_format: str = "stream-json",
    include_partial_messages: bool = True,
) -> dict[str, Any]:
    """Start Claude Code in the background and stream events to events.ndjson."""
    if not task.strip():
        raise OrchestratorError("Task cannot be empty.")
    route = resolve_route(role=role, task_type=task_type, profile=profile)
    provider = get_provider(route["profile"])
    policy = load_json(POLICY_PATH)
    default_write = bool(policy.get("safety", {}).get("default_write_enabled", False))
    write_enabled = allow_write or default_write
    permission_mode = route["permission_mode"] if not write_enabled else "acceptEdits"
    timeout = timeout_seconds or int(route["timeout_seconds"])
    timeout = min(timeout, int(policy.get("safety", {}).get("max_timeout_seconds", 1800)))
    timeout = enforce_cost_guard(route.get("model_override") or provider.model, timeout)
    if output_format != "stream-json":
        raise OrchestratorError("run_streaming_agent requires output_format='stream-json'.")

    run_id = new_run_id()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    effective_cwd = cwd or Path.cwd()
    prompt = build_prompt(role, task, context)
    safe_prompt = str(redact(prompt))
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    prompt_path = run_dir / "prompt.txt"
    prompt_path.write_text(safe_prompt, encoding="utf-8")
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    events_path = run_dir / "events.ndjson"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    events_path.write_text("", encoding="utf-8")

    metadata: dict[str, Any] = {
        "run_id": run_id,
        "mode": "streaming",
        "status": "starting",
        "started_at": utc_now_iso(),
        "cwd": str(effective_cwd),
        "role": role,
        "task_type": route["task_type"],
        "profile": {
            "id": provider.id,
            "name": provider.name,
            "model": route.get("model_override") or provider.model,
            "provider_default_model": provider.model,
            "base_url": provider.env.get("ANTHROPIC_BASE_URL"),
            "endpoints": provider.endpoints,
        },
        "permission_mode": permission_mode,
        "allow_write": write_enabled,
        "timeout_seconds": timeout,
        "output_format": output_format,
        "include_partial_messages": include_partial_messages,
        "prompt_sha256": prompt_hash,
        "route_reason": route.get("reason", ""),
        "prompt_path": str(prompt_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "events_path": str(events_path),
        "worker_pid": None,
        "child_pid": None,
    }
    metadata["git_before"] = capture_git_snapshot(run_dir, effective_cwd, "before")
    write_metadata(run_dir, metadata)
    append_event(run_dir, {"type": "run_started", "status": "starting", "role": role, "task_type": route["task_type"]})

    env = build_worker_env(provider.env, route.get("model_override"))
    worker_cmd = [sys.executable, "-B", str(Path(__file__).resolve()), "_stream-worker", "--run-id", run_id]
    creationflags = 0
    popen_kwargs: dict[str, Any] = {}
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        popen_kwargs["start_new_session"] = True
    worker = subprocess.Popen(
        worker_cmd,
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        **popen_kwargs,
    )
    metadata.update({"worker_pid": worker.pid, "worker_command": redact(worker_cmd)})
    write_metadata(run_dir, metadata)
    append_event(run_dir, {"type": "stream_worker_started", "worker_pid": worker.pid})
    (RUNS_DIR / "latest.txt").write_text(run_id, encoding="utf-8")
    return {
        **metadata,
        "status": "starting",
        "worker_pid": worker.pid,
        "poll": {
            "tool": "cc_poll_run",
            "run_id": run_id,
            "event_offset": 0,
            "stdout_offset": 0,
            "stderr_offset": 0,
        },
    }


def stream_worker(run_id: str) -> dict[str, Any]:
    """Internal worker process. It owns Claude Code pipes for a streaming run."""
    run_dir = safe_run_dir(run_id)
    metadata = update_metadata(run_dir, worker_pid=os.getpid())
    prompt = (run_dir / "prompt.txt").read_text(encoding="utf-8", errors="replace")
    permission_mode = str(metadata.get("permission_mode", "plan"))
    output_format = str(metadata.get("output_format", "stream-json"))
    include_partial_messages = bool(metadata.get("include_partial_messages", True))
    timeout = int(metadata.get("timeout_seconds") or 1800)
    cwd = Path(str(metadata.get("cwd") or Path.cwd()))
    cmd = [
        claude_bin_path(),
        "-p",
        "--output-format",
        output_format,
    ]
    if output_format == "stream-json":
        cmd.append("--verbose")
    if include_partial_messages:
        cmd.append("--include-partial-messages")
    cmd.extend(
        [
            "--permission-mode",
            permission_mode,
            "--no-session-persistence",
            prompt,
        ]
    )
    append_event(run_dir, {"type": "stream_worker_ready", "worker_pid": os.getpid()})
    creationflags = 0
    popen_kwargs: dict[str, Any] = {}
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True
    started = time.time()
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=force_utf8_env(dict(os.environ)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
        **popen_kwargs,
    )
    update_metadata(run_dir, status="running", child_pid=proc.pid, command=redact(cmd))
    (run_dir / "pid.txt").write_text(str(proc.pid), encoding="utf-8")
    append_event(run_dir, {"type": "process_started", "pid": proc.pid, "status": "running"})
    event_lock = threading.Lock()

    def safe_append(event: dict[str, Any]) -> None:
        with event_lock:
            append_event(run_dir, event)

    def pump(stream: Any, out_path: Path, source: str) -> None:
        try:
            with out_path.open("a", encoding="utf-8", errors="replace") as out:
                for line in iter(stream.readline, ""):
                    safe_line = str(redact(line))
                    out.write(safe_line)
                    out.flush()
                    if source == "stdout":
                        try:
                            payload: Any = redact(json.loads(line))
                            event_type = "claude_stream"
                        except json.JSONDecodeError:
                            payload = {"text": safe_line.rstrip("\r\n")}
                            event_type = "stdout"
                    else:
                        payload = {"text": safe_line.rstrip("\r\n")}
                        event_type = "stderr"
                    phase = extract_event_phase(payload, source)
                    event = {"type": event_type, "source": source, "payload": payload}
                    if phase:
                        event["phase"] = phase
                    safe_append(event)
        except Exception as exc:
            safe_append({"type": "stream_pump_error", "source": source, "error": str(exc)})

    threads = [
        threading.Thread(target=pump, args=(proc.stdout, run_dir / "stdout.txt", "stdout"), daemon=True),
        threading.Thread(target=pump, args=(proc.stderr, run_dir / "stderr.txt", "stderr"), daemon=True),
    ]
    for thread in threads:
        thread.start()

    timed_out = False
    stopped = False
    exit_code: int | None = None
    try:
        while True:
            exit_code = proc.poll()
            if exit_code is not None:
                break
            if (run_dir / "stop-requested.json").exists():
                stopped = True
                terminate_process_tree(proc.pid, force=False, wait_seconds=5)
            if time.time() - started > timeout:
                timed_out = True
                safe_append({"type": "timeout", "timeout_seconds": timeout})
                terminate_process_tree(proc.pid, force=False, wait_seconds=5)
                if pid_alive(proc.pid):
                    terminate_process_tree(proc.pid, force=True, wait_seconds=2)
            time.sleep(0.2)
        try:
            exit_code = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            terminate_process_tree(proc.pid, force=True, wait_seconds=2)
            exit_code = proc.poll()
    finally:
        for thread in threads:
            thread.join(timeout=2)

    duration_ms = int((time.time() - started) * 1000)
    latest_metadata = read_metadata(run_dir)
    stopped = stopped or bool(latest_metadata.get("stop_requested_at"))
    if timed_out:
        status = "timed_out"
        final_exit = 124 if exit_code is None else exit_code
    elif stopped:
        status = "stopped"
        final_exit = -15 if exit_code is None else exit_code
    else:
        final_exit = 0 if exit_code is None else exit_code
        status = "succeeded" if final_exit == 0 else "failed"
    final_metadata = update_metadata(
        run_dir,
        status=status,
        finished_at=utc_now_iso(),
        duration_ms=duration_ms,
        exit_code=final_exit,
        timed_out=timed_out,
        stdout_path=str(run_dir / "stdout.txt"),
        stderr_path=str(run_dir / "stderr.txt"),
        events_path=str(run_dir / "events.ndjson"),
        git_after=capture_git_snapshot(run_dir, cwd, "after"),
    )
    append_event(run_dir, {"type": "process_exited", "status": status, "exit_code": final_exit, "duration_ms": duration_ms})
    return final_metadata


def single_run_status(run_id: str, include_output_tail: bool = True, tail_chars: int = 4000) -> dict[str, Any]:
    run_dir = safe_run_dir(run_id)
    metadata = read_metadata(run_dir)
    status = str(metadata.get("status") or "unknown")
    child_pid = metadata.get("child_pid")
    worker_pid = metadata.get("worker_pid")
    child_alive = pid_alive(int(child_pid)) if child_pid else False
    worker_alive = pid_alive(int(worker_pid)) if worker_pid else False
    active = status in {"starting", "running", "stop_requested"} and (child_alive or worker_alive)
    if status in {"starting", "running", "stop_requested"} and not active:
        if metadata.get("finished_at") or metadata.get("exit_code") is not None:
            exit_code = metadata.get("exit_code")
            if status == "stop_requested":
                status = "stopped"
            elif metadata.get("timed_out"):
                status = "timed_out"
            else:
                status = "succeeded" if exit_code == 0 else "failed"
        else:
            status = "lost"
    started_at = metadata.get("started_at")
    finished_at = metadata.get("finished_at")
    elapsed_ms = metadata.get("duration_ms")
    if elapsed_ms is None and started_at:
        try:
            started_dt = datetime.fromisoformat(str(started_at))
            end_dt = datetime.fromisoformat(str(finished_at)) if finished_at else datetime.now(timezone.utc)
            elapsed_ms = int((end_dt - started_dt).total_seconds() * 1000)
        except Exception:
            elapsed_ms = None
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    events_path = run_dir / "events.ndjson"
    event_tail = tail_file(events_path, chars=20000)
    events: list[dict[str, Any]] = []
    for line in event_tail.splitlines()[-200:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    event_summary = summarize_events(events)
    stdout_tail = tail_file(stdout_path, chars=tail_chars)
    stderr_tail = tail_file(stderr_path, chars=min(tail_chars, 2000))
    result = {
        "ok": True,
        "run_id": run_id,
        "status": status,
        "active": active,
        "worker_pid": worker_pid,
        "child_pid": child_pid,
        "worker_alive": worker_alive,
        "child_alive": child_alive,
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_ms": elapsed_ms,
        "exit_code": metadata.get("exit_code"),
        "timed_out": bool(metadata.get("timed_out", False)),
        "role": metadata.get("role"),
        "task_type": metadata.get("task_type"),
        "profile": metadata.get("profile"),
        "latest_phase": event_summary.get("latest_phase"),
        "tool_calls": event_summary.get("tool_calls", []),
        "stdout_bytes": stdout_path.stat().st_size if stdout_path.exists() else 0,
        "stderr_bytes": stderr_path.stat().st_size if stderr_path.exists() else 0,
        "events_bytes": events_path.stat().st_size if events_path.exists() else 0,
        "last_stdout_line": last_nonempty_line(stdout_tail),
        "last_stderr_line": last_nonempty_line(stderr_tail),
        "paths": {
            "run_dir": str(run_dir),
            "metadata": str(run_dir / "metadata.json"),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "events": str(events_path),
        },
    }
    if include_output_tail:
        result["stdout_tail"] = stdout_tail
        result["stderr_tail"] = stderr_tail
    return result


def run_status(
    run_id: str | None = None,
    include_output_tail: bool = False,
    tail_chars: int = 4000,
    include_finished: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    if run_id:
        return single_run_status(run_id, include_output_tail=include_output_tail, tail_chars=tail_chars)
    runs: list[dict[str, Any]] = []
    candidates = [path for path in RUNS_DIR.iterdir() if path.is_dir() and RUN_ID_RE.match(path.name)]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            item = single_run_status(path.name, include_output_tail=include_output_tail, tail_chars=tail_chars)
        except Exception:
            continue
        if include_finished or item.get("active"):
            runs.append(item)
        if len(runs) >= limit:
            break
    return {
        "ok": True,
        "active_count": sum(1 for item in runs if item.get("active")),
        "count": len(runs),
        "runs": runs,
    }


def poll_run(
    run_id: str,
    stdout_offset: int = 0,
    stderr_offset: int = 0,
    event_offset: int = 0,
    max_bytes: int = 20000,
    include_output_tail: bool = True,
    tail_chars: int = 4000,
) -> dict[str, Any]:
    run_dir = safe_run_dir(run_id)
    status = single_run_status(run_id, include_output_tail=include_output_tail, tail_chars=tail_chars)
    stdout_delta = read_file_delta(run_dir / "stdout.txt", offset=stdout_offset, max_bytes=max_bytes)
    stderr_delta = read_file_delta(run_dir / "stderr.txt", offset=stderr_offset, max_bytes=max_bytes)
    events_delta = parse_events_delta(run_dir / "events.ndjson", offset=event_offset, max_bytes=max_bytes)
    event_summary = summarize_events(events_delta["events"])
    return {
        "ok": True,
        "run_id": run_id,
        "status": status,
        "stdout": stdout_delta,
        "stderr": stderr_delta,
        "events": {
            "path": events_delta["path"],
            "offset": events_delta["offset"],
            "next_offset": events_delta["next_offset"],
            "size": events_delta["size"],
            "truncated": events_delta["truncated"],
            "items": events_delta["events"],
        },
        "latest_phase": event_summary.get("latest_phase") or status.get("latest_phase"),
        "tool_calls": event_summary.get("tool_calls") or status.get("tool_calls", []),
    }


def stop_run(run_id: str, force: bool = False, timeout_seconds: int = 5) -> dict[str, Any]:
    run_dir = safe_run_dir(run_id)
    status = single_run_status(run_id, include_output_tail=False)
    if not status.get("active"):
        final_status = status.get("status")
        return {
            "ok": True,
            "run_id": run_id,
            "previous_status": final_status,
            "status": "already_stopped" if final_status == "stopped" else "already_finished",
            "active": False,
            "exit_code": status.get("exit_code"),
        }
    requested_at = utc_now_iso()
    (run_dir / "stop-requested.json").write_text(json.dumps({"requested_at": requested_at, "force": force}, ensure_ascii=False), encoding="utf-8")
    update_metadata(run_dir, status="stop_requested", stop_requested_at=requested_at)
    append_event(run_dir, {"type": "stop_requested", "force": force})
    results: list[dict[str, Any]] = []
    child_pid = status.get("child_pid")
    worker_pid = status.get("worker_pid")
    if child_pid:
        results.append(terminate_process_tree(int(child_pid), force=force, wait_seconds=timeout_seconds))
    refreshed = single_run_status(run_id, include_output_tail=False)
    if refreshed.get("active") and worker_pid:
        results.append(terminate_process_tree(int(worker_pid), force=True if force else False, wait_seconds=timeout_seconds))
    final = single_run_status(run_id, include_output_tail=False)
    stopped = not final.get("active")
    stopped_at = utc_now_iso()
    if stopped:
        update_metadata(run_dir, status="stopped", stopped_at=stopped_at, finished_at=stopped_at, exit_code=final.get("exit_code") if final.get("exit_code") is not None else -15)
        append_event(run_dir, {"type": "stopped", "status": "stopped"})
        final = single_run_status(run_id, include_output_tail=False)
    return {
        "ok": True,
        "run_id": run_id,
        "previous_status": status.get("status"),
        "status": final.get("status"),
        "active": final.get("active"),
        "force": force,
        "stopped": stopped,
        "stop_results": results,
    }


def read_team_manifest(team_id: str) -> dict[str, Any]:
    if not TEAM_ID_RE.match(team_id):
        raise OrchestratorError(f"Invalid team id: {team_id}")
    path = TEAMS_DIR / f"{team_id}.json"
    if not path.exists():
        raise OrchestratorError(f"Team manifest not found: {team_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_team_manifest(team_id: str, data: dict[str, Any]) -> Path:
    TEAMS_DIR.mkdir(parents=True, exist_ok=True)
    path = TEAMS_DIR / f"{team_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def send_instruction(
    run_id: str,
    instruction: str,
    force: bool = False,
    role: str | None = None,
    task_type: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """Append instruction by stopping the run and restarting with recovered context."""
    if not instruction.strip():
        raise OrchestratorError("Instruction cannot be empty.")
    previous = poll_run(run_id, max_bytes=50000, include_output_tail=True)
    status = previous["status"]
    if status.get("active"):
        stop = stop_run(run_id, force=force, timeout_seconds=5)
    else:
        stop = {"ok": True, "status": "already_finished"}
    metadata = read_metadata(safe_run_dir(run_id))
    context = "\n".join(
        [
            f"Previous run id: {run_id}",
            f"Previous status: {status.get('status')}",
            "",
            "Previous stdout tail:",
            str(status.get("stdout_tail", ""))[-6000:],
            "",
            "Previous stderr tail:",
            str(status.get("stderr_tail", ""))[-2000:],
            "",
            "New instruction:",
            instruction.strip(),
        ]
    )
    task = "Continue the previous Claude Code worker run using the new instruction. Preserve useful context, avoid repeating completed work, and report what changed."
    new_run = run_streaming_agent(
        task=task,
        role=role or str(metadata.get("role") or "implementation"),
        task_type=task_type or metadata.get("task_type"),
        profile=(metadata.get("profile") or {}).get("name"),
        allow_write=bool(metadata.get("allow_write", False)),
        timeout_seconds=timeout_seconds or metadata.get("timeout_seconds"),
        cwd=Path(str(metadata.get("cwd") or Path.cwd())),
        context=context,
    )
    return {"ok": True, "old_run_id": run_id, "stop": stop, "new_run": new_run}


def spawn_role_team(
    task: str,
    roles: list[str] | None = None,
    cwd: Path | None = None,
    context: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    if not task.strip():
        raise OrchestratorError("Task cannot be empty.")
    selected_roles = roles or ["requirements", "architecture", "security", "testing"]
    if not selected_roles:
        raise OrchestratorError("At least one role is required.")
    team_id = "team-" + new_run_id()
    runs: list[dict[str, Any]] = []
    for role in selected_roles:
        run = run_streaming_agent(
            task=task,
            role=role,
            cwd=cwd,
            context="\n".join(part for part in [f"Team id: {team_id}", context or ""] if part),
            timeout_seconds=timeout_seconds,
        )
        runs.append({"role": role, "run_id": run["run_id"], "status": run["status"], "profile": run.get("profile")})
    manifest = {
        "team_id": team_id,
        "created_at": utc_now_iso(),
        "task": task,
        "cwd": str(cwd or Path.cwd()),
        "roles": selected_roles,
        "runs": runs,
    }
    path = write_team_manifest(team_id, manifest)
    return {"ok": True, "team_id": team_id, "manifest_path": str(path), "runs": runs}


def resolve_team_run_ids(team_id: str | None = None, run_ids: list[str] | None = None) -> list[str]:
    ids = list(run_ids or [])
    if team_id:
        manifest = read_team_manifest(team_id)
        ids.extend(str(item["run_id"]) for item in manifest.get("runs", []) if item.get("run_id"))
    if not ids:
        raise OrchestratorError("Provide team_id or run_ids.")
    seen: set[str] = set()
    unique: list[str] = []
    for run_id in ids:
        safe_run_dir(run_id)
        if run_id not in seen:
            seen.add(run_id)
            unique.append(run_id)
    return unique


def extract_signal_lines(text: str, limit: int = 60) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip(" -*\t")
        if len(line) < 8 or len(line) > 220:
            continue
        if any(token in line.lower() for token in ("error", "risk", "bug", "todo", "conflict", "agree", "recommend", "建议", "风险", "冲突", "一致", "结论")):
            lines.append(line)
        elif raw.lstrip().startswith(("-", "*", "1.", "2.", "3.")):
            lines.append(line)
        if len(lines) >= limit:
            break
    return lines


def collect_team_results(team_id: str | None = None, run_ids: list[str] | None = None, tail_chars: int = 8000) -> dict[str, Any]:
    ids = resolve_team_run_ids(team_id, run_ids)
    items: list[dict[str, Any]] = []
    line_counts: dict[str, int] = {}
    conflict_lines: list[str] = []
    for run_id in ids:
        status = single_run_status(run_id, include_output_tail=True, tail_chars=tail_chars)
        text = str(status.get("stdout_tail", ""))
        signals = extract_signal_lines(text)
        for line in signals:
            key = re.sub(r"\s+", " ", line.lower())
            line_counts[key] = line_counts.get(key, 0) + 1
            if any(token in key for token in ("conflict", "risk", "blocked", "error", "冲突", "风险", "错误", "阻塞")):
                conflict_lines.append(line)
        items.append({"run_id": run_id, "role": status.get("role"), "status": status.get("status"), "active": status.get("active"), "signals": signals[:20]})
    agreements = [line for line, count in line_counts.items() if count > 1][:20]
    report_lines = ["# Team Results", ""]
    if team_id:
        report_lines.append(f"Team: `{team_id}`")
        report_lines.append("")
    report_lines.append("## Runs")
    for item in items:
        report_lines.append(f"- `{item['run_id']}` role `{item.get('role')}` status `{item.get('status')}` active `{item.get('active')}`")
    report_lines.extend(["", "## Agreements"])
    report_lines.extend(f"- {line}" for line in agreements) if agreements else report_lines.append("- No repeated agreement lines detected; controller review required.")
    report_lines.extend(["", "## Conflicts / Risks"])
    report_lines.extend(f"- {line}" for line in conflict_lines[:20]) if conflict_lines else report_lines.append("- No explicit conflict/risk markers detected.")
    return {"ok": True, "team_id": team_id, "run_ids": ids, "items": items, "agreements": agreements, "conflicts": conflict_lines[:20], "report": "\n".join(report_lines)}


def cross_review(
    run_ids: list[str],
    reviewer_roles: list[str] | None = None,
    cwd: Path | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    ids = resolve_team_run_ids(run_ids=run_ids)
    roles = reviewer_roles or ["security", "testing", "review"]
    bundle_lines = ["Review these previous worker outputs. Focus on contradictions, missed risks, and acceptance blockers.", ""]
    for run_id in ids:
        status = single_run_status(run_id, include_output_tail=True, tail_chars=6000)
        bundle_lines.extend([f"## Run {run_id} / role {status.get('role')} / status {status.get('status')}", str(status.get("stdout_tail", ""))[-6000:], ""])
    task = "Cross-review prior Claude Code worker outputs and produce second-round findings ordered by severity."
    spawned: list[dict[str, Any]] = []
    for role in roles:
        run = run_streaming_agent(task=task, role=role, cwd=cwd, context="\n".join(bundle_lines), timeout_seconds=timeout_seconds)
        spawned.append({"reviewer_role": role, "run_id": run["run_id"], "status": run["status"], "profile": run.get("profile")})
    return {"ok": True, "source_run_ids": ids, "review_runs": spawned}


def preflight_write_scope(
    cwd: Path | None = None,
    allowed_paths: list[str] | None = None,
    denied_paths: list[str] | None = None,
    max_diff_lines: int = 800,
) -> dict[str, Any]:
    root = (cwd or Path.cwd()).resolve()
    if not root.exists():
        raise OrchestratorError(f"cwd does not exist: {root}")
    def normalize(items: list[str] | None) -> list[str]:
        result: list[str] = []
        for item in items or []:
            candidate = (root / item).resolve()
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise OrchestratorError(f"Path is outside cwd: {item}") from exc
            result.append(str(candidate))
        return result
    data = {
        "created_at": utc_now_iso(),
        "cwd": str(root),
        "allowed_paths": normalize(allowed_paths),
        "denied_paths": normalize(denied_paths),
        "max_diff_lines": max_diff_lines,
        "rules": [
            "Claude Code may only edit allowed_paths.",
            "Claude Code must never edit denied_paths.",
            "Codex must review git diff before accepting changes.",
        ],
    }
    scope_dir = root / ".claude-code-orchestrator"
    scope_dir.mkdir(parents=True, exist_ok=True)
    path = scope_dir / "write-scope.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(path), "scope": data}


def diff_summary(cwd: Path | None = None, limit_chars: int = 200000) -> dict[str, Any]:
    diff = git_diff(cwd=cwd, limit_chars=limit_chars)
    text = diff.get("diff", "")
    files: dict[str, dict[str, Any]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            current = parts[-1][2:] if len(parts) >= 4 and parts[-1].startswith("b/") else parts[-1] if parts else None
            if current:
                files.setdefault(current, {"added": 0, "deleted": 0, "risk": []})
        elif current and line.startswith("+") and not line.startswith("+++"):
            files[current]["added"] += 1
        elif current and line.startswith("-") and not line.startswith("---"):
            files[current]["deleted"] += 1
    risk_keywords = {
        "package": "dependency/package metadata changed",
        "lock": "lockfile changed",
        "config": "configuration changed",
        "auth": "auth-sensitive path",
        "secret": "secret-sensitive path",
        "server": "runtime server path",
        "workflow": "CI workflow changed",
    }
    for file, info in files.items():
        lower = file.lower()
        for key, reason in risk_keywords.items():
            if key in lower:
                info["risk"].append(reason)
    total_added = sum(item["added"] for item in files.values())
    total_deleted = sum(item["deleted"] for item in files.values())
    needs_tests = bool(files) and (total_added + total_deleted > 20 or any(item["risk"] for item in files.values()))
    return {
        "ok": diff.get("ok", False),
        "cwd": diff.get("cwd"),
        "file_count": len(files),
        "total_added": total_added,
        "total_deleted": total_deleted,
        "files": files,
        "risks": [f"{file}: {', '.join(info['risk'])}" for file, info in files.items() if info["risk"]],
        "needs_tests": needs_tests,
        "truncated": diff.get("truncated", False),
    }


def secret_scan_text(text: str, source: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if SECRET_VALUE_RE.search(line) or (SECRET_KEY_RE.search(line) and "=" in line):
            findings.append({"source": source, "line": lineno, "snippet": str(redact(line))[:500]})
    return findings


def secret_scan_run(run_id: str, include_diff: bool = True) -> dict[str, Any]:
    run_dir = safe_run_dir(run_id)
    metadata = read_metadata(run_dir)
    findings: list[dict[str, Any]] = []
    for name in ("stdout.txt", "stderr.txt", "events.ndjson"):
        path = run_dir / name
        if path.exists():
            findings.extend(secret_scan_text(path.read_text(encoding="utf-8", errors="replace"), str(path)))
    if include_diff:
        cwd = Path(str(metadata.get("cwd") or Path.cwd()))
        if (cwd / ".git").exists():
            diff = git_diff(cwd=cwd, limit_chars=300000)
            findings.extend(secret_scan_text(str(diff.get("diff", "")), f"git-diff:{cwd}"))
    return {"ok": len(findings) == 0, "run_id": run_id, "finding_count": len(findings), "findings": findings[:100]}


def rollback_run(run_id: str, confirm: bool = False) -> dict[str, Any]:
    run_dir = safe_run_dir(run_id)
    metadata = read_metadata(run_dir)
    cwd = Path(str(metadata.get("cwd") or Path.cwd()))
    before = metadata.get("git_before") or {}
    after = metadata.get("git_after") or {}
    before_diff = Path(before.get("diff_path", "")) if before.get("diff_path") else None
    after_diff = Path(after.get("diff_path", "")) if after.get("diff_path") else None
    if not before.get("is_git_repo") or not (cwd / ".git").exists():
        return {"ok": False, "run_id": run_id, "error": "Rollback requires a git repository snapshot."}
    if not before_diff or not before_diff.exists() or not after_diff or not after_diff.exists():
        return {"ok": False, "run_id": run_id, "error": "Missing before/after git snapshots for this run."}
    if before_diff.read_text(encoding="utf-8", errors="replace").strip():
        return {
            "ok": False,
            "run_id": run_id,
            "error": "Pre-run worktree was dirty. Automated rollback is refused to avoid reverting unrelated user changes.",
            "before_diff_path": str(before_diff),
            "after_diff_path": str(after_diff),
        }
    if not confirm:
        return {
            "ok": False,
            "run_id": run_id,
            "requires_confirm": True,
            "message": "Pre-run diff was empty. Pass confirm=true to apply reverse patch for the post-run diff.",
            "after_diff_path": str(after_diff),
        }
    backup_path = run_dir / f"rollback-backup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.diff"
    current = subprocess.run(["git", "diff", "--binary", "--", "."], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    backup_path.write_text(str(redact(current.stdout or current.stderr or "")), encoding="utf-8")
    proc = subprocess.run(["git", "apply", "-R", str(after_diff)], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    return {
        "ok": proc.returncode == 0,
        "run_id": run_id,
        "exit_code": proc.returncode,
        "backup_path": str(backup_path),
        "stdout": str(redact(proc.stdout or ""))[-2000:],
        "stderr": str(redact(proc.stderr or ""))[-2000:],
    }


def load_cost_guard() -> dict[str, Any]:
    if COST_GUARD_PATH.exists():
        return json.loads(COST_GUARD_PATH.read_text(encoding="utf-8"))
    return {"max_concurrent": 4, "max_timeout_seconds": 1800, "per_model": {}, "updated_at": None}


def cost_guard(config: dict[str, Any] | None = None, apply: bool = False) -> dict[str, Any]:
    current = load_cost_guard()
    if config:
        current.update(config)
        current["updated_at"] = utc_now_iso()
        if apply:
            COST_GUARD_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(COST_GUARD_PATH), "applied": apply, "guard": current}


def enforce_cost_guard(model: str | None, timeout_seconds: int) -> int:
    guard = load_cost_guard()
    active = run_status(include_finished=False).get("active_count", 0)
    max_concurrent = int(guard.get("max_concurrent", 4))
    if active >= max_concurrent:
        raise OrchestratorError(f"Cost guard blocked run: active workers {active} >= max_concurrent {max_concurrent}.")
    timeout = min(timeout_seconds, int(guard.get("max_timeout_seconds", timeout_seconds)))
    if model:
        per_model = guard.get("per_model", {}).get(model, {})
        if per_model.get("max_timeout_seconds"):
            timeout = min(timeout, int(per_model["max_timeout_seconds"]))
    return timeout


def benchmark_model(
    profile: str | None = None,
    role: str = "testing",
    task: str = "Return a concise JSON object with keys ok and summary.",
    timeout_seconds: int = 120,
    execute: bool = False,
) -> dict[str, Any]:
    route = resolve_route(role=role, profile=profile)
    provider = get_provider(route["profile"])
    if not execute:
        return {
            "ok": True,
            "dry_run": True,
            "message": "Pass execute=true to run a real benchmark task through Claude Code.",
            "profile": provider.name,
            "model": route.get("model_override") or provider.model,
            "task": task,
        }
    started = time.time()
    run = run_agent(task=task, role=role, profile=profile, timeout_seconds=timeout_seconds, output_format="json")
    return {
        "ok": run.get("exit_code") == 0,
        "dry_run": False,
        "profile": provider.name,
        "model": route.get("model_override") or provider.model,
        "duration_ms": int((time.time() - started) * 1000),
        "run_id": run.get("run_id"),
        "exit_code": run.get("exit_code"),
        "stdout_tail": run.get("stdout_tail", "")[-2000:],
    }


def calibrate_policy(preferences: dict[str, Any], apply: bool = True) -> dict[str, Any]:
    data = {
        "updated_at": utc_now_iso(),
        "preferences": preferences,
        "notes": "Use this file to record local model preferences discovered from real workloads.",
    }
    if apply:
        CALIBRATION_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "applied": apply, "path": str(CALIBRATION_PATH), "calibration": data}


def dashboard(include_finished: bool = True, limit: int = 30, open_browser: bool = False) -> dict[str, Any]:
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    data = run_status(include_finished=include_finished, include_output_tail=True, tail_chars=1000, limit=limit)
    cards = []
    for item in data.get("runs", []):
        cards.append(
            f"<section class='card'><h2>{item.get('role')} <code>{item.get('run_id')}</code></h2>"
            f"<p>Status: <b>{item.get('status')}</b> Active: {item.get('active')} Elapsed: {item.get('elapsed_ms')} ms</p>"
            f"<p>Model: {(item.get('profile') or {}).get('model')}</p>"
            f"<pre>{str(item.get('last_stdout_line') or item.get('last_stderr_line') or '')}</pre></section>"
        )
    html = "\n".join(
        [
            "<!doctype html><html><head><meta charset='utf-8'><title>Claude Code Workers</title>",
            "<style>body{font-family:system-ui;background:#0d1117;color:#e6edf3;margin:24px}.card{border:1px solid #30363d;border-radius:8px;padding:16px;margin:12px 0;background:#161b22}code{color:#7ee787}pre{white-space:pre-wrap;color:#a5d6ff}</style>",
            "</head><body><h1>Claude Code Worker Dashboard</h1>",
            f"<p>Generated at {utc_now_iso()}</p>",
            "".join(cards) if cards else "<p>No runs found.</p>",
            "</body></html>",
        ]
    )
    path = DASHBOARD_DIR / "index.html"
    path.write_text(html, encoding="utf-8")
    if open_browser:
        if os.name == "nt":
            subprocess.Popen(["cmd", "/c", "start", "", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True, "path": str(path), "run_count": data.get("count", 0), "opened": open_browser}


def open_run_folder(run_id: str, open_folder: bool = True) -> dict[str, Any]:
    run_dir = safe_run_dir(run_id)
    if not run_dir.exists():
        raise OrchestratorError(f"Run not found: {run_id}")
    if open_folder:
        if os.name == "nt":
            subprocess.Popen(["explorer", str(run_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", str(run_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True, "run_id": run_id, "path": str(run_dir), "opened": open_folder}


def export_report(run_id: str | None = None, team_id: str | None = None, output_dir: Path | None = None) -> dict[str, Any]:
    report_dir = output_dir or REPORTS_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Claude Code Orchestrator Report", "", f"Generated: {utc_now_iso()}", ""]
    if team_id:
        collected = collect_team_results(team_id=team_id)
        lines.extend([collected["report"], ""])
        name = f"{team_id}.md"
    elif run_id:
        status = single_run_status(run_id, include_output_tail=True, tail_chars=10000)
        scan = secret_scan_run(run_id, include_diff=False)
        lines.extend(
            [
                f"Run: `{run_id}`",
                "",
                f"- Status: `{status.get('status')}`",
                f"- Role: `{status.get('role')}`",
                f"- Model: `{(status.get('profile') or {}).get('model')}`",
                f"- Elapsed: `{status.get('elapsed_ms')}` ms",
                f"- Secret scan findings: `{scan.get('finding_count')}`",
                "",
                "## Stdout Tail",
                "```text",
                str(status.get("stdout_tail", ""))[-10000:],
                "```",
                "",
                "## Stderr Tail",
                "```text",
                str(status.get("stderr_tail", ""))[-4000:],
                "```",
            ]
        )
        name = f"run-{run_id}.md"
    else:
        raise OrchestratorError("Provide run_id or team_id.")
    path = report_dir / name
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"ok": True, "path": str(path), "run_id": run_id, "team_id": team_id}


def run_visible_agent(
    task: str,
    role: str = "implementation",
    task_type: str | None = None,
    profile: str | None = None,
    allow_write: bool = False,
    cwd: Path | None = None,
    context: str | None = None,
) -> dict[str, Any]:
    """Open Claude Code in a visible PowerShell window with selected provider env."""
    if not task.strip():
        raise OrchestratorError("Task cannot be empty.")
    route = resolve_route(role=role, task_type=task_type, profile=profile)
    provider = get_provider(route["profile"])
    permission_mode = route["permission_mode"] if not allow_write else "acceptEdits"
    prompt = build_prompt(role, task, context)
    safe_prompt = str(redact(prompt))
    effective_cwd = cwd or Path.cwd()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    prompt_path = run_dir / "prompt.txt"
    bootstrap_path = run_dir / "start-visible.ps1"
    prompt_path.write_text(safe_prompt, encoding="utf-8")
    env = build_worker_env(provider.env, route.get("model_override"))
    env_for_log: dict[str, str] = {}
    for key, value in provider.env.items():
        env_for_log[key] = value
    if route.get("model_override"):
        env_for_log["ANTHROPIC_MODEL"] = str(route["model_override"])
    env_for_log["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    console_lines = [
        "[Console]::InputEncoding = [System.Text.UTF8Encoding]::new()",
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()",
        "$OutputEncoding = [System.Text.UTF8Encoding]::new()",
    ]
    script = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            f"Set-Location -LiteralPath {json.dumps(str(effective_cwd))}",
            *console_lines,
            f"$prompt = Get-Content -Raw -LiteralPath {json.dumps(str(prompt_path))}",
            f"& {json.dumps(claude_bin_path())} --permission-mode {permission_mode} $prompt",
            "Write-Host ''",
            "Write-Host 'Claude Code session ended. Press Enter to close this window.'",
            "[void][Console]::ReadLine()",
        ]
    )
    bootstrap_path.write_text(script, encoding="utf-8")
    metadata = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": "visible_window",
        "cwd": str(effective_cwd),
        "role": role,
        "task_type": route["task_type"],
        "profile": {
            "id": provider.id,
            "name": provider.name,
            "model": route.get("model_override") or provider.model,
            "provider_default_model": provider.model,
            "base_url": provider.env.get("ANTHROPIC_BASE_URL"),
            "endpoints": provider.endpoints,
        },
        "permission_mode": permission_mode,
        "allow_write": allow_write,
        "prompt_path": str(prompt_path),
        "bootstrap_path": str(bootstrap_path),
        "env": redact(env_for_log),
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.Popen(
        [
            "powershell",
            "-NoExit",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(bootstrap_path),
        ],
        cwd=str(effective_cwd),
        env=env,
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
    )
    (RUNS_DIR / "latest.txt").write_text(run_id, encoding="utf-8")
    return metadata


def git_diff(cwd: Path | None = None, limit_chars: int = 12000) -> dict[str, Any]:
    effective_cwd = cwd or Path.cwd()
    if not (effective_cwd / ".git").exists():
        return {"ok": False, "error": f"Not a git repository: {effective_cwd}"}
    proc = subprocess.run(
        ["git", "diff", "--", "."],
        cwd=str(effective_cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    text = proc.stdout or proc.stderr or ""
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "cwd": str(effective_cwd),
        "truncated": len(text) > limit_chars,
        "diff": text[:limit_chars],
    }


def run_workflow_plan(task: str, cwd: Path | None = None) -> dict[str, Any]:
    """Return a deterministic multi-agent run plan without launching every agent."""
    steps = []
    for role in ROLE_ORDER:
        route = resolve_route(role=role)
        provider = get_provider(route["profile"])
        steps.append(
            {
                "role": role,
                "task_type": route["task_type"],
                "profile": provider.name,
                "model": route.get("model_override") or provider.model,
                "permission_mode": route["permission_mode"],
                "timeout_seconds": route["timeout_seconds"],
                "selection_score": (route.get("auto_selection") or {}).get("score"),
                "selection_role": route.get("selection_role", role),
                "reason": route.get("reason", ""),
            }
        )
    return {
        "task": task,
        "cwd": str(cwd or Path.cwd()),
        "controller": "codex",
        "worker_roles": ROLE_ORDER,
        "phases": [
            "parallel_analysis",
            "cross_review",
            "execution",
            "controller_summary",
        ],
        "steps": steps,
    }


def default_auto_policy() -> dict[str, Any]:
    return {
        "default_profile": "auto",
        "profile_aliases": {
            "strong_text": "auto:architecture",
            "code_strong": "auto:implementation",
            "development_strong": "auto:development",
            "review_strong": "auto:review",
            "security_strong": "auto:security",
            "performance_strong": "auto:performance",
            "compatibility_stable": "auto:compatibility",
            "documentation_balanced": "auto:documentation",
            "automation_strong": "auto:automation",
            "multimodal": "auto:multimodal",
            "general": "auto:requirements",
            "fast": "auto:testing",
            "ops": "auto:ops",
        },
        "task_routes": {
            "simple": {"profile_alias": "fast", "permission_mode": "plan", "timeout_seconds": 180, "reason": "Fast low-risk planning or summarization."},
            "normal": {"profile_alias": "general", "permission_mode": "plan", "timeout_seconds": 420, "reason": "Balanced local model for routine project analysis."},
            "complex_code": {"profile_alias": "code_strong", "permission_mode": "plan", "timeout_seconds": 900, "reason": "Highest local score for code implementation."},
            "development": {"profile_alias": "development_strong", "permission_mode": "plan", "timeout_seconds": 900, "reason": "Highest local score for main code development."},
            "review": {"profile_alias": "review_strong", "permission_mode": "plan", "timeout_seconds": 600, "reason": "Highest local score for code review."},
            "security_review": {"profile_alias": "security_strong", "permission_mode": "plan", "timeout_seconds": 600, "reason": "Highest local score for security review."},
            "performance_review": {"profile_alias": "performance_strong", "permission_mode": "plan", "timeout_seconds": 600, "reason": "Best local fit for runtime, IO, and resource optimization review."},
            "compatibility_review": {"profile_alias": "compatibility_stable", "permission_mode": "plan", "timeout_seconds": 600, "reason": "Best local fit for multi-environment compatibility checks."},
            "documentation": {"profile_alias": "documentation_balanced", "permission_mode": "plan", "timeout_seconds": 420, "reason": "Balanced local model for documentation and examples."},
            "automation": {"profile_alias": "automation_strong", "permission_mode": "plan", "timeout_seconds": 600, "reason": "Best local fit for CI/CD and repeatable automation work."},
            "architecture": {"profile_alias": "strong_text", "permission_mode": "plan", "timeout_seconds": 600, "reason": "Highest local score for architecture reasoning."},
            "multimodal": {"profile_alias": "multimodal", "permission_mode": "plan", "timeout_seconds": 600, "reason": "Highest local score for multimodal tasks."},
            "ops": {"profile_alias": "ops", "permission_mode": "plan", "timeout_seconds": 420, "reason": "Stable local model for operational checks."},
        },
        "role_defaults": {
            "requirements": "normal",
            "architecture": "architecture",
            "development": "development",
            "security": "security_review",
            "testing": "simple",
            "implementation": "complex_code",
            "review": "review",
            "performance": "performance_review",
            "compatibility": "compatibility_review",
            "documentation": "documentation",
            "automation": "automation",
            "ops": "ops",
            "multimodal": "multimodal",
        },
        "safety": {
            "default_write_enabled": False,
            "visible_window_default": False,
            "max_timeout_seconds": 1800,
            "redact_secret_values": True,
        },
    }


def write_auto_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    policy = default_auto_policy()
    path.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "policy_path": str(path), "policy": policy}


def write_reports(output_dir: Path | None = None) -> dict[str, Any]:
    report_dir = output_dir or (ROOT / "reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    scores = score_models()
    plan = run_workflow_plan("local multi-agent routing calibration")
    scores_path = report_dir / "model_scores.json"
    strategy_path = report_dir / "multi_agent_strategy.md"
    scores_path.write_text(json.dumps(scores, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Claude Code Orchestrator Strategy",
        "",
        "Scoring source: local CCSwitch configuration plus heuristic public documentation signals. This is not a paid benchmark run.",
        "",
        "## Models",
        "",
    ]
    for item in scores["models"]:
        lines.append(f"- `{item['model']}` via `{item['profile_name']}`: overall {item['overall']}/10; role scores {json.dumps(item['role_scores'], ensure_ascii=False)}")
    lines.extend(["", "## Multi-Agent Routing", ""])
    for step in plan["steps"]:
        lines.append(
            f"- `{step['role']}` -> profile `{step['profile']}`, model `{step['model']}`, permission `{step['permission_mode']}`, score `{step['selection_score']}`"
        )
    lines.extend(
        [
            "",
            "## Research References",
            "",
            "- Qwen documentation: https://qwen.readthedocs.io/en/latest/",
            "- Qwen concepts and tool-calling notes: https://qwen.readthedocs.io/en/latest/getting_started/concepts.html",
            "- GLM-5 official blog: https://z.ai/blog/glm-5",
            "",
            "## Notes",
            "",
            "- Write access remains disabled by default; pass allow_write only for scoped implementation tasks.",
            "- If a configured model disappears from CCSwitch, routing falls back to the highest-scored available local model.",
            "- Secrets are redacted from tool output and persisted logs.",
        ]
    )
    strategy_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "scores_path": str(scores_path), "strategy_path": str(strategy_path), "workflow_plan": plan}


def build_claude_md(role: str = "implementation", project_name: str | None = None) -> str:
    agents = load_json(AGENTS_PATH)
    agent = agents.get(role) or agents.get("implementation", {})
    role_prompt = agent.get("prompt", "")
    role_description = agent.get("description", "Claude Code worker controlled by Codex.")
    title = project_name or "this repository"
    return "\n".join(
        [
            CLAUDE_MD_MARKER_BEGIN,
            "# CLAUDE.md",
            "",
            "You are a Claude Code worker inside a Codex-controlled multi-agent workflow.",
            "",
            f"Project: {title}",
            f"Assigned role: {role}",
            f"Role purpose: {role_description}",
            "",
            "## Control Model",
            "",
            "- Codex is the controller, planner, reviewer, and final decision maker.",
            "- Claude Code is an external worker process launched by Claude Code Orchestrator.",
            "- Do not treat your own output as final until Codex reviews it.",
            "- Keep work scoped to the user request and the current repository.",
            "",
            "## Role Instruction",
            "",
            role_prompt or "Follow the assigned role and keep output concise, safe, and verifiable.",
            "",
            "## Safety Rules",
            "",
            "- Do not print secrets, API keys, cookies, tokens, or hidden config values.",
            "- Do not run destructive commands unless the user explicitly requested them.",
            "- Do not revert unrelated user changes.",
            "- Prefer read-only analysis unless write access is explicitly granted.",
            "- When editing, list changed files and verification results.",
            "- If blocked, report the blocker, the evidence, and the smallest next action.",
            "",
            "## Progress Reporting",
            "",
            "- State the current phase before long work.",
            "- Prefer short, structured summaries.",
            "- Mention tests or checks actually run.",
            "- Save important reasoning in the final response, not in hidden state.",
            CLAUDE_MD_MARKER_END,
            "",
        ]
    )


def write_claude_md(
    cwd: Path | None = None,
    role: str = "implementation",
    project_name: str | None = None,
    append: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    effective_cwd = (cwd or Path.cwd()).resolve()
    effective_cwd.mkdir(parents=True, exist_ok=True)
    path = effective_cwd / "CLAUDE.md"
    content = build_claude_md(role=role, project_name=project_name or effective_cwd.name)
    backup_path: Path | None = None

    if path.exists():
        current = path.read_text(encoding="utf-8", errors="replace")
        if CLAUDE_MD_MARKER_BEGIN in current and CLAUDE_MD_MARKER_END in current:
            updated = re.sub(
                re.escape(CLAUDE_MD_MARKER_BEGIN) + r".*?" + re.escape(CLAUDE_MD_MARKER_END) + r"\n?",
                content,
                current,
                flags=re.DOTALL,
            )
            path.write_text(updated, encoding="utf-8")
            return {
                "ok": True,
                "path": str(path),
                "mode": "updated-managed-section",
                "backup_path": None,
                "role": role,
            }
        if append:
            path.write_text(current.rstrip() + "\n\n" + content, encoding="utf-8")
            return {
                "ok": True,
                "path": str(path),
                "mode": "appended-managed-section",
                "backup_path": None,
                "role": role,
            }
        if force:
            backup_path = path.with_name(f"CLAUDE.md.backup.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
            backup_path.write_text(current, encoding="utf-8")
            path.write_text(content, encoding="utf-8")
            return {
                "ok": True,
                "path": str(path),
                "mode": "replaced-with-backup",
                "backup_path": str(backup_path),
                "role": role,
            }
        return {
            "ok": False,
            "path": str(path),
            "error": "CLAUDE.md already exists. Use append=true to add a managed section or force=true to replace with a backup.",
            "role": role,
        }

    path.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "path": str(path),
        "mode": "created",
        "backup_path": None,
        "role": role,
    }


def selftest() -> dict[str, Any]:
    env = force_utf8_env({})
    decoded = subprocess_text("中文✅".encode("utf-8"))
    claude_md = build_claude_md("review", "selftest")
    sample_github_token = "ghp_" + ("1" * 36)
    sample_api_key = "sk-" + "testSecretValue"
    redacted = str(redact(f"token {sample_github_token} {sample_api_key}"))
    try:
        safe_run_dir("../bad")
        run_id_rejected = False
    except OrchestratorError:
        run_id_rejected = True
    worker_env = build_worker_env({"ANTHROPIC_API_KEY": sample_api_key})
    checks = {
        "utf8_env": env.get("PYTHONIOENCODING") == "utf-8" and env.get("PYTHONUTF8") == "1",
        "timeout_bytes_decode": decoded == "中文✅",
        "policy_exists": POLICY_PATH.exists(),
        "agents_exists": AGENTS_PATH.exists(),
        "claude_md_template": "Assigned role: review" in claude_md and CLAUDE_MD_MARKER_BEGIN in claude_md,
        "secret_redaction": sample_github_token not in redacted and sample_api_key not in redacted,
        "run_id_validation": run_id_rejected,
        "worker_env_allowlist": "ANTHROPIC_API_KEY" in worker_env and "GITHUB_TOKEN" not in worker_env and "NPM_TOKEN" not in worker_env,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "decoded_sample": decoded,
    }


def last_run(run_id: str | None = None, include_output: bool = True) -> dict[str, Any]:
    if run_id is None:
        latest_path = RUNS_DIR / "latest.txt"
        if not latest_path.exists():
            raise OrchestratorError("No runs found yet.")
        run_id = latest_path.read_text(encoding="utf-8").strip()
    run_dir = safe_run_dir(run_id)
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.exists():
        raise OrchestratorError(f"Run metadata not found: {run_id}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if include_output:
        for name in ("stdout", "stderr"):
            path = run_dir / f"{name}.txt"
            metadata[f"{name}_tail"] = path.read_text(encoding="utf-8", errors="replace")[-4000:] if path.exists() else ""
    return metadata


def print_json(data: Any) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace") + b"\n")


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_json_arg(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise OrchestratorError(f"Invalid JSON argument: {exc}") from exc


def parse_key_values(items: list[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise OrchestratorError(f"Expected key=value, got: {item}")
        key, value = item.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Claude Code orchestrator backed by CCSwitch.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("healthcheck")
    lp = sub.add_parser("list-profiles")
    lp.add_argument("--include-secrets", action="store_true")
    pick = sub.add_parser("pick")
    pick.add_argument("--role", default="implementation")
    pick.add_argument("--task-type")
    pick.add_argument("--profile")
    run = sub.add_parser("run")
    run.add_argument("task")
    run.add_argument("--role", default="implementation")
    run.add_argument("--task-type")
    run.add_argument("--profile")
    run.add_argument("--allow-write", action="store_true")
    run.add_argument("--timeout-seconds", type=int)
    run.add_argument("--cwd")
    stream = sub.add_parser("run-streaming")
    stream.add_argument("task")
    stream.add_argument("--role", default="implementation")
    stream.add_argument("--task-type")
    stream.add_argument("--profile")
    stream.add_argument("--allow-write", action="store_true")
    stream.add_argument("--timeout-seconds", type=int)
    stream.add_argument("--cwd")
    stream.add_argument("--context")
    stream.add_argument("--no-include-partial-messages", action="store_true")
    poll = sub.add_parser("poll-run")
    poll.add_argument("--run-id", required=True)
    poll.add_argument("--stdout-offset", type=int, default=0)
    poll.add_argument("--stderr-offset", type=int, default=0)
    poll.add_argument("--event-offset", type=int, default=0)
    poll.add_argument("--max-bytes", type=int, default=20000)
    poll.add_argument("--tail-chars", type=int, default=4000)
    poll.add_argument("--no-output-tail", action="store_true")
    stop = sub.add_parser("stop-run")
    stop.add_argument("--run-id", required=True)
    stop.add_argument("--force", action="store_true")
    stop.add_argument("--timeout-seconds", type=int, default=5)
    status = sub.add_parser("run-status")
    status.add_argument("--run-id")
    status.add_argument("--include-output", action="store_true")
    status.add_argument("--include-finished", action="store_true")
    status.add_argument("--tail-chars", type=int, default=4000)
    status.add_argument("--limit", type=int, default=50)
    send = sub.add_parser("send-instruction")
    send.add_argument("--run-id", required=True)
    send.add_argument("instruction")
    send.add_argument("--force", action="store_true")
    send.add_argument("--role")
    send.add_argument("--task-type")
    send.add_argument("--timeout-seconds", type=int)
    team = sub.add_parser("spawn-role-team")
    team.add_argument("task")
    team.add_argument("--roles", default="requirements,architecture,security,testing")
    team.add_argument("--cwd")
    team.add_argument("--context")
    team.add_argument("--timeout-seconds", type=int)
    collect = sub.add_parser("collect-team-results")
    collect.add_argument("--team-id")
    collect.add_argument("--run-id", action="append", dest="run_ids")
    collect.add_argument("--tail-chars", type=int, default=8000)
    cross = sub.add_parser("cross-review")
    cross.add_argument("--run-id", action="append", dest="run_ids", required=True)
    cross.add_argument("--reviewer-roles", default="security,testing,review")
    cross.add_argument("--cwd")
    cross.add_argument("--timeout-seconds", type=int)
    scope = sub.add_parser("preflight-write-scope")
    scope.add_argument("--cwd")
    scope.add_argument("--allow", action="append", dest="allowed_paths")
    scope.add_argument("--deny", action="append", dest="denied_paths")
    scope.add_argument("--max-diff-lines", type=int, default=800)
    diff_summary_cmd = sub.add_parser("diff-summary")
    diff_summary_cmd.add_argument("--cwd")
    secret_scan = sub.add_parser("secret-scan-run")
    secret_scan.add_argument("--run-id", required=True)
    secret_scan.add_argument("--no-diff", action="store_true")
    rollback = sub.add_parser("rollback-run")
    rollback.add_argument("--run-id", required=True)
    rollback.add_argument("--confirm", action="store_true")
    bench = sub.add_parser("benchmark-model")
    bench.add_argument("--profile")
    bench.add_argument("--role", default="testing")
    bench.add_argument("--task", default="Return a concise JSON object with keys ok and summary.")
    bench.add_argument("--timeout-seconds", type=int, default=120)
    bench.add_argument("--execute", action="store_true")
    calibrate = sub.add_parser("calibrate-policy")
    calibrate.add_argument("--preferences-json", default="{}")
    calibrate.add_argument("--preference", action="append", dest="preferences")
    calibrate.add_argument("--no-apply", action="store_true")
    guard = sub.add_parser("cost-guard")
    guard.add_argument("--config-json", default="{}")
    guard.add_argument("--max-concurrent", type=int)
    guard.add_argument("--max-timeout-seconds", type=int)
    guard.add_argument("--apply", action="store_true")
    dash = sub.add_parser("dashboard")
    dash.add_argument("--include-finished", action="store_true")
    dash.add_argument("--limit", type=int, default=30)
    dash.add_argument("--open", action="store_true")
    open_folder = sub.add_parser("open-run-folder")
    open_folder.add_argument("--run-id", required=True)
    open_folder.add_argument("--no-open", action="store_true")
    export = sub.add_parser("export-report")
    export.add_argument("--run-id")
    export.add_argument("--team-id")
    export.add_argument("--output-dir")
    visible = sub.add_parser("run-visible")
    visible.add_argument("task")
    visible.add_argument("--role", default="implementation")
    visible.add_argument("--task-type")
    visible.add_argument("--profile")
    visible.add_argument("--allow-write", action="store_true")
    visible.add_argument("--cwd")
    diff = sub.add_parser("diff")
    diff.add_argument("--cwd")
    workflow = sub.add_parser("workflow-plan")
    workflow.add_argument("task")
    workflow.add_argument("--cwd")
    sub.add_parser("score-models")
    sub.add_parser("write-auto-policy")
    reports = sub.add_parser("write-reports")
    reports.add_argument("--output-dir")
    claude_md = sub.add_parser("write-claude-md")
    claude_md.add_argument("--cwd")
    claude_md.add_argument("--role", default="implementation")
    claude_md.add_argument("--project-name")
    claude_md.add_argument("--append", action="store_true")
    claude_md.add_argument("--force", action="store_true")
    sub.add_parser("selftest")
    last = sub.add_parser("last-run")
    last.add_argument("--run-id")
    worker = sub.add_parser("_stream-worker")
    worker.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        if args.command == "healthcheck":
            print_json(healthcheck())
        elif args.command == "list-profiles":
            print_json(list_profiles(include_secrets=args.include_secrets))
        elif args.command == "pick":
            route = resolve_route(args.role, args.task_type, args.profile)
            provider = get_provider(route["profile"])
            print_json({**route, "selected_provider": redact(provider.settings), "model": route.get("model_override") or provider.model})
        elif args.command == "run":
            print_json(
                run_agent(
                    task=args.task,
                    role=args.role,
                    task_type=args.task_type,
                    profile=args.profile,
                    allow_write=args.allow_write,
                    timeout_seconds=args.timeout_seconds,
                    cwd=Path(args.cwd) if args.cwd else None,
                )
            )
        elif args.command == "run-streaming":
            print_json(
                run_streaming_agent(
                    task=args.task,
                    role=args.role,
                    task_type=args.task_type,
                    profile=args.profile,
                    allow_write=args.allow_write,
                    timeout_seconds=args.timeout_seconds,
                    cwd=Path(args.cwd) if args.cwd else None,
                    context=args.context,
                    include_partial_messages=not args.no_include_partial_messages,
                )
            )
        elif args.command == "poll-run":
            print_json(
                poll_run(
                    run_id=args.run_id,
                    stdout_offset=args.stdout_offset,
                    stderr_offset=args.stderr_offset,
                    event_offset=args.event_offset,
                    max_bytes=args.max_bytes,
                    include_output_tail=not args.no_output_tail,
                    tail_chars=args.tail_chars,
                )
            )
        elif args.command == "stop-run":
            print_json(stop_run(run_id=args.run_id, force=args.force, timeout_seconds=args.timeout_seconds))
        elif args.command == "run-status":
            print_json(
                run_status(
                    run_id=args.run_id,
                    include_output_tail=args.include_output,
                    tail_chars=args.tail_chars,
                    include_finished=args.include_finished,
                    limit=args.limit,
                )
            )
        elif args.command == "send-instruction":
            print_json(
                send_instruction(
                    run_id=args.run_id,
                    instruction=args.instruction,
                    force=args.force,
                    role=args.role,
                    task_type=args.task_type,
                    timeout_seconds=args.timeout_seconds,
                )
            )
        elif args.command == "spawn-role-team":
            print_json(
                spawn_role_team(
                    task=args.task,
                    roles=split_csv(args.roles),
                    cwd=Path(args.cwd) if args.cwd else None,
                    context=args.context,
                    timeout_seconds=args.timeout_seconds,
                )
            )
        elif args.command == "collect-team-results":
            print_json(collect_team_results(team_id=args.team_id, run_ids=args.run_ids, tail_chars=args.tail_chars))
        elif args.command == "cross-review":
            print_json(
                cross_review(
                    run_ids=args.run_ids,
                    reviewer_roles=split_csv(args.reviewer_roles),
                    cwd=Path(args.cwd) if args.cwd else None,
                    timeout_seconds=args.timeout_seconds,
                )
            )
        elif args.command == "preflight-write-scope":
            print_json(
                preflight_write_scope(
                    cwd=Path(args.cwd) if args.cwd else None,
                    allowed_paths=args.allowed_paths,
                    denied_paths=args.denied_paths,
                    max_diff_lines=args.max_diff_lines,
                )
            )
        elif args.command == "diff-summary":
            print_json(diff_summary(cwd=Path(args.cwd) if args.cwd else None))
        elif args.command == "secret-scan-run":
            print_json(secret_scan_run(args.run_id, include_diff=not args.no_diff))
        elif args.command == "rollback-run":
            print_json(rollback_run(args.run_id, confirm=args.confirm))
        elif args.command == "benchmark-model":
            print_json(
                benchmark_model(
                    profile=args.profile,
                    role=args.role,
                    task=args.task,
                    timeout_seconds=args.timeout_seconds,
                    execute=args.execute,
                )
            )
        elif args.command == "calibrate-policy":
            preferences = parse_json_arg(args.preferences_json)
            preferences.update(parse_key_values(args.preferences))
            print_json(calibrate_policy(preferences, apply=not args.no_apply))
        elif args.command == "cost-guard":
            guard_config = parse_json_arg(args.config_json)
            if args.max_concurrent is not None:
                guard_config["max_concurrent"] = args.max_concurrent
            if args.max_timeout_seconds is not None:
                guard_config["max_timeout_seconds"] = args.max_timeout_seconds
            print_json(cost_guard(guard_config, apply=args.apply))
        elif args.command == "dashboard":
            print_json(dashboard(include_finished=args.include_finished, limit=args.limit, open_browser=args.open))
        elif args.command == "open-run-folder":
            print_json(open_run_folder(args.run_id, open_folder=not args.no_open))
        elif args.command == "export-report":
            print_json(export_report(run_id=args.run_id, team_id=args.team_id, output_dir=Path(args.output_dir) if args.output_dir else None))
        elif args.command == "run-visible":
            print_json(
                run_visible_agent(
                    task=args.task,
                    role=args.role,
                    task_type=args.task_type,
                    profile=args.profile,
                    allow_write=args.allow_write,
                    cwd=Path(args.cwd) if args.cwd else None,
                )
            )
        elif args.command == "diff":
            print_json(git_diff(cwd=Path(args.cwd) if args.cwd else None))
        elif args.command == "workflow-plan":
            print_json(run_workflow_plan(args.task, cwd=Path(args.cwd) if args.cwd else None))
        elif args.command == "score-models":
            print_json(score_models())
        elif args.command == "write-auto-policy":
            print_json(write_auto_policy())
        elif args.command == "write-reports":
            print_json(write_reports(output_dir=Path(args.output_dir) if args.output_dir else None))
        elif args.command == "write-claude-md":
            print_json(
                write_claude_md(
                    cwd=Path(args.cwd) if args.cwd else None,
                    role=args.role,
                    project_name=args.project_name,
                    append=args.append,
                    force=args.force,
                )
            )
        elif args.command == "selftest":
            print_json(selftest())
        elif args.command == "last-run":
            print_json(last_run(args.run_id))
        elif args.command == "_stream-worker":
            print_json(stream_worker(args.run_id))
        return 0
    except OrchestratorError as exc:
        print_json({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
