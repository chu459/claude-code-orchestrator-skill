param(
    [string]$CodexHome = $env:CODEX_HOME
)

$ErrorActionPreference = "Stop"

if (-not $CodexHome) {
    $CodexHome = Join-Path $env:USERPROFILE ".codex"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$targetRoot = Join-Path $CodexHome "skills"
$target = Join-Path $targetRoot "claude-code-orchestrator"
$backup = "$target.backup.$(Get-Date -Format 'yyyyMMdd-HHmmss')"

New-Item -ItemType Directory -Force -Path $targetRoot | Out-Null

if (Test-Path -LiteralPath $target) {
    Move-Item -LiteralPath $target -Destination $backup
    Write-Host "Backed up existing skill to $backup"
}

New-Item -ItemType Directory -Force -Path $target | Out-Null
robocopy $repoRoot $target /E /XD .git runs reports __pycache__ /XF *.pyc | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "robocopy failed with exit code $LASTEXITCODE"
}
$global:LASTEXITCODE = 0

$toolHome = Join-Path $target "scripts\cc-orchestrator"

Write-Host ""
Write-Host "Claude Code Orchestrator Skill installed."
Write-Host "Skill path: $target"
Write-Host ""
Write-Host "Run:"
Write-Host "  `$env:CC_ORCHESTRATOR_HOME = `"$toolHome`""
Write-Host "  python `"`$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py`" selftest"
Write-Host "  python `"`$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py`" healthcheck"
Write-Host ""
Write-Host "For Codex MCP, add the config from docs/mcp.codex.example.toml to your Codex config.toml."
