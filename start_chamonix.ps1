Param()

# start_chamonix.ps1
# Wrapper to start the FastAPI uvicorn server from the project venv.

$Project = 'C:\Users\Administrator\Desktop\Phase1-testing\chamonix_ski_pass_automation'
Set-Location $Project

# Ensure logs directory exists
$logs = Join-Path $Project 'logs'
if (-Not (Test-Path $logs)) { New-Item -Path $logs -ItemType Directory | Out-Null }

# Per-process environment variables (edit if needed)
$env:DEV_WEBHOOK_ENABLED = '0'

$python = Join-Path $Project '.venv\Scripts\python.exe'
$logOut = Join-Path $logs 'service_out.log'
$logErr = Join-Path $logs 'service_err.log'

Write-Output "Starting FastAPI using: $python"
Write-Output "Logs: $logOut , $logErr"

try {
    & $python -m uvicorn fastAPI:app --host 127.0.0.1 --port 5000 *> $logOut 2> $logErr
} catch {
    Write-Error "Failed to start uvicorn: $_"
    exit 1
}
