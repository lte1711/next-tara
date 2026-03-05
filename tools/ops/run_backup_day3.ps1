$ErrorActionPreference = "Stop"
. "C:\projects\NEXT-TRADE\tools\ops\nexttrade_backup.ps1"
Invoke-NextTradeBackup -Stage PH7C_DAY3 | Out-String | Write-Output

