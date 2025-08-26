#!/usr/bin/env bash
set -euo pipefail

# ============ 基本环境 ============
export PYTHONUNBUFFERED=1
export RUN_MODE=prod
export BASE_MODEL="${BASE_MODEL:-Qwen/Qwen3-4B-Thinking-2507}"
export SCORER_PROVIDER="${SCORER_PROVIDER:-gemini}"   # 可选：gemini / deepseek_r1 / openai 等
: "${SCORER_API_KEY:?请先 export SCORER_API_KEY=你的真实Key}"

# 目录就绪
mkdir -p logs reports/preflight reports/rc1 data/rollouts checkpoints/rc1/best templates/pack_v2

# 全局日志管道：所有 stdout/stderr 进入总日志 + 局部日志
exec > >(tee -a "logs/ops_$(date +%Y%m%d_%H%M%S).log") 2>&1

# 错误陷阱：一旦出错，打包关键信息用于上报
on_error () {
  echo "🚨 发生错误，正在收集最后200行日志与关键产物……"
  tail -n 200 logs/*.log || true
  tar -czf "reports/rc1/FAIL_$(date +%Y%m%d_%H%M%S).tgz" \
    logs \
    reports/preflight || true
  echo "❌ 失败归档已生成：reports/rc1/FAIL_*.tgz"
}
trap on_error ERR

# ============ 1. Python 环境与依赖 ============
if ! command -v python3 >/dev/null; then echo "❌ 缺少 python3"; exit 2; fi
PYVER=$(python3 - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)
echo "Python version: $PYVER"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip wheel
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
else
  # 最低依赖兜底（按项目需要增补）
  pip install "torch~=2.3" "transformers>=4.42" "datasets>=2.19" \
              "trl>=0.9" "peft>=0.11" "accelerate>=0.33" "evaluate>=0.4" \
              "tqdm" "numpy" "scikit-learn" "pyyaml" "jsonlines" "jinja2"
fi

# ============ 2. Git 指纹（可审计） ============
git rev-parse --is-inside-work-tree >/dev/null 2>&1 && {
  git status --porcelain > reports/rc1/git_status.txt || true
  git rev-parse HEAD > reports/rc1/git_commit.txt || true
}

# ============ 3. 资源检查 ============
python - <<'PY'
import shutil, os
free_gb = shutil.disk_usage(".").free/2**30
assert free_gb>50, f"磁盘不足：{free_gb:.1f}GB，至少需>50GB"
print(f"DISK_OK {free_gb:.1f}GB 可用")
PY

# ============ 4. 评分器真连通 + 防模拟 ============
# 4.1 探针：必须有真实延迟与可计费调用
python scripts/probe_scorer.py --n 8 --provider "$SCORER_PROVIDER" --live

# 4.2 防伪：缓存命中率首轮必须 < 90%
python scripts/assert_not_simulated.py --cache_hit_lt 0.90 --min_eval_n 50

# ============ 5. 影子评测集物化 ============
python -m src.evaluation.shadow_run --n 245 --seed 20250820 --stratify \
  --materialize data/shadow_eval_245.jsonl \
  --dump-manifest reports/rc1/sample_manifest.json
sha256sum data/shadow_eval_245.jsonl > reports/rc1/shadow_eval_245.sha256

# ============ 6. 构建种子池（按需调整n与配比） ============
python scripts/build_rollout_pool.py \
  --out data/rollouts/rc1_seed.jsonl \
  --n 30000 \
  --mix "hotpotqa:0.45,strategyqa:0.30,gsm8k:0.25" \
  --max_turns 6 --clarify_rate 0.30 \
  --tools "wiki,calc" \
  --templates_dir templates/pack_v2

# ============ 7. 多样性体检（扩量前闸门） ============
python scripts/validate_pool.py data/rollouts/rc1_seed.jsonl \
  --min_distinct2 0.60 --kl3_min 0.15 --roles_min 4 --styles_min 3 \
  --max_dup_pct 2.0 --max_len 4096 --min_len 64 \
  --leak_check data/shadow_eval_245.jsonl --leak_ngram 5 --leak_sim 0.85 \
  --by_task "hotpotqa,strategyqa,gsm8k"
sha256sum data/rollouts/rc1_seed.jsonl > reports/rc1/rc1_seed.sha256

# ============ 8. 难度指标 → 分桶 → 平衡分布 ============
python scripts/difficulty_metrics.py \
  --in data/rollouts/rc1_seed.jsonl \
  --out data/rollouts/rc1_seed.metrics.jsonl

python scripts/difficulty_bucketize.py \
  --metrics data/rollouts/rc1_seed.metrics.jsonl \
  --target "easy:0.25,medium:0.45,hard:0.30" \
  --by_task "hotpotqa,strategyqa,gsm8k" \
  --out data/rollouts/rc1_seed.balanced.jsonl

python scripts/validate_difficulty.py \
  --metrics data/rollouts/rc1_seed.metrics.jsonl \
  --balanced data/rollouts/rc1_seed.balanced.jsonl \
  --min_hard_pct 0.30 --max_easy_pct 0.30 \
  --len_max 3500 --turns_max 8 --tool_hops_max 8 \
  --clue_overlap_max_easy 0.65 --clue_overlap_min_hard 0.10 \
  --out reports/rc1/difficulty_report.json

sha256sum data/rollouts/rc1_seed.metrics.jsonl > reports/rc1/rc1_seed.metrics.sha256
sha256sum data/rollouts/rc1_seed.balanced.jsonl > reports/rc1/rc1_seed.balanced.sha256

# ============ 9. 权重文件与惩罚开关体检 ============
test -f configs/weights.json || (echo "缺少 configs/weights.json" && exit 2)
python - <<'PY'
import json,hashlib
w=json.load(open("configs/weights.json"))
wsum=sum(w["weights"].values())
assert abs(wsum-1.0)<1e-6, "weights 未归一化"
assert max(w["weights"].values())<=0.5+1e-9, "存在单维>0.5"
assert all(v>=0 for v in w["weights"].values()), "出现负权重"
print("WEIGHTS_OK",hashlib.sha256(open("configs/weights.json","rb").read()).hexdigest())
PY

grep -q "use_overclar_penalty: true" configs/ppo_scale.yaml || (echo "未启用过度澄清惩罚(use_overclar_penalty)" && exit 2)
pytest -q tests/test_overclar_penalty.py

# ============ 10. Round 1 报告聚合 ============
python - <<'PY'
import json,hashlib,datetime
def sha(p):
  import pathlib,hashlib
  try: return hashlib.sha256(open(p,"rb").read()).hexdigest()
  except: return None
r={"round":"round1","ts":datetime.datetime.utcnow().isoformat()+"Z","pass":True}
r["files"]={
  "shadow_eval":"data/shadow_eval_245.jsonl",
  "shadow_eval_sha":sha("data/shadow_eval_245.jsonl"),
  "seed_pool":"data/rollouts/rc1_seed.jsonl",
  "seed_pool_sha":sha("data/rollouts/rc1_seed.jsonl"),
  "seed_pool_balanced":"data/rollouts/rc1_seed.balanced.jsonl",
  "seed_pool_balanced_sha":sha("data/rollouts/rc1_seed.balanced.jsonl"),
  "weights":"configs/weights.json",
  "ppo_cfg":"configs/ppo_scale.yaml",
}
open("reports/preflight/round1.json","w").write(json.dumps(r,indent=2))
print("PRE-R1-REPORT: reports/preflight/round1.json")
PY

# ============ 11. Round 2 复核（更接近实战口径） ============
# 11.1 防伪：缓存命中阈值放宽到 <95%
python scripts/assert_not_simulated.py --cache_hit_lt 0.95 --min_eval_n 50

# 11.2 以当前权重/惩罚口径再跑一次影子检查（带 tag）
python -m src.evaluation.shadow_run --n 245 --seed 20250820 --stratify --tag "pre_run_check"

# 11.3 生成 Round 2 通过票
python - <<'PY'
import json,datetime,os
r={"round":"round2","ts":datetime.datetime.utcnow().isoformat()+"Z","pass":True}
open("reports/preflight/round2_pass.json","w").write(json.dumps(r,indent=2))
print("PRE-R2-REPORT: reports/preflight/round2_pass.json")
PY

# ============ 12. 只有通过后才允许启动训练 ============
test -f reports/preflight/round2_pass.json || (echo "预检未通过：禁止开跑" && exit 2)

# 接入难度感知采样
if ! grep -q 'seed_pool: "data/rollouts/rc1_seed.balanced.jsonl"' configs/ppo_scale.yaml; then
  echo "⚠️ 你尚未将 balanced 种子池写入 configs/ppo_scale.yaml：seed_pool: \"data/rollouts/rc1_seed.balanced.jsonl\""
  echo "⚠️ priority_sampling.by_difficulty 建议 {easy:0.2, medium:0.4, hard:0.4}"
fi

# 训练启动（断点续训：如需恢复，加 --resume-from checkpoints/rc1/latest ）
python -m train.ppo_runner --config configs/ppo_scale.yaml | tee -a logs/train.log
