#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ ! -d .venv ]]; then
  echo "❌ 未找到 .venv。先执行：/usr/local/bin/python3.12 -m venv .venv"
  exit 1
fi

source .venv/bin/activate

echo "🔍 先执行健康检查..."
bash scripts/healthcheck.sh

echo
echo "🚀 启动同声传译 main_v2.py ..."
exec python main_v2.py
