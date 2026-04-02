$ErrorActionPreference = "Stop"

$root = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSCommandPath))
if ($root.StartsWith("\\?\")) {
  $root = $root.Substring(4)
}
Set-Location $root

function Import-DotEnv([string]$path) {
  if (-not (Test-Path $path)) { return }
  Write-Host "Loading env from $path"
  Get-Content $path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line) { return }
    if ($line.StartsWith("#")) { return }
    $idx = $line.IndexOf("=")
    if ($idx -lt 1) { return }
    $name = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1).Trim()
    if ($value.StartsWith('"') -and $value.EndsWith('"')) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    if ($name) { [System.Environment]::SetEnvironmentVariable($name, $value, 'Process') }
  }
}

Import-DotEnv (Join-Path $root ".env")

if (-not (Test-Path (Join-Path $root ".venv"))) {
  python -m venv (Join-Path $root ".venv")
}

$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
  throw "Python executable not found at $pythonExe"
}

Write-Host "Installing backend dependencies..."
$env:PYO3_USE_ABI3_FORWARD_COMPATIBILITY = "1"
& $pythonExe -m pip install -U pip
& $pythonExe -m pip install -r (Join-Path $root "requirements.txt")

Write-Host ""
Write-Host "Gateway:  http://127.0.0.1:8010/health"
Write-Host "AI:       http://127.0.0.1:8001/health"
Write-Host "Data:     http://127.0.0.1:8002/health"
Write-Host "Alerts:   http://127.0.0.1:8003/health"
Write-Host "Scheduler http://127.0.0.1:8004/health"
Write-Host ""
Write-Host "Frontend should use VITE_API_BASE=http://127.0.0.1:8010"
Write-Host ""
Write-Host "Starting backend stack as a single local process group..."

& $pythonExe -m services.serve_all
