$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$runtime = Join-Path $repo ".factory/runs"
New-Item -ItemType Directory -Force -Path $runtime | Out-Null

function Test-LocalPort([int]$Port) {
  $client = [System.Net.Sockets.TcpClient]::new()
  try {
    $result = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
    return $result.AsyncWaitHandle.WaitOne(500) -and $client.Connected
  } catch { return $false } finally { $client.Dispose() }
}

function Start-Hidden([string]$File, [string[]]$Arguments, [string]$Name) {
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  Start-Process -FilePath $File -ArgumentList $Arguments -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime "$Name-$stamp.log") -RedirectStandardError (Join-Path $runtime "$Name-$stamp.err.log") | Out-Null
}

$python = Join-Path $repo ".venv/Scripts/python.exe"
if (-not (Test-Path $python)) { throw "Run uv sync first; missing $python" }
if (-not (Test-LocalPort 8010)) {
  $env:PUBLIC_ORIGIN = "https://rentalboard.orcuncandan.com"
  $env:DEMO_ENABLED = "false"
  $env:ENVIRONMENT = "production"
  $env:RELEASE_ID = "rentalboard-0.1.0-selfhost"
  $env:DATABASE_PATH = ".data/rentalboard-hosted.sqlite"
  $env:EVENT_LOG_PATH = ".factory/runs/events.jsonl"
  Start-Hidden $python @("-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "8010", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1") "api"
}
if (-not (Test-LocalPort 4174)) {
  $node = (Get-Command node.exe -ErrorAction Stop).Source
  Start-Hidden $node @((Join-Path $repo "node_modules/vite/bin/vite.js"), "preview") "frontend"
}
$cloudflared = "C:/Program Files (x86)/cloudflared/cloudflared.exe"
$tunnel = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "cloudflared.exe" -and $_.CommandLine -match "355abd67-74db-4c1d-b76a-b2d6f8870113" }
if (-not $tunnel) {
  Start-Hidden $cloudflared @("tunnel", "--config", (Join-Path $PSScriptRoot "config.yml"), "run", "355abd67-74db-4c1d-b76a-b2d6f8870113") "tunnel"
}
Write-Output "RentalBoard startup checked; API :8010, frontend :4174, Cloudflare Tunnel."
