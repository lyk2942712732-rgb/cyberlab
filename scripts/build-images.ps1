$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    docker build -t cyberlab/kali:local docker/kali
    if ($LASTEXITCODE -ne 0) { throw 'Kali image build failed' }
    docker build -t cyberlab/sqli-basic:v1 docker/targets/sqli-basic
    if ($LASTEXITCODE -ne 0) { throw 'Target image build failed' }
    docker save -o sqli-basic.tar cyberlab/sqli-basic:v1
    if ($LASTEXITCODE -ne 0) { throw 'Target image export failed' }
    Write-Output 'Images built. Upload sqli-basic.tar from the teaching console.'
} finally { Pop-Location }
