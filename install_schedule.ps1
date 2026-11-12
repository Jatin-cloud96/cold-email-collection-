# PowerShell script to register Windows Task Scheduler job
$TaskName = "IndiaEmailLeadFinderDaily"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatPath = Join-Path $ScriptDir "schedule_daily.bat"

Write-Host "Registering Windows Scheduled Task: $TaskName"
Write-Host "Target script: $BatPath"

$Action = New-ScheduledTaskAction -Execute $BatPath -WorkingDirectory $ScriptDir
# Trigger: Every day at 09:00 AM
$Trigger = New-ScheduledTaskTrigger -Daily -At "09:00AM"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Daily automated run of India Professional Email Lead Finder" -Force

Write-Host "`n[Success] Task registered successfully! It will run daily at 9:00 AM."
Write-Host "You can view or run it in Windows Task Scheduler (taskschd.msc)."

