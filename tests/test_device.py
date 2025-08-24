import pytest
import torch
from src.runtime.device import get_device, to_device

def test_get_device():
    """测试设备自动选择"""
    device = get_device()
    
    if torch.backends.mps.is_available():
        assert str(device) == "mps"
    else:
        assert str(device) == "cpu"

def test_to_device_tensor():
    """测试张量设备移动"""
    device = get_device()
    
    # 创建测试张量
    tensor = torch.tensor([1.0, 2.0, 3.0])
    
    # 移动到设备
    device_tensor = to_device(tensor, device)
    
    assert device_tensor.device.type == device.type
    
    # 检查dtype
    if device.type == "mps":
        assert device_tensor.dtype == torch.float16
    elif device.type == "cpu":
        assert device_tensor.dtype == torch.float32

def test_to_device_non_tensor():
    """测试非张量对象处理"""
    device = get_device()
    
    # 非张量对象应该原样返回
    obj = {"key": "value"}
    result = to_device(obj, device)
    
    assert result == obj
