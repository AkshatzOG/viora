param(
  [string]$OutputPath = (Join-Path $PSScriptRoot 'release\Viora-v15.8.4-source.zip')
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$OutputDir = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$StageRoot = Join-Path $OutputDir ('.viora-stage-' + [Guid]::NewGuid().ToString('N'))
$StageApp = Join-Path $StageRoot 'Viora'
New-Item -ItemType Directory -Force -Path $StageApp | Out-Null

try {
  $RootFiles = @(
    '.env.example', '.gitignore', 'README.md', 'LICENSE', 'ROADMAP.md', 'RELEASE_NOTES.md', 'SECURITY.md',
    'VERSION', 'app.py', 'build_windows.ps1', 'check_install.py', 'close_agent.bat', 'config.py',
    'launcher.py', 'package_release.ps1', 'requirements-build.txt', 'requirements.txt',
    'START_VIORA.bat', 'START_VIORA.vbs', 'STOP_VIORA.vbs'
  )
  foreach ($name in $RootFiles) {
    $source = Join-Path $ProjectRoot $name
    if (Test-Path -LiteralPath $source -PathType Leaf) { Copy-Item -LiteralPath $source -Destination $StageApp -Force }
  }

  foreach ($folder in @('agent', 'core', 'static', 'templates', 'tools', 'tests', 'docs')) {
    $sourceRoot = Join-Path $ProjectRoot $folder
    if (-not (Test-Path -LiteralPath $sourceRoot -PathType Container)) { continue }
    Get-ChildItem -LiteralPath $sourceRoot -Recurse -File | ForEach-Object {
      $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart([System.IO.Path]::DirectorySeparatorChar)
      if ($relative -match '(^|\\)(__pycache__|venv|\.git|cache|logs)(\\|$)') { return }
      if ($relative -match '\.(db|sqlite|sqlite3|pyc|log)$') { return }
      if ($relative -match '(^|\\)Surgena-Personal-Use\.ttf$') { return }
      $destination = Join-Path (Join-Path $StageApp $folder) $relative
      New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
      Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
    }
  }

  if (Test-Path -LiteralPath $OutputPath) { Remove-Item -LiteralPath $OutputPath -Force }
  Compress-Archive -Path $StageApp -DestinationPath $OutputPath -CompressionLevel Optimal

  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $archive = [System.IO.Compression.ZipFile]::OpenRead($OutputPath)
  try {
    $unsafe = @($archive.Entries | Where-Object { $_.FullName -match '(^|/)(\.env|venv|\.git|data|downloads|__pycache__)(/|$)|\.(db|sqlite|sqlite3|pyc)$|Surgena-Personal-Use\.ttf$' })
    if ($unsafe.Count) { throw ('Release archive contains excluded runtime files: ' + ($unsafe.FullName -join ', ')) }
  } finally { $archive.Dispose() }
  Write-Host "Created clean source archive: $OutputPath"
} finally {
  $ResolvedStage = [System.IO.Path]::GetFullPath($StageRoot)
  $ResolvedOutput = [System.IO.Path]::GetFullPath($OutputDir).TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
  if ($ResolvedStage.StartsWith($ResolvedOutput, [System.StringComparison]::OrdinalIgnoreCase) -and (Split-Path -Leaf $ResolvedStage).StartsWith('.viora-stage-')) {
    Remove-Item -LiteralPath $ResolvedStage -Recurse -Force -ErrorAction SilentlyContinue
  }
}
