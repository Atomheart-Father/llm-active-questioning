#!/usr/bin/env python3
"""
RC1正式训练预检脚本
确保所有依赖、配置、目录结构就绪
"""

import os
import json
import yaml
from pathlib import Path
import logging

def check_data_freeze():
    """检查数据版本冻结"""
    print("🔍 检查数据版本冻结...")
    
    # 检查shadow_eval数据
    shadow_file = Path("data/shadow_eval_245.jsonl")
    if shadow_file.exists():
        with open(shadow_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        print(f"  ✅ shadow_eval数据: {len(lines)}条样本")
    else:
        print(f"  ❌ shadow_eval数据缺失: {shadow_file}")
        return False
    
    # 检查weights.json
    weights_file = Path("configs/weights.json")
    if weights_file.exists():
        with open(weights_file, 'r', encoding='utf-8') as f:
            weights = json.load(f)
        print(f"  ✅ 权重配置: 版本{weights.get('version', 'unknown')}")
        print(f"    - lambda: {weights.get('lambda', 'N/A')}")
        print(f"    - 权重维度: {len(weights.get('weights', {}))}")
    else:
        print(f"  ❌ 权重配置缺失: {weights_file}")
        return False
    
    return True

def check_api_config():
    """检查API配置"""
    print("🔍 检查评分API配置...")
    
    # 检查环境变量
    required_env = ['BASE_MODEL']
    optional_env = ['GEMINI_API_KEY', 'DEEPSEEK_API_KEY']
    
    for env_var in required_env:
        value = os.getenv(env_var)
        if value:
            print(f"  ✅ {env_var}: {value}")
        else:
            print(f"  ❌ {env_var}: 未设置")
            return False
    
    for env_var in optional_env:
        value = os.getenv(env_var)
        if value:
            print(f"  ✅ {env_var}: {'*' * (len(value) - 4) + value[-4:]}")
        else:
            print(f"  ⚠️ {env_var}: 未设置 (可选)")
    
    return True

def check_config_consistency():
    """检查配置一致性"""
    print("🔍 检查配置一致性...")
    
    config_file = Path("configs/ppo_scale.yaml")
    if not config_file.exists():
        print(f"  ❌ 配置文件缺失: {config_file}")
        return False
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 检查关键配置
    checks = [
        ('seeds', [20250820, 20250821, 20250822]),
        ('max_concurrent', 6),
        ('steps', 50000),
        ('train_samples', 80000),
        ('overclar.alpha', 0.07),
        ('overclar.cap', 3)
    ]
    
    for key, expected in checks:
        if '.' in key:
            current = config
            for part in key.split('.'):
                current = current.get(part, {})
        else:
            current = config.get(key)
        
        if current == expected:
            print(f"  ✅ {key}: {current}")
        else:
            print(f"  ⚠️ {key}: {current} (期望: {expected})")
    
    return True

def check_directories():
    """检查目录结构"""
    print("🔍 检查目录结构...")
    
    required_dirs = [
        "reports/rc1",
        "checkpoints/rc1", 
        "deploy/gguf",
        "data",
        "templates/pack_v2"
    ]
    
    all_good = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists():
            print(f"  ✅ {dir_path}/")
        else:
            print(f"  ❌ {dir_path}/ (缺失)")
            path.mkdir(parents=True, exist_ok=True)
            print(f"    已创建: {dir_path}/")
    
    return all_good

def check_dependencies():
    """检查依赖库"""
    print("🔍 检查依赖库...")
    
    required_modules = [
        'numpy', 'pandas', 'scipy', 'yaml', 'sqlite3',
        'pathlib', 'json', 'logging', 'time', 'random'
    ]
    
    missing = []
    for module in required_modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError:
            print(f"  ❌ {module} (缺失)")
            missing.append(module)
    
    if missing:
        print(f"  缺失依赖: {missing}")
        return False
    
    return True

def estimate_resources():
    """估算资源需求"""
    print("🔍 估算资源需求...")
    
    # 基于配置估算
    config_file = Path("configs/ppo_scale.yaml")
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    steps = config.get('steps', 50000)
    seeds = len(config.get('seeds', []))
    eval_every = config.get('eval_every_steps', 1000)
    
    total_evals = (steps // eval_every) * seeds
    eval_samples = config.get('eval_shadow_n', 245)
    total_api_calls = total_evals * eval_samples * 3  # K=3投票
    
    # 时间估算（每个API调用1-2秒）
    estimated_hours = (total_api_calls * 1.5) / 3600
    
    print(f"  📊 训练规模:")
    print(f"    - 总步数: {steps * seeds:,}")
    print(f"    - 评估次数: {total_evals}")
    print(f"    - API调用: {total_api_calls:,}")
    print(f"    - 预估时间: {estimated_hours:.1f}小时")
    
    return True

def main():
    """主预检流程"""
    print("🚀 RC1正式训练预检")
    print("=" * 50)
    
    checks = [
        ("数据版本冻结", check_data_freeze),
        ("API配置", check_api_config), 
        ("配置一致性", check_config_consistency),
        ("目录结构", check_directories),
        ("依赖库", check_dependencies),
        ("资源估算", estimate_resources)
    ]
    
    all_passed = True
    for name, check_func in checks:
        try:
            result = check_func()
            if not result:
                all_passed = False
            print()
        except Exception as e:
            print(f"  ❌ {name}检查失败: {e}")
            all_passed = False
            print()
    
    print("=" * 50)
    if all_passed:
        print("✅ 预检通过，可以启动RC1训练！")
        print()
        print("🚀 启动命令:")
        print(f"export BASE_MODEL=\"Qwen/Qwen3-4B-Thinking-2507\"")
        print(f"python -m train.ppo_runner --config configs/ppo_scale.yaml")
        return 0
    else:
        print("❌ 预检未通过，请修复问题后重试")
        return 1

if __name__ == "__main__":
    exit(main())
