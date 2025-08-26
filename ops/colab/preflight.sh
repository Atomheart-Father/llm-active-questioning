#!/usr/bin/env bash
set -euo pipefail
source "/content/drive/MyDrive/llm-aq/env/env.sh"

cd /content/repo

echo "==> 预检：权重文件/过度澄清惩罚/打分器连通性/磁盘空间等（按你仓库已有脚本执行）"

# 1) 权重文件校验（如脚本不存在会被跳过）
test -f configs/weights.json && python - <<'PY'
import json,sys
w=json.load(open("configs/weights.json"))
s=sum(w["weights"].values())
assert abs(s-1.0)<1e-6, "weights not normalized"
assert max(w["weights"].values())<=0.5+1e-9, "a single dim > 0.5"
print("weights.json OK")
PY

# 2) 过度澄清惩罚单测（若你的 tests 存在）
pytest -q tests/test_overclar_penalty.py || echo "WARN: overclar test missing or failed"

# 3) 打分器探针（若你有该脚本）
if [ -n "${SCORER_PROVIDER:-}" ]; then
  echo "==> scorer probe"
  python scripts/probe_scorer.py --n 4 --provider "$SCORER_PROVIDER" --live || echo "WARN: probe failed or script missing"
fi

# 4) 磁盘余量
python - <<'PY'
import shutil
free_gb = shutil.disk_usage(".").free/2**30
print(f"Free disk: {free_gb:.1f} GB")
PY

echo "==> 预检完成（存在的都跑了）。"
