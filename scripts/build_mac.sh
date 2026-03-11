#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "ERR  未找到 .venv/bin/python，请先在 macOS 上创建虚拟环境"
  exit 1
fi

echo "==> 清理旧的 build/dist"
rm -rf build dist

echo "==> 执行 PyInstaller 打包"
.venv/bin/python -m PyInstaller --clean --noconfirm realtime_translator_mac.spec

APP_DIR="$PROJECT_DIR/dist/realtime_translator.app"
if [[ ! -d "$APP_DIR" ]]; then
  echo "ERR  未找到 .app 输出目录: $APP_DIR"
  exit 1
fi

DIST_DIR="$PROJECT_DIR/dist/realtime_translator_support"
mkdir -p "$DIST_DIR"

echo "==> 整理运行所需配置文件"
cp config.yaml.example "$DIST_DIR/config.yaml.example"
if [[ -f config.yaml ]]; then
  cp config.yaml "$DIST_DIR/config.yaml"
fi

echo "==> 复制辅助脚本与说明"
cp README.md "$DIST_DIR/README.md"
cp README_EN.md "$DIST_DIR/README_EN.md"
cp scripts/healthcheck.sh "$DIST_DIR/healthcheck.sh"

echo "==> 生成说明文件"
cat > "$DIST_DIR/START_MAC.txt" <<'EOF'
1. 将 realtime_translator.app 拖到 Applications 或任意目录
2. 将本目录中的 config.yaml.example 复制为 config.yaml 并填写凭据
3. 首次启动若被系统拦截，请在“系统设置 -> 隐私与安全性”中允许运行
4. 如需 Channel 1 语音输出，请额外安装 FFmpeg 并保证可在 PATH 中找到
EOF

echo
echo "OK  macOS 打包完成:"
echo "OK  App: $APP_DIR"
echo "OK  Support files: $DIST_DIR"
exit 0
