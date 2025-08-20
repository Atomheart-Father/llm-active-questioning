#!/bin/bash
# Phase 3.2 超参数扫描脚本
# 用于RC1模型的系统性超参数调优

set -e

echo "🔍 PPO超参数扫描 - Phase 3.2"
echo "=================================="

# 检查环境
if [ -z "$BASE_MODEL" ]; then
    echo "❌ 错误: 请设置 BASE_MODEL 环境变量"
    exit 1
fi

# 创建扫描结果目录
SWEEP_DIR="reports/rc1/sweeps"
mkdir -p "$SWEEP_DIR"

# 基础配置文件
BASE_CONFIG="configs/ppo_scale.yaml"
if [ ! -f "$BASE_CONFIG" ]; then
    echo "❌ 错误: 基础配置文件不存在: $BASE_CONFIG"
    exit 1
fi

# 扫描参数定义
declare -a LEARNING_RATES=("5e-6" "1e-5" "2e-5")
declare -a ALPHA_VALUES=("0.05" "0.07" "0.10")
declare -a KL_COEFS=("0.01" "0.02" "0.03")
declare -a SEEDS=("20250820" "20250821" "20250822")

echo "📋 扫描计划:"
echo "   学习率: ${LEARNING_RATES[*]}"
echo "   α值: ${ALPHA_VALUES[*]}"
echo "   KL系数: ${KL_COEFS[*]}"
echo "   种子: ${SEEDS[*]}"
echo "   总组合数: $((${#LEARNING_RATES[@]} * ${#ALPHA_VALUES[@]} * ${#KL_COEFS[@]}))"

# 记录开始时间
START_TIME=$(date +%s)
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# 扫描日志
SWEEP_LOG="$SWEEP_DIR/sweep_$TIMESTAMP.log"
echo "📝 扫描日志: $SWEEP_LOG"

# 函数：运行单个扫描实验
run_sweep_experiment() {
    local lr=$1
    local alpha=$2
    local kl_coef=$3
    local exp_id="${lr}_${alpha}_${kl_coef}"
    
    echo "🚀 运行实验: lr=$lr, α=$alpha, kl=$kl_coef" | tee -a "$SWEEP_LOG"
    
    # 创建实验专用配置
    local exp_config="$SWEEP_DIR/config_$exp_id.yaml"
    cp "$BASE_CONFIG" "$exp_config"
    
    # 修改配置参数（使用临时Python脚本）
    python3 << EOF
import yaml
with open('$exp_config', 'r') as f:
    config = yaml.safe_load(f)

config['lr'] = float('$lr')
config['overclar']['alpha'] = float('$alpha') 
config['init_kl_coef'] = float('$kl_coef')

# 缩减扫描实验规模
config['steps'] = 10000  # 降到10k步
config['train_samples'] = 20000  # 降到20k样本
config['eval_shadow_n'] = 100  # 降到100样本评估

with open('$exp_config', 'w') as f:
    yaml.dump(config, f, default_flow_style=False)
EOF
    
    # 运行实验
    local exp_output="$SWEEP_DIR/result_$exp_id.json"
    if python -m train.ppo_runner --config "$exp_config" > "$SWEEP_DIR/log_$exp_id.txt" 2>&1; then
        echo "✅ 实验完成: $exp_id" | tee -a "$SWEEP_LOG"
        
        # 提取关键指标
        if [ -f "reports/rc1/rc1_final_report.json" ]; then
            python3 << EOF
import json
try:
    with open('reports/rc1/rc1_final_report.json', 'r') as f:
        result = json.load(f)
    
    # 提取关键指标
    summary = {
        'experiment_id': '$exp_id',
        'hyperparams': {'lr': $lr, 'alpha': $alpha, 'kl_coef': $kl_coef},
        'timestamp': '$(date -Iseconds)'
    }
    
    if 'aggregate' in result:
        agg = result['aggregate']
        summary['metrics'] = {
            'success_improvement_median': agg.get('success_deltas_pp', {}).get('hotpotqa', {}).get('median', 0),
            'overclar_reduction_median': agg.get('overclar_reduction_pct', {}).get('median', 0),
            'shadow_spearman_median': agg.get('shadow_metrics', {}).get('spearman', {}).get('median', 0)
        }
    
    if 'acceptance_check' in result:
        summary['passed'] = result['acceptance_check']['all_passed']
    
    with open('$exp_output', 'w') as f:
        json.dump(summary, f, indent=2)
        
except Exception as e:
    print(f"提取指标失败: {e}")
EOF
        fi
    else
        echo "❌ 实验失败: $exp_id" | tee -a "$SWEEP_LOG"
        echo "{'experiment_id': '$exp_id', 'error': 'training_failed'}" > "$exp_output"
    fi
    
    # 清理临时文件
    rm -f "$exp_config"
}

# 主扫描循环
experiment_count=0
total_experiments=$((${#LEARNING_RATES[@]} * ${#ALPHA_VALUES[@]} * ${#KL_COEFS[@]}))

echo "🏁 开始超参数扫描..." | tee -a "$SWEEP_LOG"

for lr in "${LEARNING_RATES[@]}"; do
    for alpha in "${ALPHA_VALUES[@]}"; do
        for kl_coef in "${KL_COEFS[@]}"; do
            experiment_count=$((experiment_count + 1))
            echo "📊 进度: $experiment_count/$total_experiments"
            
            run_sweep_experiment "$lr" "$alpha" "$kl_coef"
            
            # 简短休息避免资源冲突
            sleep 5
        done
    done
done

# 生成汇总报告
echo "📊 生成汇总报告..." | tee -a "$SWEEP_LOG"

SUMMARY_REPORT="$SWEEP_DIR/sweep_summary_$TIMESTAMP.json"

python3 << EOF
import json
import glob
from pathlib import Path

sweep_dir = Path('$SWEEP_DIR')
result_files = list(sweep_dir.glob('result_*.json'))

experiments = []
for file in result_files:
    try:
        with open(file, 'r') as f:
            exp_data = json.load(f)
        experiments.append(exp_data)
    except Exception as e:
        print(f"读取文件失败 {file}: {e}")

# 按成功率改善排序
experiments.sort(key=lambda x: x.get('metrics', {}).get('success_improvement_median', 0), reverse=True)

# 统计信息
passed_count = sum(1 for exp in experiments if exp.get('passed', False))
total_count = len(experiments)

summary = {
    'sweep_metadata': {
        'timestamp': '$TIMESTAMP',
        'total_experiments': total_count,
        'passed_experiments': passed_count,
        'success_rate': passed_count / total_count if total_count > 0 else 0
    },
    'best_experiments': experiments[:5],  # Top 5
    'all_experiments': experiments
}

with open('$SUMMARY_REPORT', 'w') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print(f"汇总报告已保存: $SUMMARY_REPORT")
print(f"成功实验: {passed_count}/{total_count} ({passed_count/total_count*100:.1f}%)")

if experiments:
    best = experiments[0]
    print(f"最佳配置: {best.get('hyperparams', {})}")
    if 'metrics' in best:
        metrics = best['metrics']
        print(f"  成功率改善: {metrics.get('success_improvement_median', 0):.2f}pp")
        print(f"  过度澄清降低: {metrics.get('overclar_reduction_median', 0):.1f}%")
        print(f"  影子Spearman: {metrics.get('shadow_spearman_median', 0):.3f}")
EOF

# 计算总用时
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
HOURS=$((DURATION / 3600))
MINUTES=$(((DURATION % 3600) / 60))

echo "⏱️  扫描完成！" | tee -a "$SWEEP_LOG"
echo "   总用时: ${HOURS}h ${MINUTES}m" | tee -a "$SWEEP_LOG"
echo "   结果目录: $SWEEP_DIR" | tee -a "$SWEEP_LOG"
echo "   汇总报告: $SUMMARY_REPORT" | tee -a "$SWEEP_LOG"

echo "🎯 下一步建议:"
echo "   1. 查看 $SUMMARY_REPORT 确定最佳超参数"
echo "   2. 使用最佳配置运行完整训练: python -m train.ppo_runner --config configs/ppo_scale.yaml"
echo "   3. 运行可选分支: DPO优化 或 GGUF部署"
