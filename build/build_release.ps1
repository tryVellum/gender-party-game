param(
    [string]$Version = "",
    [switch]$SkipDependencyInstall,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "Сборка установщика поддерживается только на Windows."
}

$VersionMatch = Select-String -Path (Join-Path $Root "version.py") -Pattern 'APP_VERSION\s*=\s*"([^"]+)"'
if (-not $VersionMatch) {
    throw "Не удалось определить версию из version.py."
}
$SourceVersion = $VersionMatch.Matches[0].Groups[1].Value

if (-not $Version) {
    $Version = $SourceVersion
} elseif ($Version -ne $SourceVersion) {
    throw "Версия сборки $Version не совпадает с APP_VERSION=$SourceVersion в version.py."
}

Write-Host "Building Gender Party Game $Version" -ForegroundColor Cyan

if (-not $SkipDependencyInstall) {
    python -m pip install --upgrade pip
    python -m pip install -r requirements-dev.txt
}

$VendorDirectory = Join-Path $Root "static\vendor"
$SocketClientPath = Join-Path $VendorDirectory "socket.io.min.js"
New-Item -ItemType Directory -Path $VendorDirectory -Force | Out-Null

if (-not (Test-Path $SocketClientPath)) {
    Write-Host "Downloading the local Socket.IO browser client..."
    Invoke-WebRequest `
        -UseBasicParsing `
        -Uri "https://cdn.socket.io/4.7.5/socket.io.min.js" `
        -OutFile $SocketClientPath
}

if (-not $SkipTests) {
    python -m ruff format --check app.py config.py database.py init_env.py launcher.py runtime_paths.py version.py build/generate_version_info.py tests
    python -m ruff check app.py config.py database.py init_env.py launcher.py runtime_paths.py version.py build/generate_version_info.py tests
    python -m pytest -q
}

python build/generate_version_info.py `
    --version $Version `
    --output (Join-Path $Root "build\version_info.txt")

$BuildDirectory = Join-Path $Root "build-output"
$DistDirectory = Join-Path $Root "dist"
$ReleaseDirectory = Join-Path $Root "release"

Remove-Item $BuildDirectory -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $DistDirectory -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $ReleaseDirectory -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $ReleaseDirectory -Force | Out-Null

python -m PyInstaller `
    --noconfirm `
    --clean `
    --workpath $BuildDirectory `
    --distpath $DistDirectory `
    (Join-Path $Root "build\GenderPartyGame.spec")

$ApplicationDirectory = Join-Path $DistDirectory "GenderPartyGame"
$ApplicationExe = Join-Path $ApplicationDirectory "GenderPartyGame.exe"
if (-not (Test-Path $ApplicationExe)) {
    throw "PyInstaller did not create GenderPartyGame.exe."
}

if (-not $SkipTests) {
    Write-Host "Running packaged application smoke test..."
    $SmokeData = Join-Path $env:TEMP "GenderPartyGame-Smoke-$([guid]::NewGuid().ToString('N'))"
    $env:GENDER_PARTY_DATA_DIR = $SmokeData
    $env:GENDER_PARTY_NO_BROWSER = "1"
    $env:GENDER_PARTY_NO_TRAY = "1"
    $env:PORT = "51234"

    $SmokeProcess = Start-Process -FilePath $ApplicationExe -PassThru
    try {
        $Ready = $false
        for ($Attempt = 0; $Attempt -lt 60; $Attempt += 1) {
            Start-Sleep -Milliseconds 500
            try {
                $Health = Invoke-RestMethod -Uri "http://127.0.0.1:51234/api/health" -TimeoutSec 1
                if ($Health.app -eq "gender-party-game") {
                    $Ready = $true
                    break
                }
            } catch {
                # The server may still be starting.
            }
        }

        if (-not $Ready) {
            throw "The packaged application did not answer its health endpoint."
        }
    } finally {
        if ($SmokeProcess -and -not $SmokeProcess.HasExited) {
            Stop-Process -Id $SmokeProcess.Id -Force
        }
        Remove-Item Env:GENDER_PARTY_DATA_DIR -ErrorAction SilentlyContinue
        Remove-Item Env:GENDER_PARTY_NO_BROWSER -ErrorAction SilentlyContinue
        Remove-Item Env:GENDER_PARTY_NO_TRAY -ErrorAction SilentlyContinue
        Remove-Item Env:PORT -ErrorAction SilentlyContinue
        Remove-Item $SmokeData -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$PortableDirectory = Join-Path $ReleaseDirectory "GenderPartyGame-Portable-$Version"
Copy-Item $ApplicationDirectory $PortableDirectory -Recurse -Force
New-Item -ItemType File -Path (Join-Path $PortableDirectory "portable.flag") -Force | Out-Null

$PortableArchive = Join-Path $ReleaseDirectory "GenderPartyGame-Portable-$Version.zip"
Compress-Archive -Path $PortableDirectory -DestinationPath $PortableArchive -CompressionLevel Optimal
Remove-Item $PortableDirectory -Recurse -Force

$InnoCandidates = @(
    (Get-Command "ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 7\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }

$InnoCompiler = $InnoCandidates | Select-Object -First 1
if (-not $InnoCompiler) {
    throw "Inno Setup compiler (ISCC.exe) was not found. Install Inno Setup and retry."
}

& $InnoCompiler "/DMyAppVersion=$Version" (Join-Path $Root "build\installer.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed with exit code $LASTEXITCODE."
}

Write-Host "Release files:" -ForegroundColor Green
Get-ChildItem $ReleaseDirectory | Select-Object Name, Length | Format-Table -AutoSize
