$ErrorActionPreference = "Stop"
powershell -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "C:\projects\NEXT-TRADE\ops_scripts\ops_checkpoint_sync.ps1"
powershell -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "C:\projects\NEXT-TRADE\tools\ops\pmx_003r\watchdog_2m.ps1"
