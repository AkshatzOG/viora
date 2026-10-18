$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StageStatic = $null
Push-Location $ProjectRoot
try {
  if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
    throw 'Run this script on Windows.'
  }

  python -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10 or later is required'"
  if ($LASTEXITCODE -ne 0) { throw 'Python 3.10 or later is required.' }
  python -m PyInstaller --version *> $null
  if ($LASTEXITCODE -ne 0) { throw 'PyInstaller is missing. Install requirements-build.txt, then rerun this script.' }

  $StageStatic = Join-Path $ProjectRoot ('.build-static-' + [Guid]::NewGuid().ToString('N'))
  Copy-Item -LiteralPath (Join-Path $ProjectRoot 'static') -Destination $StageStatic -Recurse
  $PersonalFont = Join-Path $StageStatic 'fonts\Surgena-Personal-Use.ttf'
  if (Test-Path -LiteralPath $PersonalFont -PathType Leaf) { Remove-Item -LiteralPath $PersonalFont -Force }

  python -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name Viora `
    --add-data 'templates;templates' `
    --add-data "$StageStatic;static" `
    --hidden-import app `
    --hidden-import python_mpv_jsonipc `
    --collect-all yt_dlp `
    launcher.py
  if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed. See the build output above.' }

  $AppDir = Join-Path $ProjectRoot 'dist\Viora'
  $RuntimeDir = Join-Path $AppDir 'runtime'
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

  $MpvSource = $env:MPV_PATH
  if (-not $MpvSource -or -not (Test-Path -LiteralPath $MpvSource -PathType Leaf)) { $MpvSource = 'C:\mpv\mpv.exe' }
  if (-not (Test-Path -LiteralPath $MpvSource -PathType Leaf)) {
    $mpvCommand = Get-Command mpv.exe -ErrorAction SilentlyContinue
    if ($mpvCommand) { $MpvSource = $mpvCommand.Source }
  }
  if (Test-Path -LiteralPath $MpvSource -PathType Leaf) {
    Copy-Item -LiteralPath $MpvSource -Destination (Join-Path $RuntimeDir 'mpv.exe') -Force
    $MpvDirectory = Split-Path -Parent $MpvSource
    Get-ChildItem -LiteralPath $MpvDirectory -Filter '*.dll' -File -ErrorAction SilentlyContinue | ForEach-Object {
      Copy-Item -LiteralPath $_.FullName -Destination $RuntimeDir -Force
    }
    $MpvDocs = Join-Path $MpvDirectory 'doc'
    if (Test-Path -LiteralPath $MpvDocs -PathType Container) { Copy-Item -LiteralPath $MpvDocs -Destination $RuntimeDir -Recurse -Force }
    Write-Host "Bundled MPV from $MpvSource"
  } else { Write-Warning 'MPV was not found. The app will need MPV installed on the target PC.' }

  $YtdlpSource = $env:YTDLP_PATH
  if (-not $YtdlpSource -or -not (Test-Path -LiteralPath $YtdlpSource -PathType Leaf)) { $YtdlpSource = 'C:\mpv\yt-dlp.exe' }
  if (-not (Test-Path -LiteralPath $YtdlpSource -PathType Leaf)) {
    $ytdlpCommand = Get-Command yt-dlp.exe -ErrorAction SilentlyContinue
    if ($ytdlpCommand) { $YtdlpSource = $ytdlpCommand.Source }
  }
  if (Test-Path -LiteralPath $YtdlpSource -PathType Leaf) {
    Copy-Item -LiteralPath $YtdlpSource -Destination (Join-Path $RuntimeDir 'yt-dlp.exe') -Force
    Write-Host "Bundled yt-dlp from $YtdlpSource"
  } else { Write-Warning 'yt-dlp was not found. Online search/download features may not work in the packaged app.' }

  Write-Host "Viora app files: $AppDir"
  Write-Host 'The runtime folder carries MPV/yt-dlp when they are available on the build PC. Keep included third-party license and notice files with redistributed binaries.'
} finally {
  if ($StageStatic) {
    $ResolvedStage = [System.IO.Path]::GetFullPath($StageStatic)
    $ResolvedProject = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if ($ResolvedStage.StartsWith($ResolvedProject, [System.StringComparison]::OrdinalIgnoreCase) -and (Split-Path -Leaf $ResolvedStage).StartsWith('.build-static-')) {
      Remove-Item -LiteralPath $ResolvedStage -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
  Pop-Location
}
