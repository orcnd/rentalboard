$ErrorActionPreference = "Stop"
$startScript = (Resolve-Path (Join-Path $PSScriptRoot "start.ps1")).Path
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$startScript`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "RentalBoardSelfHost" -Action $action -Trigger $trigger -Settings $settings -Description "Start RentalBoard API, frontend and Cloudflare Tunnel after sign-in" -Force | Out-Null
Write-Output "Registered RentalBoardSelfHost for $env:USERDOMAIN\$env:USERNAME at logon."
