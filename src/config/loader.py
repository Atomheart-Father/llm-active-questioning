import yaml
import os
import sys
from typing import Dict, Any
from pathlib import Path

def load_config(config_path: str) -> Dict[str, Any]:
    """加载并校验配置文件"""
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        sys.exit(2)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"❌ YAML解析失败: {e}")
        sys.exit(2)
    
    # 强校验
    required_sections = ['run', 'data', 'model', 'engine', 'strategy']
    for section in required_sections:
        if section not in config:
            print(f"❌ 缺少必需配置节: {section}")
            sys.exit(2)
    
    # 校验run节
    run = config['run']
    required_run = ['seed', 'output_dir', 'save_steps', 'eval_steps', 'max_steps']
    for key in required_run:
        if key not in run:
            print(f"❌ 缺少必需配置: run.{key}")
            sys.exit(2)
    
    # 校验data节
    data = config['data']
    required_data = ['train_path', 'eval_path', 'max_length', 'batch_size']
    for key in required_data:
        if key not in data:
            print(f"❌ 缺少必需配置: data.{key}")
            sys.exit(2)
    
    # 校验model节
    model = config['model']
    if 'base' not in model:
        print("❌ 缺少必需配置: model.base")
        sys.exit(2)
    
    # 校验engine节
    engine = config['engine']
    required_engine = ['name', 'target_kl', 'lr', 'clip_coef']
    for key in required_engine:
        if key not in engine:
            print(f"❌ 缺少必需配置: engine.{key}")
            sys.exit(2)
    
    # 校验strategy节
    strategy = config['strategy']
    if 'name' not in strategy:
        print("❌ 缺少必需配置: strategy.name")
        sys.exit(2)
    
    # 保存有效配置
    os.makedirs('reports', exist_ok=True)
    with open('reports/config_effective.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    print("✅ 配置校验通过，已保存到 reports/config_effective.yaml")
    return config

def verify_config(config_path: str) -> None:
    """验证配置文件（CLI入口）"""
    load_config(config_path)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("用法: python src/config/loader.py <config_file>")
        sys.exit(1)
    verify_config(sys.argv[1])
