# Exit 0 if origin/main == VPS HEAD; exit 1 if diverged.
& "$PSScriptRoot\sync-vps-robinhood.ps1" -VerifyOnly
exit $LASTEXITCODE
