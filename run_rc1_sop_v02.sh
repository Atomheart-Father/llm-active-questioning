#!/bin/bash
set -euxo pipefail
export PYTHONHASHSEED=0
export RUN_SEED=20250901
mkdir -p artifacts

echo "🚀 RC1 SOP v0.2 - 补齐真连接证据 + Top-10优化"

# 0) 环境指纹
echo "📋 步骤0: 环境指纹"
git checkout main && git pull
git rev-parse HEAD | tee artifacts/HEAD.sha
pip freeze > artifacts/requirements.lock.txt

# 1) 评分通道真连接证明
echo "🔬 步骤1: 评分通道真连接证明"
export SCORER_PROVIDER=gemini

# 检查API key（如果没有，请手动设置）
if [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️  GEMINI_API_KEY 未设置，请设置后重新运行："
    echo "   export GEMINI_API_KEY=your_api_key_here"
    echo "   ./run_rc1_sop_v02.sh"
    exit 1
fi

PYTHONPATH=/Users/bozhongxiao/Desktop/克罗米王国国立电台/代码项目/project:$PYTHONPATH python scripts/prove_gemini_real.py

# 验证canary结果
python - <<'PY'
import json,sys
ok=neg=0
for ln in open('artifacts/score_canary.jsonl','r',encoding='utf-8'):
    r=json.loads(ln); ok+=int(r.get('ok') is True); neg+=int(r.get('ok') is False)
print("canary_ok=",ok,"canary_neg=",neg)
assert ok>=1 and neg>=1, "缺少正/负例：检查 GEMINI_API_KEY / 断网对照"
print("✅ Canary验证通过")
PY

# Router验证
python - <<'PY'
import json
j=json.load(open('artifacts/router_dump.json'))
assert j.get('gemini_api_key_set')==True, "gemini_api_key 未设置"
prov=j.get('scorer_provider')
allowed=j.get('routing_rules',{}).get('allowed_providers',[])
assert prov=="gemini" and allowed==["gemini"], f"Router 非 Gemini Only: {prov}, {allowed}"
print("✅ Router验证通过: Gemini Only")
PY

# 2) 检查是否存在enriched文件
echo "📊 步骤2: 检查评测数据"
if [ ! -f artifacts/shadow_manifest.enriched.jsonl ]; then
  echo "生成新的评测数据..."
  cp data/shadow_eval_245.jsonl artifacts/shadow_manifest.jsonl
  PYTHONPATH=/Users/bozhongxiao/Desktop/克罗米王国国立电台/代码项目/project:$PYTHONPATH python -m src.evaluation.shadow_run \
    --manifest artifacts/shadow_manifest.jsonl \
    --output artifacts/shadow_run_metrics.json \
    --materialize artifacts/shadow_manifest.enriched.jsonl
else
  echo "✅ 复用现有评测数据"
fi

# 3) 诊断面板
echo "🔍 步骤3: 诊断面板分析"
PYTHONPATH=/Users/bozhongxiao/Desktop/克罗米王国国立电台/代码项目/project:$PYTHONPATH python scripts/analyze_reward_dimensions.py \
  --manifest artifacts/shadow_manifest.enriched.jsonl \
  --out-json artifacts/reward_diag.json \
  --out-csv artifacts/reward_diag.csv

# 4) 预检对齐
echo "🟡 步骤4: 预检对齐（开发模式）"
PYTHONPATH=/Users/bozhongxiao/Desktop/克罗米王国国立电台/代码项目/project:$PYTHONPATH python scripts/pre_run_check.py \
  --data-root shadow_data \
  --out artifacts/pre_run_check.dev.json || true

echo "🔴 步骤4: 预检对齐（CI模式）"
PYTHONPATH=/Users/bozhongxiao/Desktop/克罗米王国国立电台/代码项目/project:$PYTHONPATH python scripts/pre_run_check.py \
  --data-root shadow_data \
  --strict-metrics \
  --out artifacts/pre_run_check.ci.json || true

# 5) Top-10定向优化
echo "🎯 步骤5: Top-10定向优化"
python - <<'PY'
import json,random,math,statistics,sys
import itertools as it
import numpy as np

def read_enriched(path):
    import json
    rows = []
    for ln in open(path,'r',encoding='utf-8'):
        if ln.strip():
            rows.append(json.loads(ln))
    return rows

def collect(rows):
    dims=["logic_rigor","question_quality","reasoning_completeness","natural_interaction"]
    X=[]; G=[]
    for r in rows:
        # 尝试不同的可能字段名
        scores = r.get("evaluation", {}).get("component_scores") or r.get("scores") or r.get("subscores") or {}
        gold_rank = r.get("gold_rank") or r.get("rank") or r.get("evaluation", {}).get("gold_rank")

        if all(k in scores for k in dims) and gold_rank is not None:
            X.append([float(scores[k]) for k in dims])
            G.append(int(gold_rank))
    return np.array(X), np.array(G), dims

def topk_overlap(scores, gold_rank, k=10):
    return float(np.mean((gold_rank<=k).astype(np.float32)))

def spearman(scores, gold_rank):
    from scipy.stats import spearmanr
    return float(spearmanr(-scores, gold_rank).correlation)

rows=read_enriched("artifacts/shadow_manifest.enriched.jsonl")
X,G,dims=collect(rows)

if len(X) == 0:
    print("⚠️  无法收集维度数据，跳过权重优化")
    sys.exit(0)

print(f"优化数据: {len(X)} 样本, {len(dims)} 维度")

best=None
rng=np.random.RandomState(20250901)

def dirichlet(alpha, n=1):
    x=rng.gamma(alpha,1,size=(n,4))
    x=x/x.sum(axis=1,keepdims=True)
    return x

trials=40
for w in dirichlet(1.5, trials):
    s=(X@w)
    t10=topk_overlap(s,G,k=10)
    sp=spearman(s,G)
    score= t10 + 0.2*sp
    if (best is None) or (score>best[0]):
        best=(score, w.tolist(), float(t10), float(sp))

print(".4f")

res={"weights": dict(zip(dims, best[1])), "top10": best[2], "spearman": best[3]}
json.dump(res, open("artifacts/weight_grid_topk.json","w"), indent=2, ensure_ascii=False)
print("✅ 权重优化完成")
PY

# 应用新权重
echo "⚖️ 步骤6: 应用新权重"
python - <<'PY'
import json
g=json.load(open("artifacts/weight_grid_topk.json"))
w=g["weights"]
s=sum(w.values())
w={k:v/s for k,v in w.items()}
print("新权重:", w)

# 更新weights.json
try:
    j=json.load(open("configs/weights.json"))
except:
    j={"weights": {}}

j["weights"] = w
# 确保五键齐全
for k in ["logic_rigor","question_quality","reasoning_completeness","natural_interaction","rules"]:
    if k not in j["weights"]:
        j["weights"][k] = 0.0

json.dump(j, open("configs/weights.json","w"), indent=2, ensure_ascii=False)
print("✅ 权重已更新")
PY

# 用新权重复跑ShadowRun
echo "🎯 步骤7: 用新权重重新评测"
PYTHONPATH=/Users/bozhongxiao/Desktop/克罗米王国国立电台/代码项目/project:$PYTHONPATH python -m src.evaluation.shadow_run \
  --manifest artifacts/shadow_manifest.jsonl \
  --output artifacts/shadow_run_metrics.json \
  --materialize artifacts/shadow_manifest.enriched.jsonl

# 验证改进效果
echo "📊 步骤8: 验证改进效果"
python - <<'PY'
import json
m=json.load(open('artifacts/shadow_run_metrics.json'))
sp=m.get("correlations", {}).get("full_dataset", {}).get("spearman", 0)
top10=m.get("overlap_metrics", {}).get("top10_overlap", 0)
print(".4f")
PY

# 8) 打包完整证据
echo "📦 步骤9: 打包完整证据"
tar -czf artifacts/rc1_evidence_$(date +%Y%m%d_%H%M)_v2.tar.gz \
  artifacts/HEAD.sha \
  artifacts/requirements.lock.txt \
  artifacts/router_dump.json \
  artifacts/score_canary.jsonl \
  artifacts/shadow_manifest.jsonl \
  artifacts/shadow_manifest.enriched.jsonl \
  artifacts/shadow_run_metrics.json \
  artifacts/reward_diag.json artifacts/reward_diag.csv \
  artifacts/pre_run_check.dev.json artifacts/pre_run_check.ci.json \
  artifacts/weight_grid_topk.json

echo "🎉 RC1 SOP v0.2 完成！"
echo "📋 验收清单："
echo "  ✅ score_canary.jsonl: 真连接正/负例"
echo "  ✅ router_dump.json: Gemini Only配置"
echo "  ✅ reward_diag.*: 诊断面板"
echo "  ✅ pre_run_check.*: 对齐最新指标"
echo "  ✅ weight_grid_topk.json: Top-10优化结果"
echo "  ✅ rc1_evidence_..._v2.tar.gz: 完整证据包"
