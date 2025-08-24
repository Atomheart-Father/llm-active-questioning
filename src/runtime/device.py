import torch
from typing import Union, Any

def get_device() -> torch.device:
    """自动选择设备：优先MPS，否则CPU"""
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")

def to_device(t: Union[torch.Tensor, Any], device: torch.device = None) -> Union[torch.Tensor, Any]:
    """将张量移动到指定设备，自动处理dtype"""
    if device is None:
        device = get_device()
    
    if isinstance(t, torch.Tensor):
        # MPS优先使用fp16，CPU使用fp32
        if device.type == "mps":
            if t.dtype == torch.float32:
                t = t.to(torch.float16)
        elif device.type == "cpu":
            if t.dtype == torch.float16:
                t = t.to(torch.float32)
        
        return t.to(device)
    
    return t
