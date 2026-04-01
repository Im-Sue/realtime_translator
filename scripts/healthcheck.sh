#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

ok() { echo "✅ $1"; }
warn() { echo "⚠️  $1"; }
err() { echo "❌ $1"; }

if [[ ! -d .venv ]]; then
  err "未找到 .venv，请先创建虚拟环境。"
  exit 1
fi

source .venv/bin/activate

ok "虚拟环境存在"

python -m pip check >/dev/null && ok "依赖检查通过 (pip check)" || {
  err "依赖检查失败，请执行: python -m pip install -r requirements.txt"
  exit 1
}

if [[ ! -f config.yaml ]]; then
  err "缺少 config.yaml"
  exit 1
fi

set +e
cfg_output=$(python - <<'PY'
import yaml, sys
from pathlib import Path

p = Path('config.yaml')
try:
    c = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
except Exception as e:
    print(f"CONFIG_ERROR::{e}")
    sys.exit(2)

v = c.get('volcengine', {})
ws = str(v.get('ws_url', '') or '')
app = str(v.get('app_key', '') or '')
access = str(v.get('access_key', '') or '')
resource = str(v.get('resource_id', '') or '')

issues = []
if not ws.startswith('wss://'):
    issues.append('ws_url 不是有效 wss 地址')
if 'REPLACE_ME' in ws or ws.strip() == '':
    issues.append('ws_url 仍是占位符')
for name, val in [('app_key', app), ('access_key', access)]:
    if val.strip() == '' or 'REPLACE_ME' in val or '在这里填' in val:
        issues.append(f'{name} 未正确填写')
if not resource:
    issues.append('resource_id 为空')

if issues:
    print('CONFIG_BAD::' + '；'.join(issues))
    sys.exit(3)

print('CONFIG_OK')
PY
)
status=$?
set -e

if [[ $status -eq 2 ]]; then
  err "config.yaml 解析失败（YAML 格式错误）"
  exit 1
elif [[ $status -eq 3 ]]; then
  err "配置未就绪: ${cfg_output#CONFIG_BAD::}"
  exit 1
elif [[ $status -ne 0 ]]; then
  err "配置检查失败: ${cfg_output}"
  exit 1
else
  ok "配置检查通过"
fi

if python test_pb2_imports.py >/dev/null 2>&1; then
  ok "Protobuf 导入测试通过"
else
  err "Protobuf 导入测试失败"
  exit 1
fi

if python list_devices.py >/dev/null 2>&1; then
  ok "音频设备可枚举"
else
  err "无法枚举音频设备"
  exit 1
fi

echo
ok "健康检查完成，可启动同传：scripts/run.sh"
