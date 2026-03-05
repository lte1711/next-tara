$target = Get-CimInstance Win32_Process -Filter "ProcessId=9664"
if (-not $target) { "PID 9664 not found"; exit }
"=== TARGET ==="; $target | Select-Object ProcessId, Name, CommandLine | Format-List

$parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($target.ParentProcessId)"
"=== PARENT PID=$($target.ParentProcessId) ==="; $parent | Select-Object ProcessId, Name, CommandLine | Format-List

if ($parent) {
    $gp = Get-CimInstance Win32_Process -Filter "ProcessId=$($parent.ParentProcessId)"
    "=== GRANDPARENT PID=$($parent.ParentProcessId) ==="; $gp | Select-Object ProcessId, Name, CommandLine | Format-List
}
