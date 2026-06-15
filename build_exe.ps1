$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$PyInstaller = Join-Path $Root ".venv\Scripts\pyinstaller.exe"

if (-not (Test-Path $Python)) {
    throw "Python virtual environment was not found: $Python"
}

if (-not (Test-Path $PyInstaller)) {
    & $Python -m pip install pyinstaller
}

Push-Location $Root
try {
    foreach ($path in @("build", "dist")) {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    }

    & $PyInstaller `
        --noconfirm `
        --onedir `
        --noupx `
        --name "MatchPredict" `
        --add-data "templates;templates" `
        --add-data "static;static" `
        --add-data "data;data" `
        --add-data "scripts;scripts" `
        --exclude-module "tests" `
        --exclude-module "setuptools" `
        --exclude-module "_distutils_hack" `
        "launcher.py"

    Get-ChildItem -LiteralPath "dist\MatchPredict" -Recurse -Directory -Filter "__pycache__" |
        Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath "dist\MatchPredict" -Recurse -File |
        Where-Object { $_.Extension -in @(".pyc", ".pyo") } |
        Remove-Item -Force

    $ReadmeName = (-join ([char[]](0x4F7F, 0x7528, 0x8BF4, 0x660E))) + ".txt"
    Copy-Item -Force -LiteralPath (Join-Path $Root $ReadmeName) -Destination (Join-Path "dist\MatchPredict" $ReadmeName)

    $ZipName = "MatchPredict-" + (-join ([char[]](0x7EFF, 0x8272, 0x7248))) + ".zip"
    $zipPath = Join-Path $Root (Join-Path "dist" $ZipName)
    if (Test-Path $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path "dist\MatchPredict\*" -DestinationPath $zipPath

    Write-Host "Build finished: $zipPath"
}
finally {
    Pop-Location
}
