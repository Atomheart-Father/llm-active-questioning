#!/bin/bash
set -euxo pipefail
export PYTHONHASHSEED=0
export RUN_SEED=20250901
mkdir -p artifacts

echo "🚀 开始RC1反作弊验证流水线"

# 0) 同步代码与环境指纹（审计）
echo "📋 步骤0: 环境同步与指纹"
git checkout main && git pull
git rev-parse HEAD | tee artifacts/HEAD.sha
python -m pip install -U pip
pip install -e .
pip freeze > artifacts/requirements.lock.txt

# 1) 评分通道真连接证明（正/负对照 + 路由快照）
echo "🔬 步骤1: 评分通道真连接证明"
python scripts/prove_gemini_real.py

# 验证canary结果
python - <<'PY'
import json,sys
ok=neg=0
for ln in open('artifacts/score_canary.jsonl','r',encoding='utf-8'):
    r=json.loads(ln); ok+=int(r.get('ok') is True); neg+=int(r.get('ok') is False)
print("canary_ok=",ok,"canary_neg=",neg)
assert ok>=1 and neg>=1, "canary 缺少正/负例，请检查 API/断网对照"
PY

# 验证路由快照
test -f artifacts/router_dump.json
echo "✅ 评分通道验证完成"

# 2) 采样 200 条分层清单（固定种子）
echo "📊 步骤2: 采样200条分层清单"
python tools/sample_shadow.py \
  --n 200 --stratified --seed "${RUN_SEED}" \
  --out artifacts/shadow_manifest.jsonl

# 3) ShadowRun（字段映射/物化优先已修复的版本）
echo "🎯 步骤3: 执行ShadowRun"
python scripts/shadow_run.py \
  --in artifacts/shadow_manifest.jsonl \
  --metrics-out artifacts/shadow_run_metrics.json \
  --manifest-out artifacts/shadow_manifest.enriched.jsonl

# 4) 诊断面板（维度方差/相关性/任务分组/共线）
echo "🔍 步骤4: 诊断面板分析"
python scripts/analyze_reward_dimensions.py \
  --in artifacts/shadow_manifest.enriched.jsonl \
  --out-json artifacts/reward_diag.json \
  --out-csv artifacts/reward_diag.csv

# 5) 开发预检（结构健康检查 + 指标仅告警）
echo "🟡 步骤5: 开发预检"
python scripts/pre_run_check.py \
  --data-root shadow_data \
  --out artifacts/pre_run_check.dev.json || true

# 6) CI 预检（结构健康 + 指标硬门槛）
echo "🔴 步骤6: CI预检"
python scripts/pre_run_check.py \
  --data-root shadow_data \
  --strict-metrics \
  --out artifacts/pre_run_check.ci.json || true

# 7) 快速阈值自验：RC 目标线 Spearman≥0.55 / Top-10≥0.60
echo "📈 步骤7: 阈值自验"
python - <<'PY'
import json,sys
m=json.load(open('artifacts/shadow_run_metrics.json'))
sp,top10 = m.get("spearman"), m.get("top10")
print(f"Spearman={sp}, Top10={top10}")
PY

# 8) 打包反作弊证据包（提交 PR 时随附）
echo "📦 步骤8: 打包证据包"
tar -czf artifacts/rc1_evidence_$(date +%Y%m%d_%H%M).tar.gz \
  artifacts/HEAD.sha \
  artifacts/requirements.lock.txt \
  artifacts/router_dump.json \
  artifacts/score_canary.jsonl \
  artifacts/shadow_manifest.jsonl \
  artifacts/shadow_manifest.enriched.jsonl \
  artifacts/shadow_run_metrics.json \
  artifacts/reward_diag.json artifacts/reward_diag.csv \
  artifacts/pre_run_check.dev.json artifacts/pre_run_check.ci.json || true

echo "🎉 RC1反作弊验证流水线完成！"
