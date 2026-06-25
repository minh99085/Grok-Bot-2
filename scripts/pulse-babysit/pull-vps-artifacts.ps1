# Pull pulse artifacts from VPS (docker volume via hermes-training) into vps_full_reports/latest/
param(
    [string]$SshKey = "$env:USERPROFILE\.ssh\bot2_grok_temp",
    [string]$VpsHost = "45.32.224.147",
    [string]$VpsUser = "root",
    [string]$Container = "hermes-training"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Dest = Join-Path $RepoRoot "vps_full_reports\latest"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null

$sshArgs = @("-i", $SshKey, "-o", "ConnectTimeout=20", "-o", "StrictHostKeyChecking=no", "${VpsUser}@${VpsHost}")
$remoteDir = "/data"
$files = @(
    "btc_pulse_status.json",
    "btc_pulse_light_report.json",
    "btc_pulse_ledger.json",
    "btc_pulse_tradingview.json",
    "report.md",
    "report.docx",
    "btc_pulse_score_history.json"
)

foreach ($f in $files) {
    $local = Join-Path $Dest $f
    $remote = "$remoteDir/$f"
    $tmp = "/tmp/pulse-pull-$f"
    ssh @sshArgs "docker cp ${Container}:${remote} $tmp 2>/dev/null || exit 1"
    scp @sshArgs "${VpsUser}@${VpsHost}:$tmp" $local
    ssh @sshArgs "rm -f $tmp" 2>$null | Out-Null
    if (Test-Path $local) { Write-Host "  ok $f" }
}

if (-not (Test-Path (Join-Path $Dest "btc_pulse_status.json"))) {
    Write-Error "Pull failed: btc_pulse_status.json missing"
}
Write-Host "Pulled artifacts -> $Dest"