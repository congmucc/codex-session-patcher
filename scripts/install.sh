#!/bin/bash
# Codex Session Patcher 安装脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

source "$SCRIPT_DIR/web-common.sh"

echo "=== Codex Session Patcher 安装脚本 ==="

PYTHON_BIN="$(web_pick_python_bin || true)"
if [ -z "$PYTHON_BIN" ]; then
    echo "错误: 未找到可用的 Python 3.8+ 解释器"
    echo "已检查: python3 / python / python3.13 / python3.12 / python3.11 / python3.10 / python3.9 / python3.8 / py -3"
    exit 1
fi

echo "检测到 Python: $PYTHON_BIN ($(web_python_version_string "$PYTHON_BIN"))"

BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

SCRIPT_PATH="$PROJECT_DIR/codex_patcher.py"
TARGET_PATH="$BIN_DIR/codex-patcher"

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "错误: 未找到入口脚本 $SCRIPT_PATH"
    exit 1
fi

echo "安装路径: $TARGET_PATH"

cat > "$TARGET_PATH" << EOF
#!/bin/bash
exec "$PYTHON_BIN" "$SCRIPT_PATH" "\$@"
EOF

chmod +x "$TARGET_PATH"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo "警告: $BIN_DIR 不在 PATH 中"
    echo "请将以下内容添加到您的 shell 配置文件 (~/.bashrc 或 ~/.zshrc):"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi

echo ""
echo "=== 安装完成 ==="
echo ""
echo "使用方法:"
echo "    codex-patcher               # 执行基本清洗"
echo "    codex-patcher --auto-resume # 清洗后自动 resume"
echo "    codex-patcher --help        # 查看帮助"
echo ""
