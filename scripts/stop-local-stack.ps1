$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
$pidFile = Join-Path $projectRoot 'backend\.server.pid'

if (-not (Test-Path -LiteralPath $pidFile)) {
    $line = netstat -ano -p TCP |
        Where-Object { $_ -match '[:.]8080\s+.*LISTENING\s+(\d+)\s*$' } |
        Select-Object -First 1
    if ($line -and $line -match 'LISTENING\s+(\d+)\s*$') {
        $listenerPid = [int]$Matches[1]
        $listener = Get-Process -Id $listenerPid -ErrorAction SilentlyContinue
        if ($listener -and $listener.ProcessName -match '^python') {
            Set-Content -LiteralPath $pidFile -Value $listenerPid -Encoding ascii
        }
    }
}

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host 'Eye Care local backend process not found.'
    exit 0
}

$serverPid = [int](Get-Content -LiteralPath $pidFile -Raw)
$process = Get-Process -Id $serverPid -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $serverPid -Force
    Write-Host 'Eye Care local backend stopped.' -ForegroundColor Green
} else {
    Write-Host 'Recorded backend process is no longer running.'
}
Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
