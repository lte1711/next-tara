# S4-A checkpoint reminder helper
# Emits reminders at T+2h, T+8h, T+16h from a given start time
# Usage: .\tools\s4a_checkpoint_scheduler.ps1 -StartKst "2026-02-24 15:41:18"

param(
    [Parameter(Mandatory = $true)]
    [string]$StartKst
)

$ErrorActionPreference = "Stop"

$startTime = [DateTime]::ParseExact($StartKst, "yyyy-MM-dd HH:mm:ss", $null)
$now = [DateTime]::Now

function Wait-Until([DateTime]$targetTime, [string]$label) {
    $nowLocal = [DateTime]::Now
    if ($nowLocal -ge $targetTime) {
        Write-Host ("[S4-A REMINDER] {0} is due now (target: {1})" -f $label, $targetTime.ToString("yyyy-MM-dd HH:mm:ss"))
        return
    }
    $seconds = [int]($targetTime - $nowLocal).TotalSeconds
    Write-Host ("[S4-A REMINDER] Waiting for {0} ({1} seconds)..." -f $label, $seconds)
    Start-Sleep -Seconds $seconds
    Write-Host ("[S4-A REMINDER] {0} is due now (target: {1})" -f $label, $targetTime.ToString("yyyy-MM-dd HH:mm:ss"))
}

$checkpoint2h = $startTime.AddHours(2)
$checkpoint8h = $startTime.AddHours(8)
$checkpoint16h = $startTime.AddHours(16)

Wait-Until -targetTime $checkpoint2h -label "T+2h RESTART"
Wait-Until -targetTime $checkpoint8h -label "T+8h NETWORK CUT"
Wait-Until -targetTime $checkpoint16h -label "T+16h KILL SWITCH"

Write-Host "[S4-A REMINDER] All scheduled checkpoints completed."
