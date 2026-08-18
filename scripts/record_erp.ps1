$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot ".env"
$playwrightPath = Join-Path $projectRoot ".venv\Scripts\playwright.exe"
$recordingPath = Join-Path $projectRoot "rpa_recording.py"

if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Arquivo .env não encontrado em $projectRoot"
}

if (-not (Test-Path -LiteralPath $playwrightPath)) {
    throw "Playwright não encontrado. Prepare o ambiente virtual primeiro."
}

$erpLine = Get-Content -LiteralPath $envPath |
    Where-Object { $_ -match '^\s*ERP_URL\s*=' } |
    Select-Object -Last 1

if (-not $erpLine) {
    throw "ERP_URL não foi definido no .env"
}

$erpUrl = ($erpLine -split '=', 2)[1].Trim().Trim('"').Trim("'")
if (-not $erpUrl) {
    throw "ERP_URL está vazio no .env"
}

Write-Host "Abrindo o gravador em $erpUrl"
Write-Host "Ao terminar o fluxo, feche o navegador e o Playwright Inspector."

& $playwrightPath codegen `
    --target=python `
    --ignore-https-errors `
    --output $recordingPath `
    $erpUrl

Write-Host "Gravação salva em $recordingPath"

