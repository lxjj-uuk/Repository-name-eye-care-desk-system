$ErrorActionPreference = 'Stop'
$ruleName = 'EyeCare API 8080'
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

if (-not $existing) {
    New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort 8080 `
        -Profile Any `
        -RemoteAddress LocalSubnet | Out-Null
}

Get-NetFirewallRule -DisplayName $ruleName |
    Select-Object DisplayName, Enabled, Direction, Action, Profile

$programs = @(
    'E:\Hi3861\eye-care-desk-system\backend\.venv\Scripts\python.exe',
    'E:\Miniconda\python.exe'
)

foreach ($program in $programs) {
    if (-not (Test-Path -LiteralPath $program)) {
        continue
    }
    $programRuleName = "EyeCare Backend - $program"
    if (-not (Get-NetFirewallRule -DisplayName $programRuleName -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule `
            -DisplayName $programRuleName `
            -Direction Inbound `
            -Action Allow `
            -Program $program `
            -Profile Any `
            -RemoteAddress LocalSubnet | Out-Null
    }
}
