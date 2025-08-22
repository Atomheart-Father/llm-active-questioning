#!/usr/bin/env python3
"""
从Hugging Face数据集重建影子集，确保真实数据源与溯源信息
"""

import argparse
import json
import random
import sys
from pathlib import Path
from datasets import load_dataset

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def load_hf_dataset(dataset_name, config=None, split="train"):
    """加载HF数据集并返回溯源信息"""
    try:
        if config:
            dataset = load_dataset(dataset_name, config, split=split)
        else:
            dataset = load_dataset(dataset_name, split=split)
        
        return dataset, {
            "hf_dataset": dataset_name,
            "hf_config": config,
            "hf_split": split,
            "hf_fingerprint": dataset._fingerprint,
            "hf_num_rows": len(dataset)
        }
    except Exception as e:
        print(f"❌ 加载数据集失败: {dataset_name} - {e}")
        sys.exit(1)

def extract_samples_hotpotqa(dataset, metadata, n_samples, seed):
    """从HotpotQA提取样本"""
    random.seed(seed + 1)
    indices = random.sample(range(len(dataset)), min(n_samples, len(dataset)))
    
    samples = []
    for i, idx in enumerate(indices):
        item = dataset[idx]
        sample = {
            "id": f"hotpotqa_{seed:08d}_{i:03d}",
            "task": "hotpotqa",
            "question": item["question"],
            "answer": item["answer"],
            "source": "hf",
            **metadata
        }
        samples.append(sample)
    
    return samples

def extract_samples_strategyqa(dataset, metadata, n_samples, seed):
    """从StrategyQA提取样本"""
    random.seed(seed + 2)
    indices = random.sample(range(len(dataset)), min(n_samples, len(dataset)))
    
    samples = []
    for i, idx in enumerate(indices):
        item = dataset[idx]
        # BigBench格式：inputs是问题，targets是答案
        question = item.get("inputs", "")
        targets = item.get("targets", [""])
        answer = "yes" if targets and ("yes" in str(targets[0]).lower() or "true" in str(targets[0]).lower()) else "no"
        
        sample = {
            "id": f"strategyqa_{seed:08d}_{i:03d}",
            "task": "strategyqa", 
            "question": question,
            "answer": answer,
            "source": "hf",
            **metadata
        }
        samples.append(sample)
    
    return samples

def extract_samples_gsm8k(dataset, metadata, n_samples, seed):
    """从GSM8K提取样本"""
    random.seed(seed + 3)
    indices = random.sample(range(len(dataset)), min(n_samples, len(dataset)))
    
    samples = []
    for i, idx in enumerate(indices):
        item = dataset[idx]
        # 去除末尾解释，只保留数字答案
        answer = item["answer"]
        if "####" in answer:
            answer = answer.split("####")[-1].strip()
        
        sample = {
            "id": f"gsm8k_{seed:08d}_{i:03d}",
            "task": "gsm8k",
            "question": item["question"],
            "answer": answer,
            "source": "hf",
            **metadata
        }
        samples.append(sample)
    
    return samples

def main():
    parser = argparse.ArgumentParser(description="从HF重建影子集")
    parser.add_argument("--n", type=int, default=245, help="总样本数")
    parser.add_argument("--seed", type=int, default=20250821, help="随机种子")
    parser.add_argument("--out", required=True, help="输出JSONL文件")
    parser.add_argument("--manifest", required=True, help="清单JSON文件")
    
    args = parser.parse_args()
    
    # 分层抽样：尽量82/82/81
    n_per_task = args.n // 3
    task_counts = {
        "hotpotqa": n_per_task,
        "strategyqa": n_per_task,
        "gsm8k": args.n - 2 * n_per_task  # 余数给GSM8K
    }
    
    print(f"🔄 重建影子集: 总数={args.n}, 分层={task_counts}")
    
    all_samples = []
    
    # HotpotQA
    print("📥 加载HotpotQA...")
    dataset, metadata = load_hf_dataset("hotpot_qa", config="distractor", split="validation")
    samples = extract_samples_hotpotqa(dataset, metadata, task_counts["hotpotqa"], args.seed)
    all_samples.extend(samples)
    print(f"  ✅ HotpotQA: {len(samples)}样本")
    
    # StrategyQA
    print("📥 加载StrategyQA...")
    dataset, metadata = load_hf_dataset("tasksource/bigbench", config="strategyqa", split="train")
    samples = extract_samples_strategyqa(dataset, metadata, task_counts["strategyqa"], args.seed)
    all_samples.extend(samples)
    print(f"  ✅ StrategyQA: {len(samples)}样本")
    
    # GSM8K
    print("📥 加载GSM8K...")
    dataset, metadata = load_hf_dataset("gsm8k", config="main", split="train")
    samples = extract_samples_gsm8k(dataset, metadata, task_counts["gsm8k"], args.seed)
    all_samples.extend(samples)
    print(f"  ✅ GSM8K: {len(samples)}样本")
    
    # 打乱顺序
    random.seed(args.seed)
    random.shuffle(all_samples)
    
    # 导出JSONL
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for sample in all_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
    
    # 生成清单
    by_task = {}
    for sample in all_samples:
        task = sample["task"]
        by_task[task] = by_task.get(task, 0) + 1
    
    manifest = {
        "total_samples": len(all_samples),
        "by_task": by_task,
        "seed": args.seed,
        "source": "hf",
        "samples": all_samples
    }
    
    Path(args.manifest).parent.mkdir(parents=True, exist_ok=True)
    with open(args.manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    print(f"📊 完成重建: {len(all_samples)}样本")
    print(f"📋 任务分布: {by_task}")
    print(f"💾 导出: {args.out}")
    print(f"📄 清单: {args.manifest}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
