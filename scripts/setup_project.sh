#!/bin/bash
# LLM主动提问与推理增强系统 - 项目初始化脚本

set -e  # 遇到错误时退出

echo "🚀 开始初始化 LLM主动提问与推理增强系统..."

# 检查Python版本
echo "🔍 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，请先安装Python 3.9+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Python版本: $PYTHON_VERSION"

if [[ $(echo "$PYTHON_VERSION < 3.9" | bc -l) -eq 1 ]]; then
    echo "⚠️  建议使用Python 3.9+以获得最佳性能"
fi

# 创建虚拟环境
echo "📦 创建虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ 虚拟环境创建成功"
else
    echo "✅ 虚拟环境已存在"
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# 升级pip
echo "⬆️  升级pip..."
pip install --upgrade pip

# 安装依赖
echo "📥 安装项目依赖..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✅ 依赖安装完成"
else
    echo "❌ requirements.txt 文件不存在"
    exit 1
fi

# 安装项目本身（开发模式）
echo "🛠️  安装项目（开发模式）..."
pip install -e .

# 创建必要的目录
echo "📁 创建项目目录结构..."
mkdir -p logs
mkdir -p data/cache
mkdir -p checkpoints
mkdir -p models/downloaded
echo "✅ 目录结构创建完成"

# 验证安装
echo "🧪 验证安装..."
python3 -c "
try:
    import torch
    import transformers
    import datasets
    print('✅ 核心依赖验证成功')
    
    # 检查GPU支持
    if torch.cuda.is_available():
        print('✅ CUDA GPU 可用')
    elif torch.backends.mps.is_available():
        print('✅ Apple Silicon MPS 可用')
    else:
        print('ℹ️  仅CPU可用（性能可能较慢）')
        
except ImportError as e:
    print(f'❌ 依赖验证失败: {e}')
    exit(1)
"

# 运行快速测试
echo "⚡ 运行快速功能测试..."
if [ -f "scripts/quick_test.py" ]; then
    python scripts/quick_test.py
else
    echo "⚠️  快速测试脚本不存在，跳过测试"
fi

echo ""
echo "🎉 项目初始化完成！"
echo ""
echo "📋 下一步操作："
echo "   1. 配置API密钥（如需要）:"
echo "      export GEMINI_API_KEY='your-api-key'"
echo ""
echo "   2. 运行示例测试:"
echo "      python multi_turn_system.py"
echo ""
echo "   3. 生成训练数据:"
echo "      python dataset_expansion.py"
echo ""
echo "   4. 查看项目文档:"
echo "      cat README.md"
echo ""
echo "💡 提示: 记得激活虚拟环境: source venv/bin/activate"
echo "🚀 开始您的AI研究之旅！"
