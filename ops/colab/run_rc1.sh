#!/usr/bin/env bash
set -euo pipefail
source "/content/drive/MyDrive/llm-aq/env/env.sh"
cd /content/repo

# 把日志/ckpt都指向Drive，断线也不丢
export OUTPUT_DIR="/content/drive/MyDrive/llm-aq"
export LOG_DIR="$OUTPUT_DIR/logs"
export CKPT_DIR="$OUTPUT_DIR/checkpoints"
export REPORT_DIR="$OUTPUT_DIR/reports"
mkdir -p "$LOG_DIR" "$CKPT_DIR" "$REPORT_DIR"

# 先跑影子评估（如果你还没准备好训练）
if [ "${ONLY_EVAL:-0}" = "1" ]; then
  echo "==> ONLY_EVAL=1：仅运行影子评估（若脚本存在）"
  python -m src.evaluation.shadow_run --n 245 --seed 20250820 --stratify || echo "shadow_run missing"
  exit 0
fi

# 正式训练（请替换为你仓库中的训练入口）
if [ -f "train/ppo_runner.py" ]; then
  echo "==> 启动训练：ppo_runner.py"
  python -m train.ppo_runner --config configs/ppo_scale.yaml 2>&1 | tee -a "$LOG_DIR/train.log"
else
  echo "ERROR: 未找到 train/ppo_runner.py，请把训练入口换成你仓库里的命令。"
  exit 2
fi
