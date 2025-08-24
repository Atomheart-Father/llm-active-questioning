import os
import json
import hashlib
import pickle
from pathlib import Path
from typing import Dict, Any
import torch

def save_ckpt(state: Dict[str, Any], path: str) -> None:
    """保存checkpoint"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    
    # 保存模型状态
    if 'model' in state:
        torch.save(state['model'], path / 'model.safetensors')
    
    # 保存优化器状态
    if 'optimizer' in state:
        torch.save(state['optimizer'], path / 'opt.pt')
    
    # 保存调度器状态
    if 'scheduler' in state:
        torch.save(state['scheduler'], path / 'sched.pt')
    
    # 保存梯度缩放器状态
    if 'scaler' in state:
        torch.save(state['scaler'], path / 'scaler.pt')
    
    # 保存RNG状态
    if 'rng' in state:
        with open(path / 'rng.pkl', 'wb') as f:
            pickle.dump(state['rng'], f)
    
    # 保存元数据
    meta = {
        'step': state.get('step', 0),
        'timestamp': state.get('timestamp', ''),
        'config': state.get('config', {})
    }
    
    with open(path / 'meta.json', 'w') as f:
        json.dump(meta, f, indent=2)
    
    # 计算并记录sha256
    record_ckpt_manifest(str(path), meta)

def load_ckpt(path: str) -> Dict[str, Any]:
    """加载checkpoint"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint不存在: {path}")
    
    state = {}
    
    # 加载模型状态
    model_path = path / 'model.safetensors'
    if model_path.exists():
        state['model'] = torch.load(model_path, map_location='cpu')
    
    # 加载优化器状态
    opt_path = path / 'opt.pt'
    if opt_path.exists():
        state['optimizer'] = torch.load(opt_path, map_location='cpu')
    
    # 加载调度器状态
    sched_path = path / 'sched.pt'
    if sched_path.exists():
        state['scheduler'] = torch.load(sched_path, map_location='cpu')
    
    # 加载梯度缩放器状态
    scaler_path = path / 'scaler.pt'
    if scaler_path.exists():
        state['scaler'] = torch.load(scaler_path, map_location='cpu')
    
    # 加载RNG状态
    rng_path = path / 'rng.pkl'
    if rng_path.exists():
        with open(rng_path, 'rb') as f:
            state['rng'] = pickle.load(f)
    
    # 加载元数据
    meta_path = path / 'meta.json'
    if meta_path.exists():
        with open(meta_path, 'r') as f:
            meta = json.load(f)
            state.update(meta)
    
    return state

def record_ckpt_manifest(ckpt_path: str, meta: Dict[str, Any]) -> None:
    """记录checkpoint到manifest文件"""
    os.makedirs('reports', exist_ok=True)
    
    # 计算sha256
    ckpt_dir = Path(ckpt_path)
    sha256 = hashlib.sha256()
    
    for file_path in ckpt_dir.glob('*'):
        if file_path.is_file():
            with open(file_path, 'rb') as f:
                sha256.update(f.read())
    
    # 记录到manifest
    manifest_entry = {
        'path': ckpt_path,
        'step': meta.get('step', 0),
        'timestamp': meta.get('timestamp', ''),
        'sha256': sha256.hexdigest()
    }
    
    manifest_file = 'reports/ckpt_manifest.jsonl'
    with open(manifest_file, 'a') as f:
        f.write(json.dumps(manifest_entry) + '\n')
    
    print(f"✅ Checkpoint已记录到manifest: {ckpt_path}")
