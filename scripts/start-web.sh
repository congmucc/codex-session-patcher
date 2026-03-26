#!/bin/bash
# Codex Session Patcher Web UI 启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 Codex Session Patcher Web UI"
echo "================================"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 未安装"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装，请先安装 Node.js"
    exit 1
fi

# 安装 Python 依赖
echo "📦 安装 Python 依赖..."
cd "$PROJECT_DIR"
pip install -e ".[web]" -q

# 安装前端依赖
echo "📦 安装前端依赖..."
cd "$PROJECT_DIR/web/frontend"
if [ ! -d "node_modules" ]; then
    npm install
fi

# 构建前端
echo "🔨 构建前端..."
npm run build

# 启动后端服务
echo "🌐 启动服务..."
echo ""
echo "访问地址: http://127.0.0.1:8080"
echo "按 Ctrl+C 停止服务"
echo ""

cd "$PROJECT_DIR"
python -m web.backend.main
