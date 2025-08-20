#!/bin/bash

# LLM人机协作训练脚本

echo "========================================="
echo "LLM Human Collaboration Training"
echo "========================================="

# 检查Python环境
if ! command -v python &> /dev/null; then
    echo "错误: 未找到Python环境"
    exit 1
fi

# 进入项目目录
cd "$(dirname "$0")/.."

# 检查依赖
echo "检查项目依赖..."
pip install -r requirements.txt

# 设置环境变量
export PYTHONPATH="$PWD:$PYTHONPATH"
export TOKENIZERS_PARALLELISM=false

# 解析命令行参数
MODE="full"
USE_MOCK=""
GENERATE_SIM=""
RESUME_FROM=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --use-mock-data)
            USE_MOCK="--use-mock-data"
            shift
            ;;
        --generate-simulation)
            GENERATE_SIM="--generate-simulation"
            shift
            ;;
        --resume-from)
            RESUME_FROM="--resume-from $2"
            shift 2
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

echo "运行模式: $MODE"
echo "使用模拟数据: ${USE_MOCK:-false}"
echo "生成模拟数据: ${GENERATE_SIM:-false}"

# 执行训练
python main.py \
    --mode "$MODE" \
    $USE_MOCK \
    $GENERATE_SIM \
    $RESUME_FROM

echo "训练脚本执行完成"
