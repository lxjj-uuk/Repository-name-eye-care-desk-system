param(
    [switch]$Restart
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $projectRoot 'backend'
$python = Join-Path $backendDir '.venv\Scripts\python.exe'
$pidFile = Join-Path $backendDir '.server.pid'
$stdoutLog = Join-Path $backendDir 'uvicorn.stdout.log'
$stderrLog = Join-Path $backendDir 'uvicorn.stderr.log'
$healthUrl = 'http://127.0.0.1:8080/health'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Backend Python environment not found: $python"
}

function Get-PortListenerPid([int]$port) {
    $line = netstat -ano -p TCP |
        Where-Object { $_ -match "[:.]$port\s+.*LISTENING\s+(\d+)\s*$" } |
        Select-Object -First 1
    if ($line -and $line -match "LISTENING\s+(\d+)\s*$") {
        return [int]$Matches[1]
    }
    return $null
}

function Stop-OwnedServer {
    if (-not (Test-Path -LiteralPath $pidFile)) {
        return
    }
    $serverPid = [int](Get-Content -LiteralPath $pidFile -Raw)
    $process = Get-Process -Id $serverPid -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $serverPid -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

if ($Restart) {
    Stop-OwnedServer
}

$healthy = $false
try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 2
    $healthy = $response.StatusCode -eq 200
} catch {
}

if (-not $healthy) {
    $process = Start-Process `
        -FilePath $python `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8080') `
        -WorkingDirectory $backendDir `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ascii

    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                $healthy = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
}

if (-not $healthy) {
    throw "Backend failed to start. Check $stderrLog"
}

$listenerPid = Get-PortListenerPid 8080
if ($listenerPid) {
    $listener = Get-Process -Id $listenerPid -ErrorAction SilentlyContinue
    if ($listener -and $listener.ProcessName -match '^python') {
        Set-Content -LiteralPath $pidFile -Value $listenerPid -Encoding ascii
    }
}

$lanIp = '127.0.0.1'
foreach ($adapter in [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces()) {
    if ($adapter.OperationalStatus -ne 'Up' -or
        $adapter.NetworkInterfaceType -eq 'Loopback' -or
        $adapter.NetworkInterfaceType -eq 'Tunnel') {
        continue
    }
    $properties = $adapter.GetIPProperties()
    $addresses = $properties.UnicastAddresses |
        Where-Object { $_.Address.AddressFamily -eq 'InterNetwork' } |
        Select-Object
    $hotspotAddress = $addresses |
        Where-Object { $_.Address.IPAddressToString -eq '192.168.137.1' } |
        Select-Object -First 1
    if ($hotspotAddress) {
        $lanIp = '192.168.137.1'
        break
    }
    $hasGateway = $properties.GatewayAddresses |
        Where-Object { $_.Address.AddressFamily -eq 'InterNetwork' } |
        Select-Object -First 1
    if (-not $hasGateway) {
        continue
    }
    $address = $addresses |
        Where-Object { $_.Address.AddressFamily -eq 'InterNetwork' } |
        Select-Object -First 1
    if ($address) {
        $lanIp = $address.Address.IPAddressToString
        break
    }
}

if ($lanIp -eq '127.0.0.1') {
    foreach ($adapter in [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces()) {
        if ($adapter.OperationalStatus -ne 'Up' -or
            $adapter.NetworkInterfaceType -eq 'Loopback' -or
            $adapter.NetworkInterfaceType -eq 'Tunnel') {
            continue
        }
        $address = $adapter.GetIPProperties().UnicastAddresses |
            Where-Object { $_.Address.AddressFamily -eq 'InterNetwork' } |
            Select-Object -First 1
        if ($address) {
            $lanIp = $address.Address.IPAddressToString
            break
        }
    }
}

$localHeader = Join-Path $projectRoot 'gateway\esp32\include\cloud_config.local'
$desired = @(
    "#define EYE_CARE_CLOUD_URL `"http://${lanIp}:8080`""
    '#define EYE_CARE_DEFAULT_DEVICE_ID "hi3861_001"'
    '#define EYE_CARE_DEFAULT_UPLOAD_TOKEN "dev-token-change-me"'
) -join "`r`n"
$current = if (Test-Path -LiteralPath $localHeader) {
    (Get-Content -LiteralPath $localHeader -Raw).TrimEnd()
} else {
    ''
}
if ($current -ne $desired.TrimEnd()) {
    Set-Content -LiteralPath $localHeader -Value $desired -Encoding utf8
    Write-Host 'ESP32 local endpoint updated. Rebuild and flash gateway/esp32.' -ForegroundColor Yellow
}

Write-Host ''
Write-Host 'Eye Care local stack is running.' -ForegroundColor Green
Write-Host "API:       http://127.0.0.1:8080"
Write-Host "Docs:      http://127.0.0.1:8080/docs"
Write-Host "LAN:       http://${lanIp}:8080"
Write-Host "ESP32:     http://${lanIp}:8080"
Write-Host 'Emulator:  http://10.0.2.2:8080'
$localModel = Join-Path $projectRoot 'models\qwen2.5-1.5b-instruct-q4_k_m.gguf'
if (
    (Test-Path -LiteralPath $localModel) -and
    ((Get-Item -LiteralPath $localModel).Length -gt 500MB)
) {
    Write-Host 'AI:        Local Qwen2.5 1.5B'
} else {
    Write-Host 'AI:        Rule fallback (local model not installed)' -ForegroundColor Yellow
}
Write-Host ''
