param([switch]$DetectOnly)

$ErrorActionPreference = 'Stop'

$projectDir = Split-Path -Parent $PSScriptRoot
$image = Join-Path $projectDir 'src\out\hispark_pegasus\wifiiot_hispark_pegasus\Hi3861_wifiiot_app_allinone.bin'
$hiburn = 'D:\DevEco-Device-Tool\core\tool_hiburn\hiburn\hiburn.jar'
$java = 'D:\DevEco-Device-Tool\core\tool_hiburn\hiburn\jre\bin\java.exe'

if (!(Test-Path -LiteralPath $image)) {
    throw "Firmware image not found. Run the build first: $image"
}

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
    throw 'No active CH340 serial port was found. Check the USB cable and driver.'
}

Write-Host "Using Hi3861 serial port: $port"
if ($DetectOnly) {
    exit 0
}
Write-Host 'When BootromDownloadBoot appears, press RST once.'
& $java `
    -jar $hiburn `
    --burn `
    -n Hi3861 `
    -m serial $port 115200 `
    -b $image `
    -lp 'D:\DevEco-Device-Tool\logs\hiburn' `
    -dt 1500
exit $LASTEXITCODE
