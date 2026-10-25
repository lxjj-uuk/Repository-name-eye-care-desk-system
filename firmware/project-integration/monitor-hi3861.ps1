param([switch]$DetectOnly)

$ErrorActionPreference = 'Stop'

$ports = @([System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object -Unique)
$port = if ($ports.Count -eq 1) { $ports[0] } else { $null }
if ($null -eq $port) {
    $pnpText = (pnputil /enum-devices /class Ports) -join "`n"
    $matches = [regex]::Matches(
        $pnpText,
        'USB-SERIAL CH340 \((COM\d+)\)[\s\S]*?Status:\s*(Started|Disconnected)'
    )
    foreach ($match in $matches) {
        if ($match.Groups[2].Value -eq 'Started') {
            $port = $match.Groups[1].Value
            break
        }
    }
}
if ($null -eq $port) {
    throw 'No active CH340 serial port was found.'
}

Write-Host "Monitoring Hi3861 serial port: $port"
if ($DetectOnly) {
    exit 0
}
& 'D:\DevEco-Device-Tool\core\deveco-venv\Scripts\python.exe' `
    'D:\DevEco-Device-Tool\monitor.py' $port 115200
exit $LASTEXITCODE
