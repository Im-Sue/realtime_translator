$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

function Write-Ok($msg) { Write-Host "OK  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "WARN $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "ERR  $msg" -ForegroundColor Red }

if (-not (Test-Path -LiteralPath ".venv")) {
    Write-Err "未找到 .venv，请先执行: python -m venv .venv"
    exit 1
}

$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Err "未找到虚拟环境 Python: $Python"
    exit 1
}

Write-Ok "虚拟环境存在"

& $Python -m pip check | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "依赖检查失败，请执行: .venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}
Write-Ok "依赖检查通过 (pip check)"

if (-not (Test-Path -LiteralPath "config.yaml")) {
    Write-Err "缺少 config.yaml"
    exit 1
}

$cfgCheck = @'
import sys
from pathlib import Path
import yaml

p = Path("config.yaml")
try:
    c = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
except Exception as e:
    print(f"CONFIG_ERROR::{e}")
    sys.exit(2)

v = c.get("volcengine", {})
ws = str(v.get("ws_url", "") or "")
app = str(v.get("app_key", "") or "")
access = str(v.get("access_key", "") or "")
resource = str(v.get("resource_id", "") or "")

issues = []
if not ws.startswith("wss://"):
    issues.append("ws_url 不是有效 wss 地址")
if not app.strip():
    issues.append("app_key 未正确填写")
if not access.strip():
    issues.append("access_key 未正确填写")
if not resource.strip():
    issues.append("resource_id 为空")

if issues:
    print("CONFIG_BAD::" + "；".join(issues))
    sys.exit(3)

print("CONFIG_OK")
'@

$cfgResult = & $Python -c $cfgCheck
switch ($LASTEXITCODE) {
    0 { Write-Ok "配置检查通过" }
    2 { Write-Err "config.yaml 解析失败（YAML 格式错误）"; exit 1 }
    3 { Write-Err ("配置未就绪: " + ($cfgResult -replace '^CONFIG_BAD::', '')); exit 1 }
    default { Write-Err "配置检查失败: $cfgResult"; exit 1 }
}

& $Python -c "from core.volcengine_client import VolcengineTranslator; print('ok')" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Protobuf 导入测试失败"
    exit 1
}
Write-Ok "Protobuf 导入测试通过"

$env:PYTHONIOENCODING = "utf-8"
& $Python scripts\list_devices.py | Out-Null
$env:PYTHONIOENCODING = $null
if ($LASTEXITCODE -ne 0) {
    Write-Err "无法枚举音频设备"
    exit 1
}
Write-Ok "音频设备可枚举"

$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpeg) {
    Write-Ok "FFmpeg 可用"
} else {
    Write-Warn "未检测到 FFmpeg；如果启用 zh_to_en 语音输出，运行时会降级关闭该通道"
}

Write-Host ""
Write-Ok "Windows 健康检查完成，可执行: .venv\Scripts\python.exe main.py"
