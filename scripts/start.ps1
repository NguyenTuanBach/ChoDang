# Chạy VIN-15 cùng lúc trên Windows (tương đương scripts/start.sh): BE (FastAPI, cổng 8000), agent-api (cổng 8100) và FE (Next.js, cổng 3000).
# Gom log về một cửa sổ PowerShell. Không cần Docker (DB là Supabase qua DATABASE_URL trong .env). Ctrl+C dừng tất cả.
# BE hoặc FE chết thì dừng tất cả; agent chết thì BE vẫn chạy.
#
# Cách chạy (từ gốc repo):
#   powershell -ExecutionPolicy Bypass -File scripts\start.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\start.ps1 -SkipAgent     # không chạy agent (đỡ tốn RAM)
#
# Tham số:
#   -SkipBe      Không chạy backend (cổng 8000).
#   -SkipAgent   Không chạy agent-api (cổng 8100). BE vẫn chạy, chỉ là không gọi được agent.
#   -SkipFe      Không chạy frontend Next.js (cổng 3000).
#   -Help        In hướng dẫn này.
# Biến môi trường (đọc từ .env ở gốc repo, mẫu .env.example):
#   APP_PORT (8000), NEXT_PORT (3000), AGENT_API_PORT (8100), AGENT_API_SERVICE_TOKEN, DATABASE_URL, OPENAI_API_KEY
# Cần cài uv (hoặc Python để dùng `python -m uv`) và Node.js/npm. Lần đầu (hoặc khi lock đổi) script tự cài dependency (uv sync, npm ci).

[CmdletBinding()]
param(
    [switch]$SkipBe,
    [switch]$SkipAgent,
    [switch]$SkipFe,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

if ($Help) {
    Get-Content -LiteralPath $MyInvocation.MyCommand.Path -TotalCount 18 | Where-Object { $_ -like '#*' } | ForEach-Object { $_.TrimStart('#').TrimStart() }
    exit 0
}

if ($SkipBe -and $SkipAgent -and $SkipFe) {
    Write-Host '  [ERROR] Đã bỏ qua tất cả, không có gì để chạy.' -ForegroundColor Red
    exit 2
}

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BeDir = Join-Path $RootDir 'be'
$AgentDir = Join-Path $RootDir 'agent'
$FeDir = Join-Path $RootDir 'fe'
$LogDir = Join-Path ([System.IO.Path]::GetTempPath()) ('vin15-start-' + $PID)
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Mỗi dịch vụ nền: Name, Tag, Critical, Process, Files (stdout/stderr) và vị trí đã đọc để in log theo tiền tố.
$script:Services = New-Object System.Collections.ArrayList
$script:TearDownDone = $false
$script:AgentStarted = $false

function Step([string]$Text) { Write-Host ''; Write-Host ">>> $Text" -ForegroundColor Cyan }
function Ok([string]$Text) { Write-Host "  [OK] $Text" -ForegroundColor Green }
function Warn([string]$Text) { Write-Host "  [WARN] $Text" -ForegroundColor Yellow }
function Fail([string]$Text) { Write-Host "  [ERROR] $Text" -ForegroundColor Red }
function Info([string]$Text) { Write-Host "    $Text" -ForegroundColor DarkGray }

function Test-Command([string]$Name) { return [bool](Get-Command $Name -ErrorAction SilentlyContinue) }

function Require-Command([string]$Name, [string]$Hint) {
    if (Test-Command $Name) { return }
    Fail "Chưa cài $Name hoặc không có trong PATH. $Hint"
    exit 1
}

# ---------- .env và cấu hình ----------

function Import-DotEnv {
    # Đọc .env từng dòng; giá trị có dấu cách hay ký tự lạ không bị diễn giải.
    $envFile = Join-Path $RootDir '.env'
    if (-not (Test-Path -LiteralPath $envFile)) {
        Warn 'Không thấy .env; dùng giá trị mặc định (copy .env.example thành .env để cấu hình).'
        return
    }
    Info 'Đọc .env'
    foreach ($raw in Get-Content -LiteralPath $envFile -Encoding UTF8) {
        $line = $raw.Trim()
        if ($line -eq '' -or $line.StartsWith('#') -or -not $line.Contains('=')) { continue }
        $idx = $line.IndexOf('=')
        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        if ($key -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') { Warn "Bỏ qua khoá không hợp lệ: $key"; continue }
        if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        Set-Item -Path "Env:$key" -Value $value
    }
}

function Get-EnvOr([string]$Name, [string]$Default) {
    $current = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrEmpty($current)) { return $Default }
    return $current
}

function Initialize-Config {
    $script:AppPort = Get-EnvOr 'APP_PORT' '8000'
    $script:NextPort = Get-EnvOr 'NEXT_PORT' '3000'
    $script:AgentPort = Get-EnvOr 'AGENT_API_PORT' '8100'
    $env:APP_PORT = $script:AppPort
    $env:NEXT_PORT = $script:NextPort
    $env:AGENT_API_PORT = $script:AgentPort
    $script:BeUrl = "http://localhost:$($script:AppPort)"
    $script:FeUrl = "http://localhost:$($script:NextPort)"
    # FE (Next) chuyển tiếp /api/* sang BE_URL (xem fe/next.config.ts).
    $env:BE_URL = $script:BeUrl
    $script:AgentUrl = "http://127.0.0.1:$($script:AgentPort)"
    # Hai bên phải dùng cùng token; BE chỉ gọi agent khi có AGENT_API_URL. Giá trị đã đặt trong .env thì giữ.
    $env:AGENT_API_SERVICE_TOKEN = Get-EnvOr 'AGENT_API_SERVICE_TOKEN' 'agent-api-local-only'
    if (-not $SkipAgent) { $env:AGENT_API_URL = Get-EnvOr 'AGENT_API_URL' $script:AgentUrl }
    # agent-api chỉ nghe loopback khi chạy local.
    $env:AGENT_API_HOST = '127.0.0.1'
    if ((Get-EnvOr 'APP_ENV' 'development') -ne 'production') {
        $env:AGENT_DEV_DEFAULT_USER_EMAIL = Get-EnvOr 'AGENT_DEV_DEFAULT_USER_EMAIL' 'sv.a@example.test'
    }
}

# ---------- Cổng ----------

function Get-PortPids([int]$Port) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { return @() }
    return @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
}

function Test-PortInUse([int]$Port) { return (Get-PortPids $Port).Count -gt 0 }

function Get-PortProcessInfo([int]$Port) {
    $lines = foreach ($procId in (Get-PortPids $Port)) {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
        if ($p) { "PID $procId  $($p.Name)  $($p.CommandLine)" } else { "PID $procId (không lấy được thông tin)" }
    }
    return ($lines -join '; ')
}

function Confirm-KillPort([int]$Port, [string]$Name) {
    $procIds = Get-PortPids $Port
    if ($procIds.Count -eq 0 -or -not [Environment]::UserInteractive) { return $false }
    Write-Host ''
    Warn "Cổng $Port ($Name) đang bị chiếm bởi:"
    Write-Host ("      " + (Get-PortProcessInfo $Port))
    $answer = Read-Host "  Kill tiến trình trên để giải phóng cổng $Port? [y/N]"
    if ($answer -notmatch '^(y|yes)$') { return $false }
    foreach ($procId in $procIds) {
        try { Stop-Process -Id $procId -Force -ErrorAction Stop; Ok "Đã dừng PID $procId" } catch { Warn "Không dừng được PID ${procId}: $($_.Exception.Message)" }
    }
    Start-Sleep -Seconds 1
    return -not (Test-PortInUse $Port)
}

function Test-Ports {
    Step 'Kiểm tra cổng'
    $errors = @()
    $checks = @(
        @{ Skip = $SkipBe; Port = [int]$script:AppPort; Name = 'Backend' },
        @{ Skip = $SkipFe; Port = [int]$script:NextPort; Name = 'Frontend' },
        @{ Skip = $SkipAgent; Port = [int]$script:AgentPort; Name = 'Agent API' }
    )
    foreach ($c in $checks) {
        if ($c.Skip) { continue }
        if ((Test-PortInUse $c.Port) -and -not (Confirm-KillPort $c.Port $c.Name)) {
            $errors += "$($c.Port) ($($c.Name)): $(Get-PortProcessInfo $c.Port)"
        }
    }
    if ($errors.Count -gt 0) {
        Fail 'Cổng đang bị chiếm:'
        $errors | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        exit 1
    }
    Ok 'Cổng trống'
}

# ---------- Tiến trình nền ----------

function Read-NewLog($Svc) {
    foreach ($key in 'Out', 'Err') {
        $file = $Svc[$key + 'File']
        if (-not (Test-Path -LiteralPath $file)) { continue }
        $stream = $null
        try {
            $stream = [System.IO.File]::Open($file, 'Open', 'Read', 'ReadWrite')
            [void]$stream.Seek($Svc[$key + 'Pos'], 'Begin')
            $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8)
            while (($line = $reader.ReadLine()) -ne $null) {
                Write-Host ("  [{0}] {1}" -f $Svc.Tag, $line)
            }
            $Svc[$key + 'Pos'] = $stream.Position
        } catch {
            # Tệp log đang bị ghi: bỏ qua lượt này.
        } finally {
            if ($stream) { $stream.Dispose() }
        }
    }
}

function Show-AllLogs { foreach ($svc in $script:Services) { Read-NewLog $svc } }

# Chạy lệnh qua cmd /c (để gọi được npm.cmd, uv.exe...) với log ra tệp riêng; dừng thì taskkill /T để diệt cả cây tiến trình con.
function Start-Svc([string]$Name, [string]$Tag, [bool]$Critical, [string]$Dir, [string]$CommandLine) {
    $outFile = Join-Path $LogDir "$Tag.out.log"
    $errFile = Join-Path $LogDir "$Tag.err.log"
    '' | Set-Content -LiteralPath $outFile
    '' | Set-Content -LiteralPath $errFile
    $proc = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $CommandLine -WorkingDirectory $Dir `
        -RedirectStandardOutput $outFile -RedirectStandardError $errFile -WindowStyle Hidden -PassThru
    [void]$script:Services.Add(@{ Name = $Name; Tag = $Tag; Critical = $Critical; Process = $proc; OutFile = $outFile; ErrFile = $errFile; OutPos = 0; ErrPos = 0; Reported = $false })
}

function Stop-All {
    if ($script:TearDownDone) { return }
    $script:TearDownDone = $true
    Write-Host ''
    Write-Host '  Đang dừng ...' -ForegroundColor Yellow
    # Dừng theo thứ tự ngược (agent trước) để BE không gọi vào agent đã tắt giữa chừng.
    for ($i = $script:Services.Count - 1; $i -ge 0; $i--) {
        $p = $script:Services[$i].Process
        if ($p -and -not $p.HasExited) { & taskkill.exe /PID $p.Id /T /F 2>&1 | Out-Null }
    }
    Ok 'Đã dừng tất cả.'
}

function Wait-ForUrl([string]$Url, [string]$Label, [int]$TimeoutSeconds) {
    Info "Chờ $Label ($Url) ..."
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($r.StatusCode -lt 500) { Ok "$Label đã sẵn sàng"; return $true }
        } catch {
            if ($_.Exception.Response) { Ok "$Label đã sẵn sàng"; return $true }
        }
        Show-AllLogs
        Start-Sleep -Seconds 2
    }
    return $false
}

# ---------- Môi trường uv / npm ----------

function Get-FileSetHash([string[]]$Paths) {
    $parts = foreach ($p in $Paths) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes(($parts -join ''))
    $sha = [System.Security.Cryptography.SHA256]::Create()
    return ([System.BitConverter]::ToString($sha.ComputeHash($bytes)) -replace '-', '')
}

function Sync-Module([string]$Dir, [string]$Name) {
    $stamp = Join-Path $Dir '.venv\.vin15-synced'
    $wanted = Get-FileSetHash @((Join-Path $Dir 'uv.lock'), (Join-Path $Dir 'pyproject.toml'))
    if ((Test-Path -LiteralPath $stamp) -and ((Get-Content -LiteralPath $stamp -Raw).Trim() -eq $wanted)) { return }
    Info "Cài dependency của $Name bằng uv (lần đầu hoặc uv.lock đổi) ..."
    Push-Location $Dir
    try {
        Invoke-Expression "& $script:Uv sync --extra dev"
        if ($LASTEXITCODE -ne 0) { Fail "uv sync $Name thất bại."; exit 1 }
    } finally { Pop-Location }
    New-Item -ItemType Directory -Force -Path (Split-Path $stamp) | Out-Null
    Set-Content -LiteralPath $stamp -Value $wanted
}

function Initialize-Environment {
    Step 'Chuẩn bị môi trường (uv)'
    # uv có thể nằm trong PATH hoặc chỉ cài qua pip. Trường hợp pip, gọi thẳng uv.exe thật: `python -m uv` tự thoát ngay sau khi
    # khởi động tiến trình thật (os.execv trên Windows) nên script không theo dõi được tiến trình đó.
    $script:Uv = $null
    if (Test-Command 'uv') {
        $script:Uv = 'uv'
    } else {
        # 1) Tìm uv.exe ở các chỗ pip / trình cài đặt chính thức hay đặt (không cần gọi python).
        $roots = @(
            (Join-Path $env:APPDATA 'Python\Python*\Scripts\uv.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python*\Scripts\uv.exe'),
            (Join-Path $env:USERPROFILE '.local\bin\uv.exe'),
            (Join-Path $env:USERPROFILE '.cargo\bin\uv.exe')
        )
        $hit = $roots | ForEach-Object { Get-ChildItem -Path $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
        if ($hit) { $script:Uv = '"' + $hit.FullName + '"' }
    }
    if (-not $script:Uv) {
        # 2) Hỏi chính Python đang dùng. Tạm bỏ 'Stop' để một dòng stderr của python không làm script dừng.
        foreach ($py in @('python', 'py')) {
            if (-not (Test-Command $py)) { continue }
            $prev = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            try { $out = & $py -c "import uv; print(uv.find_uv_bin())" 2>&1 | ForEach-Object { "$_" } | Where-Object { $_ -like '*uv.exe' } | Select-Object -First 1 }
            finally { $ErrorActionPreference = $prev }
            if ($out -and (Test-Path -LiteralPath $out.Trim())) { $script:Uv = '"' + $out.Trim() + '"'; break }
        }
    }
    if (-not $script:Uv) { Fail 'Không tìm thấy uv. Cài: pip install uv (hoặc https://docs.astral.sh/uv/) rồi mở lại terminal.'; exit 1 }
    Info "Dùng: $script:Uv"
    if (-not $SkipBe) { Sync-Module $BeDir 'be' }
    if (-not $SkipAgent) { Sync-Module $AgentDir 'agent' }
    if (-not $SkipFe) {
        Require-Command 'npm' 'Cài Node.js/npm hoặc chạy với -SkipFe.'
        $stamp = Join-Path $FeDir 'node_modules\.vin15-synced'
        $wanted = Get-FileSetHash @((Join-Path $FeDir 'package-lock.json'))
        if (-not ((Test-Path -LiteralPath $stamp) -and ((Get-Content -LiteralPath $stamp -Raw).Trim() -eq $wanted))) {
            Info 'Cài dependency của fe bằng npm ci (lần đầu hoặc package-lock.json đổi) ...'
            Push-Location $FeDir
            try {
                & npm.cmd ci
                if ($LASTEXITCODE -ne 0) { Fail 'npm ci thất bại.'; exit 1 }
            } finally { Pop-Location }
            Set-Content -LiteralPath $stamp -Value $wanted
        }
    }
    Ok 'Môi trường sẵn sàng'
}

# ---------- Dịch vụ ----------

function Start-Agent {
    if ($SkipAgent) { return }
    Step "Chạy Agent API (cổng $script:AgentPort)"
    # Không bắt buộc: chết thì BE vẫn chạy, monitor chỉ cảnh báo.
    Start-Svc 'Agent API' 'AG' $false $AgentDir "$script:Uv run --no-sync vin15-agent-api"
    if (-not (Wait-ForUrl "$script:AgentUrl/healthz" 'Agent API' 60)) { Warn "Agent API không lên. Log: $LogDir\AG.*.log"; return }
    $script:AgentStarted = $true
}

function Start-Backend {
    if ($SkipBe) { return }
    Step "Chạy Backend - FastAPI (cổng $script:AppPort)"
    if (-not $env:DATABASE_URL) { Warn 'Chưa có DATABASE_URL: BE chạy không database (chỉ health).' }
    Start-Svc 'Backend' 'BE' $true $BeDir "$script:Uv run --no-sync python -m vin15"
    if (-not (Wait-ForUrl "$script:BeUrl/api/health" 'Backend' 90)) {
        Show-AllLogs
        Fail "Backend không lên. Log: $LogDir\BE.*.log"
        Stop-All
        exit 1
    }
    Info "Swagger: $script:BeUrl/docs"
}

function Start-Frontend {
    if ($SkipFe) { return }
    Step "Chạy Frontend - Next.js dev (cổng $script:NextPort)"
    Start-Svc 'Frontend' 'FE' $true $FeDir "npm run dev -- --port $script:NextPort"
    if (-not (Wait-ForUrl $script:FeUrl 'Frontend' 120)) {
        Show-AllLogs
        Fail "Frontend không lên. Log: $LogDir\FE.*.log"
        Stop-All
        exit 1
    }
}

function Watch-Services {
    Info "Log: $LogDir"
    while ($true) {
        Show-AllLogs
        foreach ($svc in $script:Services) {
            if ($svc.Process.HasExited -and -not $svc.Reported) {
                $svc.Reported = $true
                Show-AllLogs
                if ($svc.Critical) {
                    Fail "$($svc.Name) đã dừng (mã $($svc.Process.ExitCode))."
                    return
                }
                Warn "$($svc.Name) đã dừng (mã $($svc.Process.ExitCode)); BE/FE vẫn chạy."
            }
        }
        Start-Sleep -Seconds 1
    }
}

# ---------- Main ----------

try {
    Import-DotEnv
    Initialize-Config
    Test-Ports
    Initialize-Environment
    Start-Agent
    Start-Backend
    Start-Frontend

    Write-Host ''
    Write-Host '========================================================' -ForegroundColor Green
    Write-Host '  VIN-15 đang chạy' -ForegroundColor Green
    Write-Host '========================================================' -ForegroundColor Green
    if (-not $SkipBe) { Write-Host "  Backend:   $script:BeUrl  (Swagger: $script:BeUrl/docs)" }
    if (-not $SkipFe) { Write-Host "  Frontend:  $script:FeUrl" }
    if ($script:AgentStarted) { Write-Host "  Agent API: $script:AgentUrl/healthz" }
    Write-Host ''
    Write-Host '  Ctrl+C dừng tất cả.' -ForegroundColor Yellow
    Write-Host ''
    Watch-Services
} finally {
    Stop-All
}
