# Copy the front-end sources into the backend so that one Render service can
# serve both the API and the pages (same origin, no CORS).
#
# Usage (from the repository root):
#   pwsh -File deploy/sync-frontend.ps1
#
# Adjust the source path when the two repositories are not siblings.

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $repoRoot 'src\web'
$candidates = @(
    (Join-Path (Split-Path -Parent $repoRoot) '832402226_calculator_frontend\src'),
    (Join-Path $repoRoot '..\832402226_calculator_frontend\src')
)
$source = $candidates | Where-Object { Test-Path (Join-Path $_ 'calculator.html') } | Select-Object -First 1

if (-not $source) {
    Write-Error "Front-end sources not found. Checked: $($candidates -join ', ')"
}

if (Test-Path $target) { Remove-Item $target -Recurse -Force }
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item (Join-Path $source '*') $target -Recurse -Force

$count = (Get-ChildItem $target -Recurse -File).Count
Write-Host "Front-end copied into $target ($count files)."
Write-Host 'Remember to commit src/web before deploying.'