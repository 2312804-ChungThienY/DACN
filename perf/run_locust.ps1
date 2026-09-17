<#
.SYNOPSIS
  Chạy kiểm thử tải Locust (SPEC 6.2) lần lượt trên bộ dữ liệu x1 và x10.
  Mỗi lượt tự khởi động API riêng (uvicorn 2 worker) trỏ vào CSDL tương ứng, chạy xong thì tắt.

.EXAMPLE
  $env:LMS_DEMO_PASSWORD = "<mật khẩu demo>"
  .\perf\run_locust.ps1 -Minutes 10
#>
param(
    [int]$Users = 50,
    [int]$SpawnRate = 5,
    [int]$Minutes = 10,
    [int]$MinutesX1 = 5,
    [int]$Port = 8010
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not $env:LMS_DEMO_PASSWORD) { throw "Cần đặt LMS_DEMO_PASSWORD" }
New-Item -ItemType Directory -Force "$Root\perf\results" | Out-Null

function Get-Teachers([string]$Database) {
    $script = @"
import sys; sys.path.insert(0, r'$Root')
import psycopg
from database.config import load_db_config
with psycopg.connect(**load_db_config('ANALYTICS_DB').conninfo(dbname='$Database')) as c:
    print(','.join(r[0] for r in c.execute("SELECT username FROM analytics.app_user WHERE role='TEACHER' AND is_active ORDER BY user_id")))
"@
    $file = Join-Path $env:TEMP "locust_teachers.py"
    Set-Content -Path $file -Value $script -Encoding UTF8
    return (python $file).Trim()
}

function Stop-Port([int]$TcpPort) {
    # uvicorn --workers sinh tiến trình con: dừng cả cây tiến trình (taskkill /T), nếu không cổng vẫn bị giữ
    for ($i = 0; $i -lt 30; $i++) {
        $listeners = Get-NetTCPConnection -LocalPort $TcpPort -State Listen -ErrorAction SilentlyContinue
        if (-not $listeners) { return }
        $listeners | ForEach-Object { & taskkill /PID $_.OwningProcess /T /F 2>&1 | Out-Null }
        Start-Sleep -Milliseconds 700
    }
    throw "Không giải phóng được cổng $TcpPort"
}

function Invoke-Run([string]$Label, [string]$Database, [int]$RunMinutes) {
    Write-Host "==> Locust $Label ($Database, $RunMinutes phút, $Users người dùng)" -ForegroundColor Cyan
    Stop-Port $Port
    $env:LOCUST_TEACHERS = Get-Teachers $Database
    Write-Host ("    tài khoản GV: " + ($env:LOCUST_TEACHERS -split "," | Measure-Object).Count)

    # Tiến trình con thừa kế biến môi trường của phiên hiện tại (Windows PowerShell không có -Environment)
    $previous = $env:ANALYTICS_DB_NAME
    $env:ANALYTICS_DB_NAME = $Database
    $api = Start-Process -FilePath python -PassThru -WindowStyle Hidden `
        -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "$Port", "--workers", "2", `
                      "--timeout-keep-alive", "65"
    $env:ANALYTICS_DB_NAME = $previous
    try {
        $ready = $false
        for ($i = 0; $i -lt 60 -and -not $ready; $i++) {
            try { Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/api/v1/health" | Out-Null; $ready = $true } catch { Start-Sleep -Milliseconds 500 }
        }
        if (-not $ready) { throw "API không khởi động được cho $Label" }

        python -m locust -f perf/locustfile.py --host "http://127.0.0.1:$Port" --headless `
            -u $Users -r $SpawnRate -t "$($RunMinutes)m" `
            --csv "perf/results/locust_$Label" --html "perf/results/locust_$Label.html" --only-summary
    } finally {
        & taskkill /PID $api.Id /T /F 2>&1 | Out-Null
        Stop-Port $Port
        Start-Sleep -Seconds 2
    }
}

# Đặt số phút = 0 để bỏ qua một lượt (vd chỉ chạy lại x10); chạy 0 phút sẽ ghi đè kết quả cũ bằng file rỗng
if ($MinutesX1 -gt 0) { Invoke-Run -Label "x1" -Database "lms_analytics" -RunMinutes $MinutesX1 }
if ($Minutes -gt 0) { Invoke-Run -Label "x10" -Database "lms_analytics_x10" -RunMinutes $Minutes }
Write-Host "Kết quả: perf/results/locust_x1_stats.csv, locust_x10_stats.csv và các file .html" -ForegroundColor Green
