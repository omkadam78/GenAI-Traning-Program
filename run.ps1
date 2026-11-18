# PowerShell launcher for FasalBima Sathi
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
$python = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
& $python run.py $args
