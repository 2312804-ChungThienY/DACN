<#
.SYNOPSIS
  Lệnh tắt cho dự án LMS Analytics trên Windows (SPEC 6.4 "Makefile/scripts").

.EXAMPLE
  .\scripts\lms.ps1 setup          # cài thư viện Python + npm, migrate 2 CSDL
  .\scripts\lms.ps1 seed           # sinh cấu trúc Moodle giả lập
  .\scripts\lms.ps1 mock           # sinh hành vi học tập tới LMS_AS_OF
  .\scripts\lms.ps1 etl-backfill   # nạp lịch sử 3 bảng fact
  .\scripts\lms.ps1 users          # tạo/cập nhật tài khoản (cần $env:BACKEND_SEED_PASSWORD)
  .\scripts\lms.ps1 api | web      # chạy API :8000 / frontend dev :5173
  .\scripts\lms.ps1 test           # pytest + vitest
  .\scripts\lms.ps1 e2e            # Playwright (cần API + web đang chạy, $env:LMS_DEMO_PASSWORD)
  .\scripts\lms.ps1 bench          # hiệu năng: dựng x10, EXPLAIN x1/x10 (Locust, ETL: xem perf/README.md)
  .\scripts\lms.ps1 docker         # demo trọn gói bằng docker compose
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("setup", "seed", "mock", "etl-backfill", "users", "api", "web", "test", "e2e", "bench", "docker")]
    [string]$Command
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-Step([string]$Title, [scriptblock]$Block) {
    Write-Host "==> $Title" -ForegroundColor Cyan
    & $Block
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Thất bại: $Title (mã $LASTEXITCODE)" }
}

switch ($Command) {
    "setup" {
        Invoke-Step "Cài thư viện Python" { python -m pip install -r requirements.txt }
        Invoke-Step "Cài thư viện frontend" { Push-Location frontend; npm install; Pop-Location }
        Invoke-Step "Migrate CSDL phân tích" { python -m database.migrate up --target analytics }
        Invoke-Step "Migrate CSDL Moodle rút gọn" { python -m database.migrate up --target moodle }
    }
    "seed" { Invoke-Step "Sinh cấu trúc Moodle" { python -m mockdata.seed_structure --reset } }
    "mock" { Invoke-Step "Sinh hành vi học tập" { python -m mockdata.generate_activity --reset } }
    "etl-backfill" { Invoke-Step "ETL backfill" { python -m etl.jobs.backfill --from 2026-09-07 } }
    "users" { Invoke-Step "Đồng bộ tài khoản" { python -m backend.app.cli sync-users } }
    "api" { python -m uvicorn backend.app.main:app --port 8000 }
    "web" { Push-Location frontend; npm run dev; Pop-Location }
    "test" {
        Invoke-Step "pytest" { python -m pytest -q }
        Invoke-Step "vitest" { Push-Location frontend; npm test; Pop-Location }
    }
    "e2e" { Push-Location frontend; npx playwright test; Pop-Location }
    "bench" {
        Invoke-Step "Dựng CSDL x10" { python -m perf.build_x10 }
        Invoke-Step "EXPLAIN ANALYZE x1" { python -m perf.explain_queries --dataset x1 }
        Invoke-Step "EXPLAIN ANALYZE x10" { python -m perf.explain_queries --dataset x10 }
    }
    "docker" {
        if (-not (Test-Path docker\.env)) { throw "Chưa có docker/.env – sao chép từ docker/.env.example và điền giá trị" }
        Invoke-Step "docker compose up" { docker compose --env-file docker/.env up --build -d }
        Write-Host "Mở http://localhost:8080 (lần đầu chờ dịch vụ init sinh dữ liệu: docker compose logs -f init)"
    }
}
