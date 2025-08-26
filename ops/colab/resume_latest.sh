#!/usr/bin/env bash
set -euo pipefail
source "/content/drive/MyDrive/llm-aq/env/env.sh"
cd /content/repo

export OUTPUT_DIR="/content/drive/MyDrive/llm-aq"
export CKPT_DIR="$OUTPUT_DIR/checkpoints"
export LOG_DIR="$OUTPUT_DIR/logs"
mkdir -p "$LOG_DIR"

LATEST=$(ls -1dt "$CKPT_DIR"/* 2>/dev/null | head -n1 || true)
if [ -z "$LATEST" ]; then
  echo "未发现 checkpoints，改为首次启动："
  bash ops/colab/run_rc1.sh
  exit 0
fi

echo "==> 从断点恢复：$LATEST"
if [ -f "train/ppo_runner.py" ]; then
  python -m train.ppo_runner --config configs/ppo_scale.yaml --resume "$LATEST" 2>&1 | tee -a "$LOG_DIR/train_resume.log"
else
  echo "ERROR: 未找到 train/ppo_runner.py"
  exit 2
fi
