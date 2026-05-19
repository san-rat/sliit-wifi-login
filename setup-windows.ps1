# Setup script for Windows — creates a Task Scheduler task that runs
# sliit-login.py at logon and every 30 minutes.
# Run this script as Administrator (right-click PowerShell > Run as Admin).

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptPath = Join-Path $ScriptDir "sliit-login.py"
$CredsPath = Join-Path $ScriptDir "credentials.json"
$TaskName = "SLIIT-WiFi-Login"

# Find python
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) {
    $Python = (Get-Command python3 -ErrorAction SilentlyContinue).Source
}
if (-not $Python) {
    Write-Host "Error: Python not found. Install it from https://python.org" -ForegroundColor Red
    Write-Host "Make sure to check 'Add Python to PATH' during installation."
    exit 1
}

Write-Host "Python: $Python"
Write-Host "Script: $ScriptPath"

# Check credentials
if (-not (Test-Path $CredsPath)) {
    Write-Host ""
    Write-Host "No credentials.json found." -ForegroundColor Yellow
    Write-Host "Copy credentials.example.json to credentials.json and fill in your username/password:"
    Write-Host "  copy credentials.example.json credentials.json"
    Write-Host "  notepad credentials.json"
    exit 1
}

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task."
}

# Create the task
$Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$ScriptPath`"" -WorkingDirectory $ScriptDir

# Trigger 1: At logon
$TriggerLogon = New-ScheduledTaskTrigger -AtLogon

# Trigger 2: Every 30 minutes (repeating), starting now
$TriggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 30)

# Also trigger on network connect via event log
# (Event ID 10000 = NetworkProfile connected)
$CIMTriggerClass = Get-CimClass -ClassName MSFT_TaskEventTrigger `
    -Namespace Root/Microsoft/Windows/TaskScheduler
$TriggerNetwork = New-CimInstance -CimClass $CIMTriggerClass -ClientOnly
$TriggerNetwork.Enabled = $true
$TriggerNetwork.Subscription = @"
<QueryList>
  <Query Id="0" Path="Microsoft-Windows-NetworkProfile/Operational">
    <Select Path="Microsoft-Windows-NetworkProfile/Operational">*[System[EventID=10000]]</Select>
  </Query>
</QueryList>
"@

$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName `
    -Action $Action `
    -Trigger @($TriggerLogon, $TriggerRepeat, $TriggerNetwork) `
    -Settings $Settings `
    -Description "Auto-login to SLIIT FortiGate captive portal" `
    -RunLevel Limited | Out-Null

Write-Host ""
Write-Host "Done! Task '$TaskName' is now registered." -ForegroundColor Green
Write-Host "It will auto-login whenever you connect to SLIIT WiFi."
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  Check logs:    type $ScriptDir\sliit-login.log"
Write-Host "  Manual run:    python $ScriptPath"
Write-Host "  Uninstall:     Unregister-ScheduledTask -TaskName '$TaskName'"
