#!/usr/bin/env python3
"""Claude Code orchestration helpers backed by CCSwitch profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
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
POLICY_PATH = CONFIG_DIR / "model_policy.json"
AGENTS_PATH = CONFIG_DIR / "agents.json"
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
        candidates.append(explicit)
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
        return 0
    except OrchestratorError as exc:
        print_json({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
