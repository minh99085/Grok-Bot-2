# Register Windows Scheduled Task to run Grok headless pulse-babysit cycle.
param(
    [int]$IntervalHours = 4,
    [string]$TaskName = "GrokBot2-PulseBabysit",
    [string]$RepoRoot = "C:\Users\tieut\Grok-Bot-2"
)

$ErrorActionPreference = "Stop"
$grok = (Get-Command grok -ErrorAction SilentlyContinue).Source
if (-not $grok) {
    Write-Error "grok CLI not found in PATH. Install Grok CLI or use /loop in TUI instead."
}

$action = New-ScheduledTaskAction -Execute $grok -Argument @(
    "-p", "/pulse-babysit cycle",
    "--yolo",
    "--cwd", $RepoRoot,
    "--max-turns", "45"
) -WorkingDirectory $RepoRoot

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Hours $IntervalHours) -RepetitionDuration ([TimeSpan]::MaxValue)

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Registered '$TaskName' every ${IntervalHours}h using:"
Write-Host "  $grok -p `/pulse-babysit cycle` --yolo --cwd $RepoRoot"
Write-Host "View: taskschd.msc | Remove: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"