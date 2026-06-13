#!/usr/bin/env python3
"""MCP server exposing Claude Code orchestration tools."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from cc_orchestrator import (
    ROLE_ORDER,
    OrchestratorError,
    healthcheck,
    git_diff,
    last_run,
    list_profiles,
    score_models,
    resolve_route,
    get_provider,
    run_agent,
    run_visible_agent,
    run_workflow_plan,
    write_claude_md,
    write_reports,
)


mcp = FastMCP("claude_code_mcp")
ROLE_DESCRIPTION = "Agent role. Supported: " + ", ".join(ROLE_ORDER) + ". Codex remains the controller."
TASK_TYPE_DESCRIPTION = (
    "Optional task route key. Supported: simple, normal, complex_code, development, "
    "review, security_review, performance_review, compatibility_review, documentation, "
    "automation, architecture, multimodal, ops."
)


class ResponseFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"


class ListProfilesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    include_current_first: bool = Field(default=True, description="Reserved for compatibility; profiles are always current-first.")
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON, description="Return JSON or markdown.")


class PickProfileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    role: str = Field(default="implementation", description=ROLE_DESCRIPTION)
    task_type: Optional[str] = Field(default=None, description=TASK_TYPE_DESCRIPTION)
    profile: Optional[str] = Field(default=None, description="Optional explicit CCSwitch profile name or id.")
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON, description="Return JSON or markdown.")


class RunAgentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    task: str = Field(..., min_length=1, max_length=20000, description="Task to give Claude Code.")
    role: str = Field(default="implementation", description=ROLE_DESCRIPTION)
    task_type: Optional[str] = Field(default=None, description=TASK_TYPE_DESCRIPTION)
    profile: Optional[str] = Field(default=None, description="Optional explicit CCSwitch profile name or id.")
    allow_write: bool = Field(default=False, description="Allow Claude Code to use acceptEdits. Defaults to read-only/plan behavior.")
    timeout_seconds: Optional[int] = Field(default=None, ge=10, le=1800, description="Optional timeout override.")
    cwd: Optional[str] = Field(default=None, description="Working directory for Claude Code. Defaults to MCP server cwd.")
    context: Optional[str] = Field(default=None, max_length=20000, description="Additional context to append to the prompt.")


class LastRunInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    run_id: Optional[str] = Field(default=None, description="Run id. Defaults to latest run.")
    include_output: bool = Field(default=True, description="Include stdout/stderr tails.")
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON, description="Return JSON or markdown.")


class DiffInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    cwd: Optional[str] = Field(default=None, description="Git repository path. Defaults to MCP server cwd.")
    limit_chars: int = Field(default=12000, ge=1000, le=100000, description="Maximum diff characters to return.")


class WorkflowPlanInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    task: str = Field(..., min_length=1, max_length=20000, description="User task to plan for the configured Codex-controlled multi-agent workflow.")
    cwd: Optional[str] = Field(default=None, description="Working directory for the workflow.")


class ReportInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    output_dir: Optional[str] = Field(default=None, description="Optional report output directory. Defaults to reports/ under the orchestrator.")
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON, description="Return JSON or markdown.")


class ClaudeMdInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    cwd: Optional[str] = Field(default=None, description="Project directory where CLAUDE.md should be written. Defaults to MCP server cwd.")
    role: str = Field(default="implementation", description=ROLE_DESCRIPTION)
    project_name: Optional[str] = Field(default=None, description="Optional human-readable project name.")
    append: bool = Field(default=False, description="Append a managed section if CLAUDE.md already exists.")
    force: bool = Field(default=False, description="Replace CLAUDE.md after writing a timestamped backup.")


def _json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _error(exc: Exception) -> str:
    return _json({"ok": False, "error": str(exc), "next_step": "Check cc_healthcheck and profile names, then retry."})


def _profiles_markdown(profiles: list[dict]) -> str:
    lines = ["# Claude Code CCSwitch Profiles", ""]
    for item in profiles:
        current = " current" if item.get("current") else ""
        lines.append(f"## {item.get('name')} ({item.get('id')}){current}")
        lines.append(f"- Model: `{item.get('model')}`")
        lines.append(f"- Base URL: `{item.get('base_url')}`")
        if item.get("endpoints"):
            lines.append(f"- Endpoints: {', '.join(f'`{x}`' for x in item['endpoints'])}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool(
    name="cc_healthcheck",
    annotations={
        "title": "Claude Code Orchestrator Healthcheck",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def cc_healthcheck() -> str:
    """Check Claude Code, CCSwitch, and orchestrator configuration.

    Returns JSON with binary path, CCSwitch database status, config status, profile count,
    current CCSwitch profile, and Claude Code version command result.
    """
    try:
        return _json(healthcheck())
    except Exception as exc:
        return _error(exc)


@mcp.tool(
    name="cc_list_profiles",
    annotations={
        "title": "List CCSwitch Claude Profiles",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def cc_list_profiles(params: ListProfilesInput) -> str:
    """List Claude Code provider profiles from CCSwitch with secrets redacted.

    Args:
        params (ListProfilesInput): Output options.

    Returns:
        JSON or markdown profile list including id, name, current status, model,
        base URL, endpoints, and redacted settings.
    """
    try:
        profiles = list_profiles(include_secrets=False)
        if params.response_format == ResponseFormat.MARKDOWN:
            return _profiles_markdown(profiles)
        return _json({"count": len(profiles), "profiles": profiles})
    except Exception as exc:
        return _error(exc)


@mcp.tool(
    name="cc_pick_profile",
    annotations={
        "title": "Pick Claude Code Profile",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def cc_pick_profile(params: PickProfileInput) -> str:
    """Resolve which CCSwitch profile/model should be used for a role and task type.

    This does not start Claude Code and does not modify global CCSwitch state.
    """
    try:
        route = resolve_route(role=params.role, task_type=params.task_type, profile=params.profile)
        provider = get_provider(route["profile"])
        data = {
            **route,
            "selected_profile": {
                "id": provider.id,
                "name": provider.name,
                "model": route.get("model_override") or provider.model,
                "provider_default_model": provider.model,
                "base_url": provider.env.get("ANTHROPIC_BASE_URL"),
                "endpoints": provider.endpoints,
            },
        }
        if params.response_format == ResponseFormat.MARKDOWN:
            return "\n".join(
                [
                    "# Selected Claude Code Profile",
                    "",
                    f"- Role: `{data['role']}`",
                    f"- Task type: `{data['task_type']}`",
                    f"- Profile: `{provider.name}`",
                    f"- Model: `{provider.model}`",
                    f"- Permission mode: `{data['permission_mode']}`",
                    f"- Reason: {data.get('reason') or 'No route reason configured.'}",
                ]
            )
        return _json(data)
    except Exception as exc:
        return _error(exc)


@mcp.tool(
    name="cc_run_agent",
    annotations={
        "title": "Run Claude Code Agent",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def cc_run_agent(params: RunAgentInput) -> str:
    """Run Claude Code once using a selected CCSwitch profile and role prompt.

    The orchestrator injects provider environment variables into only this subprocess.
    By default it uses plan/read-only behavior. Pass allow_write=true only for scoped
    implementation work after the caller has decided file edits are appropriate.

    Returns JSON metadata with run id, profile/model, exit code, timeout status, log paths,
    and stdout/stderr tails. Secrets are redacted from persisted logs.
    """
    try:
        data = run_agent(
            task=params.task,
            role=params.role,
            task_type=params.task_type,
            profile=params.profile,
            allow_write=params.allow_write,
            timeout_seconds=params.timeout_seconds,
            cwd=Path(params.cwd) if params.cwd else None,
            context=params.context,
        )
        return _json(data)
    except OrchestratorError as exc:
        return _error(exc)


@mcp.tool(
    name="cc_run_visible_agent",
    annotations={
        "title": "Run Claude Code in Visible Window",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def cc_run_visible_agent(params: RunAgentInput) -> str:
    """Open a visible PowerShell window running Claude Code with selected CCSwitch profile.

    Use when the user wants to watch or manually take over the Claude Code session.
    The prompt and launcher script are stored under runs/<run_id>/.
    """
    try:
        data = run_visible_agent(
            task=params.task,
            role=params.role,
            task_type=params.task_type,
            profile=params.profile,
            allow_write=params.allow_write,
            cwd=Path(params.cwd) if params.cwd else None,
            context=params.context,
        )
        return _json(data)
    except Exception as exc:
        return _error(exc)


@mcp.tool(
    name="cc_last_run",
    annotations={
        "title": "Get Last Claude Code Run",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def cc_last_run(params: LastRunInput) -> str:
    """Return metadata and optional output tails for a previous Claude Code run."""
    try:
        data = last_run(run_id=params.run_id, include_output=params.include_output)
        if params.response_format == ResponseFormat.MARKDOWN:
            return "\n".join(
                [
                    "# Claude Code Run",
                    "",
                    f"- Run id: `{data.get('run_id')}`",
                    f"- Role: `{data.get('role')}`",
                    f"- Profile: `{data.get('profile', {}).get('name')}`",
                    f"- Model: `{data.get('profile', {}).get('model')}`",
                    f"- Exit code: `{data.get('exit_code')}`",
                    f"- Timed out: `{data.get('timed_out')}`",
                    "",
                    "## Stdout Tail",
                    "```",
                    str(data.get("stdout_tail", "")),
                    "```",
                    "",
                    "## Stderr Tail",
                    "```",
                    str(data.get("stderr_tail", "")),
                    "```",
                ]
            )
        return _json(data)
    except Exception as exc:
        return _error(exc)


@mcp.tool(
    name="cc_git_diff",
    annotations={
        "title": "Get Git Diff",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def cc_git_diff(params: DiffInput) -> str:
    """Return git diff for a repository after Claude Code runs."""
    try:
        return _json(git_diff(cwd=Path(params.cwd) if params.cwd else None, limit_chars=params.limit_chars))
    except Exception as exc:
        return _error(exc)


@mcp.tool(
    name="cc_workflow_plan",
    annotations={
        "title": "Plan Claude Code Multi-Agent Workflow",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def cc_workflow_plan(params: WorkflowPlanInput) -> str:
    """Return the configured role/model/permission plan for the Codex-controlled workflow.

    Worker roles include requirements, development, testing, review, performance,
    compatibility, documentation, automation, security, ops, plus legacy architecture,
    implementation, and multimodal roles.
    """
    try:
        return _json(run_workflow_plan(params.task, cwd=Path(params.cwd) if params.cwd else None))
    except Exception as exc:
        return _error(exc)


@mcp.tool(
    name="cc_write_claude_md",
    annotations={
        "title": "Write CLAUDE.md for Claude Code Workers",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def cc_write_claude_md(params: ClaudeMdInput) -> str:
    """Create or update a project CLAUDE.md for Claude Code sub-agent behavior.

    The generated document tells Claude Code that Codex is the controller, embeds the
    selected role instruction, and adds safety/progress rules for orchestrated workers.
    Existing CLAUDE.md files are not overwritten unless append=true or force=true.
    """
    try:
        return _json(
            write_claude_md(
                cwd=Path(params.cwd) if params.cwd else None,
                role=params.role,
                project_name=params.project_name,
                append=params.append,
                force=params.force,
            )
        )
    except Exception as exc:
        return _error(exc)


@mcp.tool(
    name="cc_score_models",
    annotations={
        "title": "Score Local CCSwitch Models",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def cc_score_models(params: ListProfilesInput) -> str:
    """Score all Claude models discovered from local CCSwitch provider profiles.

    Scores are local heuristics, not paid benchmark results. JSON output includes
    role_scores for every configured worker role. Secrets are never returned.
    """
    try:
        data = score_models()
        if params.response_format == ResponseFormat.MARKDOWN:
            lines = ["# Local CCSwitch Model Scores", "", f"Roles: {', '.join(ROLE_ORDER)}", ""]
            for item in data["models"]:
                role_scores = json.dumps(item.get("role_scores", {}), ensure_ascii=False)
                lines.append(f"- `{item['model']}` via `{item['profile_name']}`: overall `{item['overall']}/10`; role scores `{role_scores}`")
            return "\n".join(lines)
        return _json(data)
    except Exception as exc:
        return _error(exc)


@mcp.tool(
    name="cc_write_strategy_reports",
    annotations={
        "title": "Write Model Score and Strategy Reports",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def cc_write_strategy_reports(params: ReportInput) -> str:
    """Write model scoring and multi-agent strategy reports under the orchestrator."""
    try:
        data = write_reports(output_dir=Path(params.output_dir) if params.output_dir else None)
        if params.response_format == ResponseFormat.MARKDOWN:
            return "\n".join(
                [
                    "# Strategy Reports Written",
                    "",
                    f"- Scores: `{data['scores_path']}`",
                    f"- Strategy: `{data['strategy_path']}`",
                ]
            )
        return _json(data)
    except Exception as exc:
        return _error(exc)


if __name__ == "__main__":
    mcp.run()
