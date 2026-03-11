$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "OK  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "WARN $msg" -ForegroundColor Yellow }

function Resolve-FfmpegDirectory {
    $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($ffmpeg) {
        return (Split-Path -Parent $ffmpeg.Source)
    }

    $wingetRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    if (Test-Path -LiteralPath $wingetRoot) {
        $candidate = Get-ChildItem -Path $wingetRoot -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty FullName
        if ($candidate) {
            return (Split-Path -Parent $candidate)
        }
    }

    return $null
}

$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "未找到虚拟环境 Python: $Python"
}

Write-Step "清理旧的 build/dist"
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Step "执行 PyInstaller 打包"
& $Python -m PyInstaller --clean --noconfirm realtime_translator.spec

$DistDir = Join-Path $ProjectDir "dist\realtime_translator"
if (-not (Test-Path -LiteralPath $DistDir)) {
    throw "未找到打包输出目录: $DistDir"
}

Write-Step "复制运行所需配置文件"
Copy-Item -LiteralPath "config.yaml.example" -Destination (Join-Path $DistDir "config.yaml.example") -Force
if (Test-Path -LiteralPath "config.yaml") {
    Copy-Item -LiteralPath "config.yaml" -Destination (Join-Path $DistDir "config.yaml") -Force
    Write-Ok "已复制本地 config.yaml"
} else {
    Write-Warn "未找到本地 config.yaml，只复制了 config.yaml.example"
}

Write-Step "复制辅助脚本与说明"
Copy-Item -LiteralPath "scripts\healthcheck.ps1" -Destination (Join-Path $DistDir "healthcheck.ps1") -Force
Copy-Item -LiteralPath "scripts\list_devices.py" -Destination (Join-Path $DistDir "list_devices.py") -Force
Copy-Item -LiteralPath "README.md" -Destination (Join-Path $DistDir "README.md") -Force
Copy-Item -LiteralPath "README_EN.md" -Destination (Join-Path $DistDir "README_EN.md") -Force

Write-Step "尝试捆绑 FFmpeg 可执行文件"
$ffmpegDir = Resolve-FfmpegDirectory
if ($ffmpegDir) {
    foreach ($bin in @("ffmpeg.exe", "ffprobe.exe", "ffplay.exe")) {
        $src = Join-Path $ffmpegDir $bin
        if (Test-Path -LiteralPath $src) {
            Copy-Item -LiteralPath $src -Destination (Join-Path $DistDir $bin) -Force
        }
    }
    Write-Ok "已复制 FFmpeg 二进制文件"
} else {
    Write-Warn "当前 shell 未找到 ffmpeg，产物将依赖系统 PATH 中已有的 FFmpeg"
}

$Launcher = @'
@echo off
setlocal
cd /d %~dp0
if not exist config.yaml (
  echo [WARN] 未找到 config.yaml，正在使用 config.yaml.example 作为参数启动
  realtime_translator.exe config.yaml.example
) else (
  realtime_translator.exe config.yaml
)
endlocal
'@
Set-Content -LiteralPath (Join-Path $DistDir "run.cmd") -Value $Launcher -Encoding ASCII

Write-Host ""
Write-Ok "Windows 打包完成: $DistDir"
Write-Ok "启动方式: dist\\realtime_translator\\run.cmd"
