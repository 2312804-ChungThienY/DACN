<#
.SYNOPSIS
  Đo thời gian tải trang Dashboard (SPEC 6.2) trên bản build production:
  build Vite -> chạy API (uvicorn) -> chạy vite preview -> đo bằng Playwright -> dọn tiến trình.

.EXAMPLE
  $env:LMS_DEMO_PASSWORD = "<mật khẩu demo>"
  .\perf\run_frontend_perf.ps1
#>
param(
    [int]$ApiPort = 8021,
    [int]$WebPort = 4174,
    [int]$Runs = 5,
    [string]$Database = "lms_analytics"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not $env:LMS_DEMO_PASSWORD) { throw "Cần đặt LMS_DEMO_PASSWORD" }

function Stop-Port([int]$TcpPort) {
    for ($i = 0; $i -lt 30; $i++) {
        $listeners = Get-NetTCPConnection -LocalPort $TcpPort -State Listen -ErrorAction SilentlyContinue
        if (-not $listeners) { return }
        $listeners | ForEach-Object { & taskkill /PID $_.OwningProcess /T /F 2>&1 | Out-Null }
        Start-Sleep -Milliseconds 700
    }
    throw "Không giải phóng được cổng $TcpPort"
}

Write-Host "==> Build frontend" -ForegroundColor Cyan
Push-Location "$Root\frontend"
try { & npm run build | Select-Object -Last 3 } finally { Pop-Location }

Stop-Port $ApiPort
Stop-Port $WebPort

$previous = $env:ANALYTICS_DB_NAME
$env:ANALYTICS_DB_NAME = $Database
$api = Start-Process python -PassThru -WindowStyle Hidden -ArgumentList `
    "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "$ApiPort", "--workers", "2", "--timeout-keep-alive", "65"
$env:ANALYTICS_DB_NAME = $previous

$env:VITE_API_TARGET = "http://127.0.0.1:$ApiPort"
# npm/npx là file .cmd nên phải chạy qua cmd.exe, không gọi trực tiếp bằng Start-Process
$web = Start-Process cmd.exe -PassThru -WindowStyle Hidden -WorkingDirectory "$Root\frontend" `
    -ArgumentList "/c", "npx vite preview --port $WebPort --strictPort --host 127.0.0.1"

try {
    $ready = $false
    for ($i = 0; $i -lt 90 -and -not $ready; $i++) {
        try {
            Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$ApiPort/api/v1/health" | Out-Null
            Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$WebPort/" | Out-Null
            $ready = $true
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw "API hoặc web không khởi động được" }

    Write-Host "==> Đo tải trang ($Runs lần mỗi trang, cache lạnh)" -ForegroundColor Cyan
    $env:PERF_BASE_URL = "http://127.0.0.1:$WebPort"
    $env:PERF_RUNS = "$Runs"
    Push-Location "$Root\frontend"
    try { & node e2e/perf.mjs } finally { Pop-Location }
} finally {
    & taskkill /PID $api.Id /T /F 2>&1 | Out-Null
    & taskkill /PID $web.Id /T /F 2>&1 | Out-Null
    Stop-Port $ApiPort
    Stop-Port $WebPort
}
