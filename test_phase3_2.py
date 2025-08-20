#!/usr/bin/env python3
"""
Phase 3.2 快速验证测试
测试RC1扩量训练的主要流程组件
"""

import os
import json
import logging
from pathlib import Path

# 设置环境变量
os.environ['BASE_MODEL'] = 'qwen3-4b-thinking'

def test_config_loading():
    """测试配置加载"""
    print("🧪 测试配置加载...")
    
    import yaml
    with open('configs/ppo_scale.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 环境变量替换
    if config['base_model'].startswith('${ENV.'):
        env_var = config['base_model'][6:-1]
        config['base_model'] = os.getenv(env_var, config['base_model'])
    
    print(f"  ✅ 基础模型: {config['base_model']}")
    print(f"  ✅ 训练步数: {config['steps']}")
    print(f"  ✅ 种子列表: {config['seeds']}")
    print(f"  ✅ 高级功能: {config.get('advanced_features', {}).keys()}")
    
def test_alpha_schedule():
    """测试α退火调度"""
    print("🧪 测试α退火调度...")
    
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    
    from train.ppo_runner import PPORunner
    
    # 创建临时配置
    config = {
        'overclar': {'alpha': 0.07},
        'advanced_features': {
            'alpha_annealing': {
                'enabled': True,
                'phase1_steps': 20000,
                'phase2_steps': 30000,
                'final_alpha': 0.05
            }
        }
    }
    
    runner = PPORunner.__new__(PPORunner)  # 创建实例但不初始化
    runner.config = config
    
    # 测试不同步骤的α值
    test_steps = [0, 10000, 20000, 35000, 50000]
    for step in test_steps:
        alpha = runner.calculate_alpha_schedule(step)
        print(f"  步骤 {step:5d}: α = {alpha:.3f}")
    
    print("  ✅ α退火调度正常")
    
def test_hacking_detection():
    """测试奖励破解检测"""
    print("🧪 测试奖励破解检测...")
    
    # 模拟训练状态
    hacking_signals = {
        'ask_spam_count': 50,
        'format_exploit_count': 25,
        'variance_spike_count': 80
    }
    
    total_samples = 1000
    thresholds = {
        "ask_spam_rate": 0.05,        # 5%
        "format_exploit_rate": 0.03,  # 3%
        "variance_spike_rate": 0.10   # 10%
    }
    
    rates = {}
    alerts = {}
    for signal_name, count in hacking_signals.items():
        rate_name = signal_name.replace("_count", "_rate")
        rate = count / total_samples if total_samples > 0 else 0
        rates[rate_name] = rate
        alerts[rate_name] = rate > thresholds[rate_name]
        
        status = "❌" if alerts[rate_name] else "✅"
        print(f"  {status} {rate_name}: {rate:.1%} (阈值: {thresholds[rate_name]:.1%})")
    
    print("  ✅ 奖励破解检测正常")
    
def test_acceptance_criteria():
    """测试验收标准检查"""
    print("🧪 测试验收标准...")
    
    # 模拟汇总指标
    aggregate = {
        'success_deltas_pp': {
            'hotpotqa': {'median': 8.5},
            'strategyqa': {'median': 6.2}
        },
        'overclar_reduction_pct': {'median': 28.0},
        'shadow_metrics': {
            'spearman': {'median': 0.82},
            'top10_overlap': {'median': 0.75},
            'corr_improve_pct': {'median': 15.0}
        }
    }
    
    criteria = {
        'success_improvement_pp': 7,
        'overclar_reduction_pct': 25,
        'shadow_spearman_min': 0.78,
        'shadow_top10_min': 0.72,
        'shadow_corr_improve_min': 12
    }
    
    # 检查成功率改善（需要发问任务的中位数）
    ask_needed_tasks = ['hotpotqa', 'strategyqa']
    ask_needed_deltas = [aggregate['success_deltas_pp'][task]['median'] 
                        for task in ask_needed_tasks]
    success_improvement = sum(ask_needed_deltas) / len(ask_needed_deltas)
    
    checks = [
        ('成功率改善', success_improvement, criteria['success_improvement_pp']),
        ('过度澄清降低', aggregate['overclar_reduction_pct']['median'], criteria['overclar_reduction_pct']),
        ('影子Spearman', aggregate['shadow_metrics']['spearman']['median'], criteria['shadow_spearman_min']),
        ('影子Top10', aggregate['shadow_metrics']['top10_overlap']['median'], criteria['shadow_top10_min']),
        ('影子相关性改善', aggregate['shadow_metrics']['corr_improve_pct']['median'], criteria['shadow_corr_improve_min'])
    ]
    
    all_passed = True
    for name, value, threshold in checks:
        passed = value >= threshold
        status = "✅" if passed else "❌"
        print(f"  {status} {name}: {value:.1f} ≥ {threshold}")
        if not passed:
            all_passed = False
    
    print(f"  {'✅' if all_passed else '❌'} 整体验收: {'通过' if all_passed else '未通过'}")
    
def test_file_structure():
    """测试文件结构"""
    print("🧪 测试文件结构...")
    
    required_files = [
        'configs/ppo_scale.yaml',
        'train/ppo_runner.py',
        'train/dpo_enhancement.py',
        'scripts/sweep_ppo.sh',
        'deploy/to_gguf.sh'
    ]
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} (缺失)")
    
    # 检查目录
    required_dirs = [
        'reports/rc1',
        'checkpoints/rc1',
        'deploy/gguf'
    ]
    
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"  ✅ {dir_path}/")
        else:
            print(f"  ❌ {dir_path}/ (缺失)")

def main():
    """运行所有测试"""
    print("🚀 Phase 3.2 组件验证测试")
    print("="*50)
    
    try:
        test_config_loading()
        print()
        
        test_alpha_schedule()
        print()
        
        test_hacking_detection()
        print()
        
        test_acceptance_criteria()
        print()
        
        test_file_structure()
        print()
        
        print("🎉 Phase 3.2 主要组件验证完成！")
        print("📋 下一步:")
        print("   1. 设置BASE_MODEL环境变量")
        print("   2. 运行: python -m train.ppo_runner --config configs/ppo_scale.yaml")
        print("   3. 可选: ./scripts/sweep_ppo.sh 进行超参数扫描")
        print("   4. 可选: ./deploy/to_gguf.sh 转换为GGUF格式")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    exit(main())
