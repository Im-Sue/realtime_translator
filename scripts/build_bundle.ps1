<#
.SYNOPSIS
    Windows 构建脚本 — 准备 Python embedded bundle + Tauri 打包
.DESCRIPTION
    1. 下载 Embedded Python 3.12
    2. 改名 python.exe → rt-engine.exe
    3. 安装 pip 依赖到 deps/
    4. 复制 Python 源码到 backend/
    5. 运行 pnpm tauri build 生成最终安装包
.EXAMPLE
    .\scripts\build_bundle.ps1
    .\scripts\build_bundle.ps1 -SkipPython   # 跳过 Python 下载（已有）
    .\scripts\build_bundle.ps1 -BundleOnly   # 只准备 bundle，不运行 tauri build
#>

param(
    [switch]$SkipPython,
    [switch]$BundleOnly
)

$ErrorActionPreference = "Stop"

# ── 配置 ────────────────────────────────────────────────────

$PYTHON_VER = "3.12.8"
$PLATFORM = "windows-x64"
$BUNDLE_DIR = "bundle\$PLATFORM"
$PYTHON_DIR = "$BUNDLE_DIR\python"
$BACKEND_DIR = "$BUNDLE_DIR\backend"
$DEPS_DIR = "$BUNDLE_DIR\deps"
$PYTHON_URL = "https://www.python.org/ftp/python/$PYTHON_VER/python-$PYTHON_VER-embed-amd64.zip"
$PYTHON_ZIP = "$env:TEMP\python-embed-$PYTHON_VER.zip"

$PROJECT_ROOT = Split-Path $PSScriptRoot -Parent

Set-Location $PROJECT_ROOT
Write-Host "=== 实时同传桌面应用 构建脚本 ===" -ForegroundColor Cyan
Write-Host "项目根目录: $PROJECT_ROOT"

# ── 1. 下载 Embedded Python ─────────────────────────────────

if (-not $SkipPython) {
    Write-Host ""
    Write-Host "[1/5] 准备 Embedded Python $PYTHON_VER ..." -ForegroundColor Yellow

    # 清理旧的
    if (Test-Path $PYTHON_DIR) {
        Remove-Item $PYTHON_DIR -Recurse -Force
    }
    New-Item -ItemType Directory -Path $PYTHON_DIR -Force | Out-Null

    if (-not (Test-Path $PYTHON_ZIP)) {
        Write-Host "  下载 $PYTHON_URL ..."
        Invoke-WebRequest -Uri $PYTHON_URL -OutFile $PYTHON_ZIP -UseBasicParsing
        Write-Host "  下载完成: $PYTHON_ZIP"
    } else {
        Write-Host "  使用缓存: $PYTHON_ZIP"
    }

    Write-Host "  解压到 $PYTHON_DIR ..."
    Expand-Archive -Path $PYTHON_ZIP -DestinationPath $PYTHON_DIR -Force

    # 改名
    Rename-Item "$PYTHON_DIR\python.exe" "rt-engine.exe" -ErrorAction SilentlyContinue
    $pthFile = Get-ChildItem "$PYTHON_DIR\python*._pth" | Select-Object -First 1
    if ($pthFile) {
        $newPth = "$PYTHON_DIR\rt-engine._pth"
        Move-Item $pthFile.FullName $newPth -Force
        # 启用 import site + 添加搜索路径
        # 注意: 路径相对于 python/ 目录（即 rt-engine.exe 所在目录）
        # ../backend — 包含 realtime_translator 包（绝对导入）
        # ../backend/realtime_translator — 直接导入 desktop_backend 等
        Add-Content $newPth "`n../deps`n../backend`n../backend/realtime_translator`nimport site"
        Write-Host "  _pth 文件已更新: $newPth (添加 ../deps, ../backend, ../backend/realtime_translator, import site)"
    }

    Write-Host "  Embedded Python 准备完成" -ForegroundColor Green
} else {
    Write-Host "[1/5] 跳过 Python 下载 (--SkipPython)" -ForegroundColor DarkGray
}

# ── 2. 安装 pip + 依赖 ──────────────────────────────────────

Write-Host ""
Write-Host "[2/5] 安装 Python 依赖到 $DEPS_DIR ..." -ForegroundColor Yellow

if (Test-Path $DEPS_DIR) {
    Remove-Item $DEPS_DIR -Recurse -Force
}
New-Item -ItemType Directory -Path $DEPS_DIR -Force | Out-Null

# 使用系统 pip 安装到 bundle deps 目录（embedded Python 没有 pip）
Write-Host "  安装项目依赖到 bundle ..."
pip install `
    numpy sounddevice websockets protobuf PyYAML `
    --target="$DEPS_DIR" `
    --only-binary=:all: `
    --no-cache-dir `
    --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ 依赖安装失败!" -ForegroundColor Red
    exit 1
}

Write-Host "  依赖安装完成" -ForegroundColor Green

# ── 2b. 准备 ffmpeg ────────────────────────────────────────

Write-Host ""
Write-Host "[2b/5] 准备 ffmpeg ..."-ForegroundColor Yellow

$FFMPEG_EXE = "$PYTHON_DIR\ffmpeg.exe"
if (Test-Path $FFMPEG_EXE) {
    Write-Host "  ffmpeg.exe 已存在，跳过" -ForegroundColor DarkGray
} else {
    # 优先从本地 PATH 复制（比在线下载快得多）
    # 筛选 >10MB 的版本——小文件是 conda 等共享构建，依赖外部 DLL，安装后会报缺 avcodec-58.dll
    $localCandidates = @(Get-Command ffmpeg -All -ErrorAction SilentlyContinue | ForEach-Object { $_.Source } | Where-Object {
        (Get-Item $_).Length -gt 10MB
    })
    if ($localCandidates.Count -gt 0) {
        $chosen = $localCandidates[0]
        Copy-Item $chosen $FFMPEG_EXE -Force
        $sizeMB = [math]::Round((Get-Item $FFMPEG_EXE).Length / 1MB, 1)
        Write-Host "  从本地复制: $chosen (${sizeMB}MB, 静态构建)" -ForegroundColor Green
    } else {
        # 本地没有，在线下载 gyan.dev essentials 构建
        $FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        $FFMPEG_ZIP = "$env:TEMP\ffmpeg-release-essentials.zip"

        if (-not (Test-Path $FFMPEG_ZIP)) {
            Write-Host "  本地未找到 ffmpeg，在线下载 ... (可能需要几分钟)"
            Invoke-WebRequest -Uri $FFMPEG_URL -OutFile $FFMPEG_ZIP -UseBasicParsing
            Write-Host "  下载完成: $FFMPEG_ZIP"
        } else {
            Write-Host "  使用缓存: $FFMPEG_ZIP"
        }

        # 解压并只提取 bin/ffmpeg.exe
        $FFMPEG_TMP = "$env:TEMP\ffmpeg-extract"
        if (Test-Path $FFMPEG_TMP) { Remove-Item $FFMPEG_TMP -Recurse -Force }

        Write-Host "  解压 ffmpeg ..."
        Expand-Archive -Path $FFMPEG_ZIP -DestinationPath $FFMPEG_TMP -Force

        $ffmpegBin = Get-ChildItem -Path $FFMPEG_TMP -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
        if ($ffmpegBin) {
            Copy-Item $ffmpegBin.FullName $FFMPEG_EXE -Force
            $sizeMB = [math]::Round($ffmpegBin.Length / 1MB, 1)
            Write-Host "  ffmpeg.exe 已复制到 python/ (${sizeMB}MB)" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ 未在压缩包中找到 ffmpeg.exe!" -ForegroundColor Red
        }

        Remove-Item $FFMPEG_TMP -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ── 3. 复制 Python 源码 ────────────────────────────────────

Write-Host ""
Write-Host "[3/5] 复制 Python 源码到 $BACKEND_DIR ...\" -ForegroundColor Yellow

if (Test-Path $BACKEND_DIR) {
    Remove-Item $BACKEND_DIR -Recurse -Force
}

# 源码放入 backend/realtime_translator/ 以保持包结构
# 这样 PYTHONPATH=deps;backend 时，from realtime_translator.pb2... 能正确解析
$PKG_DIR = "$BACKEND_DIR\realtime_translator"
New-Item -ItemType Directory -Path $PKG_DIR -Force | Out-Null

# 核心文件
Copy-Item -Path "core" -Destination "$PKG_DIR\core" -Recurse
Copy-Item -Path "desktop_backend" -Destination "$PKG_DIR\desktop_backend" -Recurse
Copy-Item -Path "pb2" -Destination "$PKG_DIR\pb2" -Recurse
Copy-Item -Path "gui" -Destination "$PKG_DIR\gui" -Recurse
Copy-Item -Path "main.py" -Destination "$PKG_DIR\"
Copy-Item -Path "__init__.py" -Destination "$PKG_DIR\" -ErrorAction SilentlyContinue

# 配置模板
Copy-Item -Path "config.yaml.example" -Destination "$PKG_DIR\" -ErrorAction SilentlyContinue

# 排除 __pycache__、.pyc 和测试目录
Get-ChildItem -Path $BACKEND_DIR -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Path $BACKEND_DIR -Recurse -Filter "*.pyc" | Remove-Item -Force
$testsDir = "$PKG_DIR\desktop_backend\tests"
if (Test-Path $testsDir) {
    Remove-Item $testsDir -Recurse -Force
    Write-Host "  已排除测试目录: desktop_backend/tests/" -ForegroundColor DarkGray
}

Write-Host "  源码复制完成 (backend/realtime_translator/)" -ForegroundColor Green

# ── 4. 验证 bundle ─────────────────────────────────────────

Write-Host ""
Write-Host "[4/5] 验证 bundle 结构 ..." -ForegroundColor Yellow

$checks = @(
    @{ Path = "$PYTHON_DIR\rt-engine.exe"; Label = "rt-engine.exe" },
    @{ Path = "$BACKEND_DIR\realtime_translator\desktop_backend\sidecar.py"; Label = "realtime_translator/desktop_backend/sidecar.py" },
    @{ Path = "$BACKEND_DIR\realtime_translator\main.py"; Label = "realtime_translator/main.py" },
    @{ Path = "$BACKEND_DIR\realtime_translator\core\volcengine_client.py"; Label = "realtime_translator/core/volcengine_client.py" },
    @{ Path = "$BACKEND_DIR\realtime_translator\config.yaml.example"; Label = "realtime_translator/config.yaml.example" },
    @{ Path = "$BACKEND_DIR\realtime_translator\__init__.py"; Label = "realtime_translator/__init__.py" },
    @{ Path = "$DEPS_DIR\numpy"; Label = "deps/numpy" },
    @{ Path = "$PYTHON_DIR\ffmpeg.exe"; Label = "python/ffmpeg.exe" }
)

$allOk = $true
foreach ($check in $checks) {
    if (Test-Path $check.Path) {
        Write-Host "  ✅ $($check.Label)" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $($check.Label) - 未找到!" -ForegroundColor Red
        $allOk = $false
    }
}

# 统计大小
$bundleSize = (Get-ChildItem -Path $BUNDLE_DIR -Recurse | Measure-Object -Property Length -Sum).Sum
$bundleMB = [math]::Round($bundleSize / 1MB, 1)
Write-Host ""
Write-Host "  Bundle 总大小: ${bundleMB}MB" -ForegroundColor Cyan

if (-not $allOk) {
    Write-Host "  ⚠ 部分文件缺失，请检查!" -ForegroundColor Red
}

# ── 5. Tauri Build ─────────────────────────────────────────

if ($BundleOnly) {
    Write-Host ""
    Write-Host "[5/5] 跳过 Tauri build (--BundleOnly)" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "=== Bundle 准备完成 ===" -ForegroundColor Cyan
    Write-Host "路径: $BUNDLE_DIR"
    exit 0
}

Write-Host ""
Write-Host "[5/5] 运行 pnpm tauri build ..." -ForegroundColor Yellow

# ── 5a. 备份 tauri.conf.json 并注入 resources ──
$tauriConfPath = "src-tauri\tauri.conf.json"
$tauriConfBackup = "src-tauri\tauri.conf.json.bak"
$bundleAbsPath = (Resolve-Path $BUNDLE_DIR).Path -replace '\\', '/'

Write-Host "  备份 tauri.conf.json ..."
Copy-Item $tauriConfPath $tauriConfBackup -Force

$tauriConf = Get-Content $tauriConfPath -Raw | ConvertFrom-Json

# 注入 resources — 使用 map 格式 + 绝对路径
# 格式: {"源路径/": "目标目录"} — Tauri 将源目录下的所有文件复制到安装目录的目标路径下
$resources = @{
    "$bundleAbsPath/python/" = "python"
    "$bundleAbsPath/backend/" = "backend"
    "$bundleAbsPath/deps/" = "deps"
}
$tauriConf.bundle | Add-Member -MemberType NoteProperty -Name "resources" -Value $resources -Force

$jsonText = $tauriConf | ConvertTo-Json -Depth 10
# 使用 WriteAllText 避免 PowerShell 5.x 的 UTF8 BOM（Rust serde 不兼容 BOM）
[System.IO.File]::WriteAllText((Resolve-Path $tauriConfPath).Path, $jsonText, [System.Text.UTF8Encoding]::new($false))
Write-Host "  已注入 resources (map 格式, 绝对路径)"
Write-Host "  python/ -> python, backend/ -> backend, deps/ -> deps"

# ── 5b. 运行 tauri build ──
$env:CARGO_HTTP_CHECK_REVOKE = "false"

try {
    pnpm tauri build
    $buildResult = $LASTEXITCODE
} finally {
    # ── 5c. 还原 tauri.conf.json ──
    Write-Host ""
    Write-Host "  还原 tauri.conf.json ..."
    Move-Item $tauriConfBackup $tauriConfPath -Force
}

if ($buildResult -eq 0) {
    Write-Host ""
    Write-Host "=== 构建成功！===" -ForegroundColor Green

    $outputDir = "src-tauri\target\release\bundle"
    if (Test-Path $outputDir) {
        Write-Host "安装包位置:"
        Get-ChildItem "$outputDir\msi\*.msi" -ErrorAction SilentlyContinue | ForEach-Object {
            $sizeMB = [math]::Round($_.Length / 1MB, 1)
            Write-Host "  MSI: $($_.FullName) (${sizeMB}MB)" -ForegroundColor Cyan
        }
        Get-ChildItem "$outputDir\nsis\*.exe" -ErrorAction SilentlyContinue | ForEach-Object {
            $sizeMB = [math]::Round($_.Length / 1MB, 1)
            Write-Host "  EXE: $($_.FullName) (${sizeMB}MB)" -ForegroundColor Cyan
        }
    }
} else {
    Write-Host ""
    Write-Host "=== 构建失败 ===" -ForegroundColor Red
    exit 1
}

