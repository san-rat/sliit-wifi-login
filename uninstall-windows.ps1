# Uninstall the SLIIT WiFi auto-login task on Windows.
# Run as Administrator.

$TaskName = "SLIIT-WiFi-Login"
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Task '$TaskName' removed." -ForegroundColor Green
} else {
    Write-Host "Task not found — nothing to remove."
}

Write-Host "You can delete this folder to fully remove."
