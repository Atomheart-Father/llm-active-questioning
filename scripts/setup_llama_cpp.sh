#!/bin/bash
set -euo pipefail
# llama.cpp 环境搭建脚本
# 适用于 Apple Silicon Mac

set -e  # 遇到错误立即停止

echo "🚀 开始搭建 llama.cpp 环境..."
echo "系统信息: $(uname -m) - $(sw_vers -productName) $(sw_vers -productVersion)"

# 创建工作目录
WORK_DIR="$HOME/llama_cpp_workspace"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

echo "📁 工作目录: $WORK_DIR"

# 检查并安装 Homebrew
if ! command -v brew &> /dev/null; then
    echo "🍺 安装 Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # 添加到 PATH
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    echo "✅ Homebrew 已安装"
fi

# 安装必要依赖
echo "🔧 安装构建依赖..."
brew install cmake
brew install git

# 克隆 llama.cpp
if [ ! -d "llama.cpp" ]; then
    echo "📥 克隆 llama.cpp 仓库..."
    git clone https://github.com/ggerganov/llama.cpp.git
fi

cd llama.cpp

# 编译 llama.cpp (启用 Metal 支持)
echo "🔨 编译 llama.cpp (启用 Metal 支持)..."
make clean
make LLAMA_METAL=1 -j$(sysctl -n hw.ncpu)

# 检查编译结果
if [ -f "./main" ]; then
    echo "✅ llama.cpp 编译成功！"
    echo "📍 可执行文件位置: $(pwd)/main"
else
    echo "❌ llama.cpp 编译失败！"
    exit 1
fi

# 创建模型目录
MODELS_DIR="$WORK_DIR/models"
mkdir -p "$MODELS_DIR"

echo "📋 环境搭建完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 下一步操作指南:"
echo "1. 下载 Qwen3-4B-Thinking GGUF 模型文件"
echo "2. 将模型文件放置到: $MODELS_DIR"
echo "3. 使用以下命令测试:"
echo "   cd $WORK_DIR/llama.cpp"
echo "   ./main -m $MODELS_DIR/qwen3-4b-thinking.gguf -p \"你好，请问你能帮我解决一个数学问题吗？\" -n 100"
echo ""
echo "📂 相关路径:"
echo "   - llama.cpp 目录: $WORK_DIR/llama.cpp"
echo "   - 可执行文件: $WORK_DIR/llama.cpp/main"
echo "   - 模型目录: $MODELS_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
