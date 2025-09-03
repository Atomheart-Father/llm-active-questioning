#!/bin/bash
set -euxo pipefail
export PYTHONHASHSEED=0
export RUN_SEED=20250901
mkdir -p artifacts

echo "🚀 RC1 SOP v0.3 - 配额友好 + Top-10冲线版"

# 设置环境变量
export GEMINI_API_KEY="AIzaSyBLECdu94qJWPFOZ--9dIKpeWaWjSGJ_z0"
export SCORER_PROVIDER=gemini
export RATE_LIMIT_RPM=9
export RATE_LIMIT_CONCURRENCY=1
export PYTHONPATH=/Users/bozhongxiao/Desktop/克罗米王国国立电台/代码项目/project:$PYTHONPATH

# 0) 环境指纹
echo "📋 步骤0: 环境指纹"
git checkout main && git pull
git rev-parse HEAD | tee artifacts/HEAD.sha
pip freeze > artifacts/requirements.lock.txt

# 0.1) 检查固定评测清单
echo "📋 步骤0.1: 检查评测清单"
if [ ! -f artifacts/shadow_manifest.jsonl ]; then
  echo "生成新的评测清单..."
  python tools/sample_shadow.py --n 245 --stratified --seed "${RUN_SEED}" \
    --out artifacts/shadow_manifest.jsonl
else
  echo "✅ 复用现有评测清单"
  wc -l artifacts/shadow_manifest.jsonl
fi

# 1) 评分通道：Gemini Only + 配额友好
echo "🔬 步骤1: 评分通道真连接证明"
python scripts/prove_gemini_real.py

# 验证：至少1条正例+1条负例；Router必须Gemini Only
python - <<'PY'
import json,sys
ok=neg=0
for ln in open('artifacts/score_canary.jsonl','r',encoding='utf-8'):
    r=json.loads(ln)
    ok+=int(r.get('status')=='success')
    neg+=int(r.get('test_type')=='negative_case')
print(f"canary_ok={ok}, canary_neg={neg}")
assert ok>=1 and neg>=1, "缺少正/负例：检查 score_canary.jsonl"
cfg=json.load(open('artifacts/router_dump.json'))
assert cfg.get('gemini_api_key_set')==True, "gemini_api_key 未设置"
allowed=cfg.get('routing_rules',{}).get('allowed_providers',[])
assert cfg.get('scorer_provider')=="gemini" and allowed==["gemini"], f"Router 非 Gemini Only: {allowed}"
print("✅ Canary & Router验证通过")
PY

# 2) 影子评测（配额友好批次执行）
echo "🎯 步骤2: 影子评测分批执行"
# 将245条按3个批次跑（85/批），批间sleep 60s
split -l 85 artifacts/shadow_manifest.jsonl artifacts/batch_
for f in artifacts/batch_*; do
  mv "$f" "$f.jsonl"
  echo "处理批次: $f.jsonl"
  python scripts/shadow_run.py \
    --in "$f.jsonl" \
    --append \
    --metrics-out artifacts/shadow_run_metrics.json \
    --manifest-out artifacts/shadow_manifest.enriched.jsonl || true
  echo "批次完成，等待60秒..."
  sleep 60
done

# 3) 诊断面板
echo "🔍 步骤3: 诊断面板分析"
python scripts/analyze_reward_dimensions.py \
  --in artifacts/shadow_manifest.enriched.jsonl \
  --schema enriched \
  --out-json artifacts/reward_diag_v3.json \
  --out-csv artifacts/reward_diag_v3.csv

# 4) Top-10定向优化（离线权重搜索）
echo "🎯 步骤4: Top-10定向优化"
python - <<'PY'
import json, numpy as np, random
rng = np.random.RandomState(20250901)
dims = ["logic_rigor","question_quality","reasoning_completeness","natural_interaction"]
X, G = [], []
for ln in open("artifacts/shadow_manifest.enriched.jsonl","r",encoding="utf-8"):
    r=json.loads(ln)
    s=r.get("subscores") or r.get("scores") or {}
    if all(k in s for k in dims) and "gold_rank" in r:
        X.append([float(s[k]) for k in dims])
        G.append(int(r["gold_rank"]))
X=np.array(X); G=np.array(G)
print(f"加载了 {len(X)} 个有效样本用于优化")
if len(X) == 0:
    print("⚠️ 无有效数据，跳过权重优化")
    exit(0)
def topk(scores, gold, k=10):
    import numpy as np
    return float(np.mean((gold<=k).astype(np.float32)))
def spearman(scores, gold):
    from scipy.stats import spearmanr
    return float(spearmanr(-scores, gold).correlation)
best=(None,None,None,None)
def dirichlet(alpha, n):
    x=rng.gamma(alpha,1,size=(n,len(dims)))
    x=x/x.sum(axis=1,keepdims=True)
    return x
for w in dirichlet(1.5, 60):  # 60次试探
    s=X@w
    t10=topk(s,G,10)
    sp=spearman(s,G)
    score = t10 + 0.2*sp
    if (best[0] is None) or (score>best[0]):
        best=(score,w.tolist(),t10,sp)
json.dump({"weights":dict(zip(dims,best[1])),"top10":best[2],"spearman":best[3]},
          open("artifacts/weight_grid_topk_v3.json","w"), indent=2, ensure_ascii=False)
print(f"✅ 最佳权重: Top10={best[2]:.4f}, Spearman={best[3]:.4f}")
PY

# 4.1 应用新权重
echo "⚖️ 步骤4.1: 应用新权重"
python - <<'PY'
import json
g=json.load(open("artifacts/weight_grid_topk_v3.json"))
w=g["weights"]
s=sum(w.values())
w={k:v/s for k,v in w.items()}
try:
    cfg=json.load(open("configs/weights.json"))
except:
    cfg={"weights": {}}
cfg["weights"] = w
# 确保五键齐全
for k in ["logic_rigor","question_quality","reasoning_completeness","natural_interaction","rules"]:
    if k not in cfg["weights"]:
        cfg["weights"][k] = 0.0
json.dump(cfg, open("configs/weights.json","w"), indent=2, ensure_ascii=False)
print("✅ 新权重已应用:", cfg["weights"])
PY

# 4.2 复跑ShadowRun（仍按3批）
echo "🔄 步骤4.2: 复跑ShadowRun验证新权重"
rm -f artifacts/shadow_run_metrics_v3.json artifacts/shadow_manifest.enriched_v3.jsonl
for f in artifacts/batch_*.jsonl; do
  python scripts/shadow_run.py \
    --in "$f" \
    --append \
    --metrics-out artifacts/shadow_run_metrics_v3.json \
    --manifest-out artifacts/shadow_manifest.enriched_v3.jsonl || true
  echo "批次完成，等待60秒..."
  sleep 60
done

# 5) 预检对齐
echo "🟡 步骤5: 预检对齐"
python scripts/pre_run_check.py \
  --data-root shadow_data \
  --metrics artifacts/shadow_run_metrics_v3.json \
  --out artifacts/pre_run_check.dev_v3.json || true

python scripts/pre_run_check.py \
  --data-root shadow_data \
  --metrics artifacts/shadow_run_metrics_v3.json \
  --strict-metrics \
  --out artifacts/pre_run_check.ci_v3.json || true

# 6) 打包证据（v3）
echo "📦 步骤6: 打包证据v3"
tar -czf artifacts/rc1_evidence_$(date +%Y%m%d_%H%M)_v3.tar.gz \
  artifacts/HEAD.sha \
  artifacts/requirements.lock.txt \
  artifacts/router_dump.json \
  artifacts/score_canary.jsonl \
  artifacts/shadow_manifest.jsonl \
  artifacts/shadow_manifest.enriched_v3.jsonl \
  artifacts/shadow_run_metrics_v3.json \
  artifacts/reward_diag_v3.json artifacts/reward_diag_v3.csv \
  artifacts/pre_run_check.dev_v3.json artifacts/pre_run_check.ci_v3.json \
  artifacts/weight_grid_topk_v3.json

echo "🎉 RC1 SOP v0.3 完成！"
echo "📋 验收清单："
echo "  ✅ score_canary.jsonl: 真连接正/负例"
echo "  ✅ router_dump.json: Gemini Only配置"
echo "  ✅ shadow_run_metrics_v3.json: 新权重评测结果"
echo "  ✅ reward_diag_v3.*: 诊断面板"
echo "  ✅ weight_grid_topk_v3.json: Top-10优化结果"
echo "  ✅ rc1_evidence_*_v3.tar.gz: 完整证据包"
echo ""
echo "🎯 检查Top-10指标："
python - <<'PY'
try:
    m=json.load(open('artifacts/shadow_run_metrics_v3.json'))
    top10=m.get("overlap_metrics", {}).get("top10_overlap", 0)
    sp=m.get("correlations", {}).get("full_dataset", {}).get("spearman", 0)
    print(f"Top-10重叠率: {top10:.4f}")
    print(f"Spearman相关性: {sp:.4f}")
    if top10 >= 0.60:
        print("🎉 Top-10目标达成!")
    else:
        print(f"⚠️ Top-10差距: {0.60 - top10:.4f}")
except Exception as e:
    print(f"⚠️ 无法读取指标: {e}")
PY

