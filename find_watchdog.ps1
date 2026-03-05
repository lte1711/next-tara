Get-CimInstance Win32_Process | ForEach-Object {
    $cl = $_.CommandLine
    if ($cl -and ($cl -match 'watchdog|supervisor|run_services|start_all|launch_all|nssm|pm2')) {
        [PSCustomObject]@{ PID=$_.ProcessId; Name=$_.Name; CMD=$cl }
    }
} | Format-List
