import pytest
import tempfile
import os
import sys
from src.config.loader import load_config

def test_invalid_yaml():
    """测试无效YAML应退出码2"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("invalid: yaml: content: [")
        temp_file = f.name
    
    try:
        with pytest.raises(SystemExit) as exc_info:
            load_config(temp_file)
        assert exc_info.value.code == 2
    finally:
        os.unlink(temp_file)

def test_missing_sections():
    """测试缺少必需配置节应退出码2"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
run:
  seed: 20250823
  output_dir: "checkpoints/local"
  save_steps: 500
  eval_steps: 1000
  max_steps: 2000
# 缺少data, model, engine, strategy节
""")
        temp_file = f.name
    
    try:
        with pytest.raises(SystemExit) as exc_info:
            load_config(temp_file)
        assert exc_info.value.code == 2
    finally:
        os.unlink(temp_file)

def test_missing_run_keys():
    """测试缺少run节必需键应退出码2"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
run:
  seed: 20250823
  # 缺少output_dir, save_steps等
data:
  train_path: "data/train_min.jsonl"
  eval_path: "data/eval_min.jsonl"
  max_length: 1024
  batch_size: 1
model:
  base: "Qwen/Qwen3-4B-Thinking-2507"
engine:
  name: "trl_ppo"
  target_kl: 0.03
  lr: 1.0e-5
  clip_coef: 0.2
strategy:
  name: "ppo"
""")
        temp_file = f.name
    
    try:
        with pytest.raises(SystemExit) as exc_info:
            load_config(temp_file)
        assert exc_info.value.code == 2
    finally:
        os.unlink(temp_file)
