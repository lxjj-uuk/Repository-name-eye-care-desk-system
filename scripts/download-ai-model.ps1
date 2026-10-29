param(
    [string]$Destination = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Destination) {
    $Destination = Join-Path $projectRoot 'models\qwen2.5-1.5b-instruct-q4_k_m.gguf'
}

$url = (
    'https://modelscope.cn/models/Qwen/Qwen2.5-1.5B-Instruct-GGUF/' +
    'resolve/master/qwen2.5-1.5b-instruct-q4_k_m.gguf'
)
$expectedBytes = 1117320736
$expectedSha256 = '6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e'

New-Item -ItemType Directory -Force (Split-Path $Destination -Parent) | Out-Null
if (Test-Path -LiteralPath $Destination) {
    $existing = (Get-Item -LiteralPath $Destination).Length
    if ($existing -eq $expectedBytes) {
        $hash = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLower()
        if ($hash -eq $expectedSha256) {
            Write-Host 'AI model is already downloaded and verified.' -ForegroundColor Green
            exit 0
        }
        throw "Existing model file has an unexpected SHA256: $hash"
    }
}

& curl.exe -L --fail --retry 3 -C - --output $Destination $url
if ($LASTEXITCODE -ne 0) {
    throw "Model download failed with curl exit code $LASTEXITCODE"
}

$length = (Get-Item -LiteralPath $Destination).Length
if ($length -ne $expectedBytes) {
    throw "Model size mismatch: expected $expectedBytes bytes, got $length"
}
$actualSha256 = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLower()
if ($actualSha256 -ne $expectedSha256) {
    throw "Model SHA256 mismatch: $actualSha256"
}
Write-Host 'AI model downloaded and verified.' -ForegroundColor Green
