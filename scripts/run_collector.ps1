# Runs the collector for all active projects. Meant to be triggered by
# Windows Task Scheduler a few times a day. Safe to run anytime — read-only
# against source repos, cheap, no LLM involved.

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$LogDir = Join-Path $ProjectRoot "data\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "collector.log"

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$timestamp] Starting collection..." | Out-File -Append -Encoding utf8 $LogFile

try {
    # Capture as PowerShell objects first, then write with Out-File -Encoding —
    # piping a native command straight into *>> garbles UTF-8 output (PS 5.1
    # redirect encoding mismatch), this two-step avoids it.
    $output = python -m collector.collect 2>&1
    $output | Out-File -Append -Encoding utf8 $LogFile
    "[$timestamp] Collection finished OK." | Out-File -Append -Encoding utf8 $LogFile
} catch {
    "[$timestamp] Collection FAILED: $_" | Out-File -Append -Encoding utf8 $LogFile
    exit 1
}
