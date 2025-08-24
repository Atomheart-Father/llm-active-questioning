#!/usr/bin/env python3
import argparse
import json
import time
import sys
import os
from pathlib import Path
from typing import Dict, Any
import torch

from src.config.loader import load_config
from src.engines.trl_ppo import TRLPPOEngine
from src.strategies.ppo import PPOStrategy
from src.data.readers.jsonl_reader import JSONLReader
from src.data.collate.default import DefaultCollator
from src.core.checkpoint import save_ckpt, load_ckpt
from src.runtime.device import get_device

def fatal_error(msg: str, logs_dir: str = "logs") -> None:
    """致命错误处理"""
    print(f"FATAL: {msg}")
    
    # 收集最近200行日志
    log_file = f"{logs_dir}/train.log"
    recent_logs = []
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            lines = f.readlines()
            recent_logs = lines[-200:] if len(lines) > 200 else lines
    
    # 写入错误报告
    error_report = {
        'error': msg,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'recent_logs': recent_logs
    }
    
    os.makedirs('reports', exist_ok=True)
    error_file = f"reports/ERROR_{int(time.time())}.json"
    with open(error_file, 'w') as f:
        json.dump(error_report, f, indent=2, ensure_ascii=False)
    
    print(f"❌ 错误报告已写入: {error_file}")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, help='配置文件路径')
    parser.add_argument('--resume', help='恢复训练的checkpoint路径')
    args = parser.parse_args()
    
    try:
        # 加载配置
        config = load_config(args.config)
        
        # 创建输出目录
        output_dir = Path(config['run']['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置日志
        log_file = config['run']['log_file']
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # 设置设备
        device = get_device()
        print(f"🚀 使用设备: {device}")
        
        # 初始化引擎和策略
        engine = TRLPPOEngine()
        strategy = PPOStrategy()
        
        # 设置引擎
        engine.setup(config)
        strategy.attach_engine(engine)
        
        # 加载数据
        train_reader = JSONLReader(config['data']['train_path'])
        eval_reader = JSONLReader(config['data']['eval_path'])
        
        train_samples = train_reader.read_samples()
        eval_samples = eval_reader.read_samples()
        
        print(f"📊 训练样本: {len(train_samples)}, 评测样本: {len(eval_samples)}")
        
        # 创建数据整理器
        collator = DefaultCollator(
            engine.tokenizer, 
            config['data']['max_length']
        )
        
        # 恢复训练状态
        start_step = 0
        if args.resume:
            print(f"🔄 从checkpoint恢复: {args.resume}")
            state = load_ckpt(args.resume)
            start_step = state.get('step', 0)
            engine.load_state_dict(state)
            print(f"✅ 已恢复到步骤: {start_step}")
        
        # 训练循环
        max_steps = config['run']['max_steps']
        save_steps = config['run']['save_steps']
        eval_steps = config['run']['eval_steps']
        
        print(f"🎯 开始训练，目标步数: {max_steps}")
        
        for step in range(start_step, max_steps):
            try:
                # 准备batch
                batch_size = config['data']['batch_size']
                batch_samples = train_samples[step % len(train_samples):(step % len(train_samples)) + batch_size]
                if len(batch_samples) < batch_size:
                    batch_samples.extend(train_samples[:batch_size - len(batch_samples)])
                
                batch = collator(batch_samples)
                
                # 训练步骤
                metrics = strategy.on_batch(batch)
                
                # 记录指标
                metrics['step'] = step
                metrics['lr'] = metrics.get('lr', 0.0)
                metrics['mem_used_mb'] = torch.cuda.memory_allocated() / 1024 / 1024 if torch.cuda.is_available() else 0
                metrics['sec_per_step'] = time.time()
                
                # 写入metrics.jsonl
                os.makedirs('reports', exist_ok=True)
                with open('reports/metrics.jsonl', 'a') as f:
                    f.write(json.dumps(metrics) + '\n')
                
                # 打印进度
                if step % 10 == 0:
                    print(f"Step {step}/{max_steps}: loss={metrics.get('loss', 0):.4f}, kl={metrics.get('kl', 0):.4f}")
                
                # 保存checkpoint
                if step > 0 and step % save_steps == 0:
                    ckpt_path = output_dir / f"step_{step:06d}"
                    # 过滤掉不可序列化的配置
                    safe_config = {}
                    for key, value in config.items():
                        try:
                            json.dumps(value)
                            safe_config[key] = value
                        except (TypeError, ValueError):
                            safe_config[key] = str(value)
                    
                    state = {
                        'step': step,
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'config': safe_config,
                        **engine.state_dict()
                    }
                    save_ckpt(state, str(ckpt_path))
                    
                    # 更新latest链接
                    latest_link = output_dir / "latest"
                    if latest_link.exists():
                        latest_link.unlink()
                    latest_link.symlink_to(ckpt_path.name)
                
                # 评估
                if step > 0 and step % eval_steps == 0:
                    print(f"🔍 步骤 {step} 评估中...")
                    eval_batch = collator(eval_samples[:batch_size])
                    eval_metrics = engine.eval_step(eval_batch)
                    print(f"📊 评估结果: {eval_metrics}")
                
            except Exception as e:
                fatal_error(f"训练步骤 {step} 失败: {str(e)}", "logs")
        
        print("✅ 训练完成！")
        
    except Exception as e:
        fatal_error(f"训练启动失败: {str(e)}", "logs")

if __name__ == "__main__":
    main()
