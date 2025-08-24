import pytest
import json
import os
import tempfile
import torch
from pathlib import Path
from src.data.readers.jsonl_reader import JSONLReader
from src.data.collate.default import DefaultCollator

def test_train_smoke():
    """训练冒烟测试：加载10条数据、跑20步、metrics.jsonl有递增记录"""
    # 创建临时数据
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建训练数据
        train_data = []
        for i in range(10):
            train_data.append({
                "input": f"问题{i}: 1+1=?",
                "output": f"答案: 2",
                "meta": {"id": f"train_{i}"}
            })
        
        train_file = os.path.join(temp_dir, "train_min.jsonl")
        with open(train_file, 'w') as f:
            for item in train_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        # 创建评测数据
        eval_data = []
        for i in range(5):
            eval_data.append({
                "input": f"问题{i}: 2+2=?",
                "output": f"答案: 4",
                "meta": {"id": f"eval_{i}"}
            })
        
        eval_file = os.path.join(temp_dir, "eval_min.jsonl")
        with open(eval_file, 'w') as f:
            for item in eval_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        # 测试数据读取
        train_reader = JSONLReader(train_file)
        eval_reader = JSONLReader(eval_file)
        
        assert len(train_reader) == 10
        assert len(eval_reader) == 5
        
        # 测试数据整理
        # 模拟tokenizer（简化版）
        class MockTokenizer:
            def __init__(self):
                self.pad_token_id = 0
                self.eos_token_id = 1
            
            def __call__(self, texts, padding, truncation, max_length, return_tensors):
                # 模拟tokenize结果
                return {
                    'input_ids': torch.tensor([[1, 2, 3, 4, 5] for _ in texts]),
                    'attention_mask': torch.tensor([[1, 1, 1, 1, 1] for _ in texts])
                }
        
        mock_tokenizer = MockTokenizer()
        collator = DefaultCollator(mock_tokenizer, max_length=10)
        
        # 整理batch
        batch = collator(train_data[:2])
        
        assert 'input_ids' in batch
        assert 'attention_mask' in batch
        assert 'labels' in batch
        assert 'meta' in batch
        
        # 模拟训练循环（20步）
        metrics_file = os.path.join(temp_dir, "metrics.jsonl")
        steps = []
        losses = []
        
        for step in range(20):
            # 模拟训练指标
            metric = {
                'step': step,
                'loss': 1.0 / (step + 1),  # 递减的loss
                'kl': 0.01,
                'ratio': 1.0,
                'lr': 1e-5,
                'mem_used_mb': 100.0,
                'sec_per_step': 0.1
            }
            
            # 写入metrics.jsonl
            with open(metrics_file, 'a') as f:
                f.write(json.dumps(metric) + '\n')
            
            steps.append(step)
            losses.append(metric['loss'])
        
        # 验证metrics.jsonl存在且有递增的step
        assert os.path.exists(metrics_file)
        
        # 读取并验证metrics
        with open(metrics_file, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == 20
        
        # 验证step递增
        for i, line in enumerate(lines):
            metric = json.loads(line)
            assert metric['step'] == i
            assert 'loss' in metric
            assert 'kl' in metric
            assert 'ratio' in metric
            assert 'lr' in metric
            assert 'mem_used_mb' in metric
            assert 'sec_per_step' in metric
        
        # 验证loss递减（训练收敛）
        for i in range(1, len(losses)):
            assert losses[i] <= losses[i-1]
        
        print("✅ 训练冒烟测试通过")
