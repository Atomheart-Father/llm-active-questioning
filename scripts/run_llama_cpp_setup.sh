#!/bin/bash
# 一键设置 llama.cpp + Qwen3-4B-Thinking 环境
# 包含编译、下载、测试的完整流程

set -e
echo "🚀 LLM主动提问系统 - llama.cpp 环境一键设置"
echo "=============================================="

# 检查当前目录
if [[ ! -f "scripts/setup_llama_cpp.sh" ]]; then
    echo "❌ 请在项目根目录运行此脚本"
    exit 1
fi

# 步骤1: 搭建 llama.cpp 环境
echo "📋 步骤 1/3: 搭建 llama.cpp 环境"
echo "执行: ./scripts/setup_llama_cpp.sh"
./scripts/setup_llama_cpp.sh

if [[ $? -ne 0 ]]; then
    echo "❌ llama.cpp 环境搭建失败"
    exit 1
fi

echo "✅ llama.cpp 环境搭建完成"
echo ""

# 步骤2: 下载模型
echo "📋 步骤 2/3: 下载 Qwen3-4B-Thinking 模型"
echo "执行: python scripts/download_qwen_model.py"
python scripts/download_qwen_model.py

echo "ℹ️ 如果自动下载失败，请按照提示手动下载模型文件"
echo ""

# 步骤3: 测试推理
echo "📋 步骤 3/3: 测试推理性能"
echo "执行: python scripts/test_qwen_inference.py"

# 检查模型文件是否存在
MODELS_DIR="$HOME/llama_cpp_workspace/models"
if [[ $(find "$MODELS_DIR" -name "*.gguf" 2>/dev/null | wc -l) -eq 0 ]]; then
    echo "⚠️ 未找到 GGUF 模型文件，跳过推理测试"
    echo "请先下载模型文件到: $MODELS_DIR"
else
    python scripts/test_qwen_inference.py
    
    if [[ $? -eq 0 ]]; then
        echo "🎉 推理测试完成！"
    else
        echo "⚠️ 推理测试遇到问题，请检查日志"
    fi
fi

echo ""
echo "=============================================="
echo "🎯 llama.cpp 环境设置完成！"
echo ""
echo "📂 相关路径:"
echo "   - llama.cpp: $HOME/llama_cpp_workspace/llama.cpp"
echo "   - 模型目录: $HOME/llama_cpp_workspace/models"
echo ""
echo "🔧 手动测试命令:"
echo "   cd $HOME/llama_cpp_workspace/llama.cpp"
echo "   ./main -m ../models/你的模型文件.gguf -p \"测试问题\" -n 100"
echo ""
echo "📊 查看测试结果:"
echo "   cat qwen_llama_cpp_test_results_*.json"
echo "=============================================="
