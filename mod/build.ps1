# Builds freerot-<version>.jar without Gradle.
#
# NeoForge 21.1.x runs on Mojang mappings, and a CurseForge/NeoForge install already has
# every jar needed to compile against: the patched client, the universal jar, the
# Mojmap Minecraft jar and the full library set. So javac + jar is enough.

param(
    [string]$Install = "$env:USERPROFILE\curseforge\minecraft\Install",
    [string]$NeoForgeVersion = "21.1.221",
    [string]$McLibVersion = "1.21.1-20240808.144430",
    [string]$Jdk = "C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot",
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $root "build"
$dist = Join-Path (Split-Path -Parent $root) "dist"

$libraries = Join-Path $Install "libraries"
$neoDir = Join-Path $libraries "net\neoforged\neoforge\$NeoForgeVersion"
$mcDir = Join-Path $libraries "net\minecraft\client\$McLibVersion"

foreach ($needed in @(
    (Join-Path $neoDir "neoforge-$NeoForgeVersion-client.jar"),
    (Join-Path $neoDir "neoforge-$NeoForgeVersion-universal.jar"),
    (Join-Path $mcDir "client-$McLibVersion-srg.jar"))) {
    if (-not (Test-Path $needed)) { throw "missing $needed" }
}

$classpath = @(
    (Join-Path $neoDir "neoforge-$NeoForgeVersion-client.jar"),
    (Join-Path $neoDir "neoforge-$NeoForgeVersion-universal.jar"),
    (Join-Path $mcDir "client-$McLibVersion-srg.jar")
)
$classpath += (Get-ChildItem -Path $libraries -Recurse -Filter *.jar |
    Where-Object { $_.FullName -notlike "*neoforge-$NeoForgeVersion*" -and $_.Name -notlike "client-$McLibVersion*" } |
    ForEach-Object { $_.FullName })

if (Test-Path $build) { Remove-Item -Recurse -Force $build }
New-Item -ItemType Directory -Force $build | Out-Null
if (-not (Test-Path $dist)) { New-Item -ItemType Directory -Force $dist | Out-Null }

$sources = Get-ChildItem -Path (Join-Path $root "src") -Recurse -Filter *.java | ForEach-Object { $_.FullName }
& "$Jdk\bin\javac.exe" -nowarn -d $build -cp ($classpath -join ";") $sources
if ($LASTEXITCODE -ne 0) { throw "compile failed" }

Copy-Item -Recurse -Force (Join-Path $root "res\*") $build
& "$Jdk\bin\jar.exe" --create --file (Join-Path $dist "freerot-$Version.jar") -C $build .
if ($LASTEXITCODE -ne 0) { throw "jar failed" }

Write-Output "built $dist\freerot-$Version.jar"
