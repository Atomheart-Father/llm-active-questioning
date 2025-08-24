#!/usr/bin/env python3
import json
import jsonlines
import os
from pathlib import Path

def generate_min_data():
    """生成最小训练和评测数据集"""
    
    # 训练数据（≥100条）
    train_samples = []
    for i in range(100):
        train_samples.append({
            "input": f"请回答以下问题：{i+1} + {i+2} = ?",
            "output": f"答案是 {i+1 + i+2}",
            "meta": {"id": f"train_{i}", "type": "math"}
        })
    
    # 评测数据（≥30条）
    eval_samples = []
    for i in range(30):
        eval_samples.append({
            "input": f"请计算：{i*2} × {i*3}",
            "output": f"结果是 {i*2 * i*3}",
            "meta": {"id": f"eval_{i}", "type": "math"}
        })
    
    # 确保目录存在
    os.makedirs("data", exist_ok=True)
    
    # 写入训练数据
    with jsonlines.open("data/train_min.jsonl", 'w') as writer:
        for sample in train_samples:
            writer.write(sample)
    
    # 写入评测数据
    with jsonlines.open("data/eval_min.jsonl", 'w') as writer:
        for sample in eval_samples:
            writer.write(sample)
    
    print(f"✅ 已生成最小数据集：")
    print(f"  - 训练集：{len(train_samples)} 条")
    print(f"  - 评测集：{len(eval_samples)} 条")

if __name__ == "__main__":
    generate_min_data()
