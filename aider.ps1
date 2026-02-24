param(
  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$Args
)

& "C:\projects\NEXT-TRADE\.venv_aider\Scripts\aider.exe" @Args
