$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$targetPath = Join-Path $projectRoot "run_app.bat"
$shortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "CGC Arbitrage Scanner.lnk"

if (-not (Test-Path $targetPath)) {
    throw "Launcher not found: $targetPath"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = "Launch CGC Slab Arbitrage Scanner"
$shortcut.Save()

Write-Host "Created shortcut: $shortcutPath"
