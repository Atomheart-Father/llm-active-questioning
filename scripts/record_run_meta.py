#!/usr/bin/env python3
"""
记录RC1运行元数据指纹
"""

import os
import json
import hashlib
import subprocess
from pathlib import Path
import time

def get_git_sha():
    """获取当前git commit SHA"""
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                              capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except:
        return "unknown"

def get_file_sha256(file_path):
    """计算文件SHA256"""
    if not Path(file_path).exists():
        return "file_not_found"
    
    with open(file_path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def main():
    """记录运行元数据"""
    print("📝 记录RC1运行元数据指纹...")
    
    # 创建输出目录
    Path("reports/rc1").mkdir(parents=True, exist_ok=True)
    
    meta = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "git_sha": get_git_sha(),
        "run_mode": os.getenv("RUN_MODE"),
        "base_model": os.getenv("BASE_MODEL"),
        "scorer_provider": os.getenv("SCORER_PROVIDER"),
        "config_fingerprints": {
            "ppo_scale_yaml": get_file_sha256("configs/ppo_scale.yaml"),
            "weights_json": get_file_sha256("configs/weights.json")
        },
        "data_fingerprints": {
            "shadow_eval": get_file_sha256("data/shadow_eval_245.jsonl")
        },
        "seeds": [20250820, 20250821, 20250822],
        "training_params": {
            "steps": 50000,
            "train_samples": 80000,
            "batch_size": 64
        }
    }
    
    # 计算样本清单SHA256
    if Path("data/shadow_eval_245.jsonl").exists():
        with open("data/shadow_eval_245.jsonl", 'r', encoding='utf-8') as f:
            content = f.read()
        meta["sample_manifest_sha256"] = hashlib.sha256(content.encode()).hexdigest()
    
    # 保存元数据
    with open("reports/rc1/run_meta.json", 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 元数据已记录:")
    print(f"  Git SHA: {meta['git_sha'][:16]}...")
    print(f"  运行模式: {meta['run_mode']}")
    print(f"  配置指纹: {meta['config_fingerprints']['ppo_scale_yaml'][:16]}...")
    print(f"  数据指纹: {meta['sample_manifest_sha256'][:16]}...")
    
    return meta

if __name__ == "__main__":
    main()
