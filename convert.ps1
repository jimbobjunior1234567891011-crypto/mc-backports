# One-step converter: drop a resource pack zip on this script, get a converted pack back.
#
#   right-click convert.ps1 -> Run with PowerShell, then paste the path when asked
#   or:  powershell -ExecutionPolicy Bypass -File convert.ps1 -Pack "C:\path\to\pack.zip"
#
# Needs Python 3 and a copy of the target Minecraft version's client jar, which any
# launcher that has run that version already has. The script goes looking for it.

param(
    [string]$Pack,
    [string]$Version = "1.21.1",
    [string]$ClientJar,
    [ValidateSet("mod", "plain")]
    [string]$Mode = "mod",
    [string]$OutDir
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Fail($message) {
    Write-Host ""
    Write-Host "  $message" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to close"
    exit 1
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Fail "Python 3 is not installed, or not on PATH. Get it from python.org, tick 'Add to PATH', then run this again."
}

if (-not $Pack) {
    Write-Host ""
    Write-Host "  Drag the resource pack .zip into this window and press Enter." -ForegroundColor Cyan
    $Pack = (Read-Host "  Pack zip").Trim('"', ' ')
}
if (-not (Test-Path $Pack)) { Fail "Cannot find that file: $Pack" }

# --- find the client jar -----------------------------------------------------------
if (-not $ClientJar) {
    $candidates = @(
        "$env:APPDATA\.minecraft\versions\$Version\$Version.jar",
        "$env:APPDATA\ModrinthApp\meta\versions\$Version\$Version.jar",
        "$env:USERPROFILE\curseforge\minecraft\Install\versions\$Version\$Version.jar"
    )
    $ClientJar = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $ClientJar) {
        $roots = @("$env:APPDATA\.minecraft", "$env:APPDATA\ModrinthApp",
                   "$env:USERPROFILE\curseforge\minecraft", "$env:APPDATA\PrismLauncher") |
                 Where-Object { Test-Path $_ }
        foreach ($searchRoot in $roots) {
            $hit = Get-ChildItem -Path $searchRoot -Recurse -Filter "$Version.jar" -ErrorAction SilentlyContinue |
                   Select-Object -First 1
            if ($hit) { $ClientJar = $hit.FullName; break }
        }
    }
}
if (-not $ClientJar -or -not (Test-Path $ClientJar)) {
    Fail "Could not find a $Version client jar. Launch $Version once in any launcher, or pass -ClientJar <path>."
}

# --- convert -----------------------------------------------------------------------
$name = [IO.Path]::GetFileNameWithoutExtension($Pack)
$work = Join-Path $env:TEMP "mc-backports-$([guid]::NewGuid().ToString('N').Substring(0,8))"
$unpacked = Join-Path $work "in"
$converted = Join-Path $work "out"
if (-not $OutDir) { $OutDir = Split-Path -Parent (Resolve-Path $Pack) }

Write-Host ""
Write-Host "  pack   : $Pack"
Write-Host "  client : $ClientJar"
Write-Host "  mode   : $Mode$(if ($Mode -eq 'mod') { '  (needs the FreeRot mod in your mods folder)' })"
Write-Host ""

New-Item -ItemType Directory -Force $unpacked | Out-Null
Expand-Archive -Path $Pack -DestinationPath $unpacked -Force

# some packs are zipped with everything inside one folder
if (-not (Test-Path (Join-Path $unpacked "pack.mcmeta"))) {
    $inner = Get-ChildItem -Path $unpacked -Directory |
             Where-Object { Test-Path (Join-Path $_.FullName "pack.mcmeta") } |
             Select-Object -First 1
    if ($inner) { $unpacked = $inner.FullName }
    else { Fail "That zip has no pack.mcmeta in it, so it is not a resource pack." }
}

python (Join-Path $root "converter\backport.py") $unpacked $converted $ClientJar $Mode
if ($LASTEXITCODE -ne 0) { Fail "Conversion failed. The output above says why." }

python (Join-Path $root "converter\tests\validate.py") $converted $ClientJar
if ($LASTEXITCODE -ne 0) { Fail "The converted pack did not validate, so it was not saved." }

$out = Join-Path $OutDir "$name-$Version-backport.zip"
if (Test-Path $out) { Remove-Item $out -Force }
Compress-Archive -Path (Join-Path $converted "*") -DestinationPath $out -CompressionLevel Optimal
Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "  Done: $out" -ForegroundColor Green
Write-Host "  Put it in your instance's resourcepacks folder and enable it in Options > Resource Packs."
if ($Mode -eq "mod") {
    Write-Host "  Also put freerot-<version>.jar in the same instance's mods folder, or most items will not draw."
}
Write-Host ""
Read-Host "Press Enter to close"
