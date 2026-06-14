param(
    [string]$CodexConfig = "",
    [string]$ClaudeConfig = "",
    [string]$ToolHome = "",
    [switch]$SkipCodex,
    [switch]$SkipClaude,
    [switch]$WhatIfOnly
)

$ErrorActionPreference = "Stop"

function Backup-File {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        $backup = "$Path.backup.$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Copy-Item -LiteralPath $Path -Destination $backup -Force
        Write-Host "Backed up: $backup"
    }
}

function ConvertTo-PlainHashtable {
    param($InputObject)
    if ($null -eq $InputObject) {
        return $null
    }
    if ($InputObject -is [System.Collections.IDictionary]) {
        $hash = @{}
        foreach ($key in $InputObject.Keys) {
            $hash[$key] = ConvertTo-PlainHashtable $InputObject[$key]
        }
        return $hash
    }
    if (($InputObject -is [System.Collections.IEnumerable]) -and -not ($InputObject -is [string])) {
        $items = @()
        foreach ($item in $InputObject) {
            $items += ,(ConvertTo-PlainHashtable $item)
        }
        return $items
    }
    if ($InputObject -is [pscustomobject]) {
        $hash = @{}
        foreach ($property in $InputObject.PSObject.Properties) {
            $hash[$property.Name] = ConvertTo-PlainHashtable $property.Value
        }
        return $hash
    }
    return $InputObject
}

function Write-CodexConfig {
    param([string]$Path, [string]$Root)
    $begin = "# claude-code-orchestrator:mcp:begin"
    $end = "# claude-code-orchestrator:mcp:end"
    $escapedRoot = $Root.Replace("\", "\\")
    $block = @"
$begin
[mcp_servers.claude-code-orchestrator]
command = "python"
args = [
  "-c",
  "import os,sys,runpy; root=os.environ.get('CC_ORCHESTRATOR_HOME') or r'$escapedRoot'; sys.path.insert(0, root); runpy.run_path(os.path.join(root, 'server.py'), run_name='__main__')"
]

[mcp_servers.claude-code-orchestrator.env]
CC_ORCHESTRATOR_HOME = "$escapedRoot"
PYTHONIOENCODING = "utf-8"
PYTHONUTF8 = "1"
$end
"@
    $dir = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $content = if (Test-Path -LiteralPath $Path) { Get-Content -Raw -LiteralPath $Path } else { "" }
    $pattern = "(?s)$([regex]::Escape($begin)).*?$([regex]::Escape($end))"
    if ($content -match $pattern) {
        $next = [regex]::Replace($content, $pattern, $block)
    } else {
        $next = ($content.TrimEnd() + "`r`n`r`n" + $block + "`r`n").TrimStart()
    }
    if ($WhatIfOnly) {
        Write-Host "Would write Codex MCP config: $Path"
    } else {
        Backup-File -Path $Path
        Set-Content -LiteralPath $Path -Value $next -Encoding UTF8
        Write-Host "Wrote Codex MCP config: $Path"
    }
}

function Write-ClaudeConfig {
    param([string]$Path, [string]$Root)
    $dir = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $data = @{}
    if (Test-Path -LiteralPath $Path) {
        $raw = Get-Content -Raw -LiteralPath $Path
        if ($raw.Trim()) {
            $data = ConvertTo-PlainHashtable ($raw | ConvertFrom-Json)
        }
    }
    if (-not $data.ContainsKey("mcpServers")) {
        $data["mcpServers"] = @{}
    }
    $data["mcpServers"]["claude-code-orchestrator"] = @{
        command = "python"
        args = @(
            "-c",
            "import os,sys,runpy; root=os.environ.get('CC_ORCHESTRATOR_HOME') or r'$Root'; sys.path.insert(0, root); runpy.run_path(os.path.join(root, 'server.py'), run_name='__main__')"
        )
        env = @{
            CC_ORCHESTRATOR_HOME = $Root
            PYTHONIOENCODING = "utf-8"
            PYTHONUTF8 = "1"
        }
    }
    if ($WhatIfOnly) {
        Write-Host "Would write Claude MCP config: $Path"
    } else {
        Backup-File -Path $Path
        $json = $data | ConvertTo-Json -Depth 20
        Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
        Write-Host "Wrote Claude MCP config: $Path"
    }
}

if (-not $ToolHome) {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $candidate = Join-Path $repoRoot "scripts\cc-orchestrator"
    if (Test-Path -LiteralPath $candidate) {
        $ToolHome = $candidate
    } elseif ($env:CC_ORCHESTRATOR_HOME) {
        $ToolHome = $env:CC_ORCHESTRATOR_HOME
    } else {
        $home = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
        $ToolHome = Join-Path $home "skills\claude-code-orchestrator\scripts\cc-orchestrator"
    }
}

$ToolHome = (Resolve-Path -LiteralPath $ToolHome).Path

if (-not $CodexConfig) {
    $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
    $CodexConfig = Join-Path $codexHome "config.toml"
}

if (-not $ClaudeConfig) {
    $ClaudeConfig = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"
}

if (-not $SkipCodex) {
    Write-CodexConfig -Path $CodexConfig -Root $ToolHome
}

if (-not $SkipClaude) {
    Write-ClaudeConfig -Path $ClaudeConfig -Root $ToolHome
}

Write-Host ""
Write-Host "MCP registration finished."
Write-Host "Tool home: $ToolHome"
Write-Host "Next:"
Write-Host "  python `"$ToolHome\cc_orchestrator.py`" selftest"
Write-Host "  python `"$ToolHome\cc_orchestrator.py`" healthcheck"
