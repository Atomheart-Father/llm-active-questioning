import pytest
import tempfile
import os
import torch
from src.core.checkpoint import save_ckpt, load_ckpt

def test_save_load_ckpt():
    """测试保存和加载checkpoint后参数一致"""
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建测试状态
        test_state = {
            'model': {'param1': torch.tensor([1.0, 2.0, 3.0])},
            'optimizer': {'lr': torch.tensor(0.001)},
            'scheduler': {'step': torch.tensor(100)},
            'scaler': {'scale': torch.tensor(1.0)},
            'rng': {'seed': 42},
            'step': 1000,
            'timestamp': '2025-08-23 15:00:00',
            'config': {'test': True}
        }
        
        # 保存checkpoint
        ckpt_path = os.path.join(temp_dir, 'test_ckpt')
        save_ckpt(test_state, ckpt_path)
        
        # 验证文件存在
        assert os.path.exists(ckpt_path)
        assert os.path.exists(os.path.join(ckpt_path, 'model.safetensors'))
        assert os.path.exists(os.path.join(ckpt_path, 'opt.pt'))
        assert os.path.exists(os.path.join(ckpt_path, 'sched.pt'))
        assert os.path.exists(os.path.join(ckpt_path, 'scaler.pt'))
        assert os.path.exists(os.path.join(ckpt_path, 'rng.pkl'))
        assert os.path.exists(os.path.join(ckpt_path, 'meta.json'))
        
        # 加载checkpoint
        loaded_state = load_ckpt(ckpt_path)
        
        # 验证参数一致
        assert loaded_state['step'] == test_state['step']
        assert loaded_state['timestamp'] == test_state['timestamp']
        assert loaded_state['config'] == test_state['config']
        
        # 验证张量参数
        torch.testing.assert_close(
            loaded_state['model']['param1'], 
            test_state['model']['param1']
        )
        torch.testing.assert_close(
            loaded_state['optimizer']['lr'], 
            test_state['optimizer']['lr']
        )

def test_load_nonexistent_ckpt():
    """测试加载不存在的checkpoint应抛出异常"""
    with pytest.raises(FileNotFoundError):
        load_ckpt('/nonexistent/path')
