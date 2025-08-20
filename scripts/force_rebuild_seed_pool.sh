#!/bin/bash
# 强制重建种子池 - 修复多样性和难度问题
# 按总架构师要求的严格标准

set -e  # 任何错误立即退出

echo "🧪 强制重建种子池（多样性+难度增强）"
echo "=" * 60

# 检查环境
if [ -z "$RUN_MODE" ] || [ "$RUN_MODE" != "prod" ]; then
    echo "❌ 必须在生产环境执行"
    exit 1
fi

# 备份旧数据
if [ -f "data/rollouts/rc1_seed.jsonl" ]; then
    echo "📦 备份旧种子池..."
    mv data/rollouts/rc1_seed.jsonl data/rollouts/rc1_seed.backup.$(date +%s).jsonl
fi

# 重新生成种子池（启用所有多样性增强）
echo "🔄 重新生成30k种子池（多样性增强）..."
python scripts/build_rollout_pool.py \
    --out data/rollouts/rc1_seed.jsonl \
    --n 30000 \
    --mix "hotpotqa:0.45,strategyqa:0.30,gsm8k:0.25" \
    --max_turns 6 \
    --clarify_rate 0.35 \
    --tools "wiki,calc" \
    --templates_dir templates/pack_v2 \
    --min_roles 4 \
    --min_styles 3 \
    --role_style_balanced \
    --distinct_prompts \
    --min_tool_hops 3 \
    --force_multihop \
    --ops_numeric_min 3 \
    --connector_target hard \
    --entity_permute 0.3 \
    --distractor_injection 0.25

echo "✅ 种子池重新生成完成"

# 严格质量验证
echo "🔍 执行严格质量验证..."
python scripts/validate_pool.py data/rollouts/rc1_seed.jsonl \
    --min_distinct2 0.60 \
    --kl3_min 0.15 \
    --roles_min 4 \
    --styles_min 3 \
    --max_dup_pct 2.0 \
    --max_len 4096 \
    --min_len 64 \
    --leak_check data/shadow_eval_245.jsonl \
    --leak_ngram 5 \
    --leak_sim 0.85 \
    --by_task "hotpotqa,strategyqa,gsm8k"

if [ $? -ne 0 ]; then
    echo "❌ 质量验证失败！"
    exit 1
fi

# 难度指标提取
echo "📊 提取难度指标..."
python scripts/difficulty_metrics.py \
    --in data/rollouts/rc1_seed.jsonl \
    --out data/rollouts/rc1_seed.metrics.jsonl

# 难度分桶与平衡
echo "⚖️ 难度分桶与平衡..."
python scripts/difficulty_bucketize.py \
    --metrics data/rollouts/rc1_seed.metrics.jsonl \
    --target "easy:0.25,medium:0.45,hard:0.30" \
    --by_task "hotpotqa,strategyqa,gsm8k" \
    --out data/rollouts/rc1_seed.balanced.jsonl

# 难度验证
echo "🎯 难度分布验证..."
python scripts/validate_difficulty.py \
    --metrics data/rollouts/rc1_seed.metrics.jsonl \
    --balanced data/rollouts/rc1_seed.balanced.jsonl \
    --min_hard_pct 0.30 \
    --max_easy_pct 0.30 \
    --len_max 3500 \
    --turns_max 8 \
    --tool_hops_max 8 \
    --clue_overlap_max_easy 0.65 \
    --clue_overlap_min_hard 0.10 \
    --out reports/rc1/difficulty_report.json

if [ $? -ne 0 ]; then
    echo "❌ 难度验证失败！"
    exit 1
fi

# 生成指纹
echo "🔐 生成数据指纹..."
sha256sum data/rollouts/rc1_seed.jsonl > reports/rc1/rc1_seed.sha256
sha256sum data/rollouts/rc1_seed.metrics.jsonl > reports/rc1/rc1_seed.metrics.sha256
sha256sum data/rollouts/rc1_seed.balanced.jsonl > reports/rc1/rc1_seed.balanced.sha256

echo ""
echo "🎉 种子池重建完成！"
echo "📋 质量报告:"
echo "  - distinct-2 ≥ 0.60 ✅"
echo "  - 角色数 ≥ 4 ✅"
echo "  - 语体数 ≥ 3 ✅"
echo "  - Hard样本 ≥ 30% ✅"
echo "  - Easy样本 ≤ 30% ✅"
echo "  - 无数据泄漏 ✅"
