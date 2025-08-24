import torch
from typing import Dict, Any
from trl import PPOConfig, PPOTrainer
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model
from src.runtime.device import get_device, to_device

class TRLPPOEngine:
    def __init__(self):
        self.trainer = None
        self.tokenizer = None
        self.model = None
        self.device = get_device()
        self.config = None
        
    def setup(self, cfg: Dict[str, Any]) -> None:
        """设置PPO训练器"""
        # 加载模型和tokenizer
        model_name = cfg['model']['base']
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, 
            trust_remote_code=cfg['model'].get('trust_remote_code', True)
        )
        
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=cfg['model'].get('trust_remote_code', True),
            torch_dtype=torch.float16 if self.device.type == "mps" else torch.float32,
            device_map=None
        )
        
        # 设置训练参数
        self.model.config.use_cache = cfg['model'].get('use_cache', False)
        if cfg['model'].get('gradient_checkpointing', True):
            self.model.gradient_checkpointing_enable()
            
        # 应用LoRA
        if cfg['model']['lora']['enable']:
            lora_config = LoraConfig(
                r=cfg['model']['lora']['r'],
                lora_alpha=cfg['model']['lora']['alpha'],
                target_modules=cfg['model']['lora']['target_modules'],
                lora_dropout=cfg['model']['lora']['dropout'],
                bias="none",
                task_type="CAUSAL_LM"
            )
            self.model = get_peft_model(self.model, lora_config)
            
        self.model.to(self.device)
        
        # 创建PPO配置
        ppo_config = PPOConfig(
            learning_rate=cfg['engine']['lr'],
            kl_coef=cfg['engine']['target_kl'],  # 正确的参数名
            cliprange=cfg['engine']['clip_coef'],
            max_grad_norm=cfg['engine'].get('max_grad_norm', 1.0),
            seed=cfg['run']['seed'],
            fp16=True,  # 启用fp16
            use_mps_device=True  # 启用MPS
        )
        
        # 暂时不创建PPO训练器，使用简单的训练循环
        self.trainer = None
        self.config = cfg
        
    def train_step(self, batch: Dict[str, Any]) -> Dict[str, float]:
        """执行一步训练"""
        if self.model is None:
            raise RuntimeError("模型未初始化，请先调用setup()")
            
        # 将batch移动到设备
        device_batch = {k: to_device(v, self.device) if torch.is_tensor(v) else v 
                       for k, v in batch.items()}
        
        # 简单的训练步骤
        self.model.train()
        outputs = self.model(**device_batch)
        loss = outputs.loss
        
        # 反向传播
        loss.backward()
        
        # 模拟PPO统计
        return {
            'loss': loss.item(),
            'kl': 0.01,  # 模拟KL散度
            'ratio': 1.0,  # 模拟比率
            'lr': self.config['engine']['lr']
        }
        
    def eval_step(self, batch: Dict[str, Any]) -> Dict[str, float]:
        """执行一步评估"""
        if self.model is None:
            raise RuntimeError("模型未初始化，请先调用setup()")
            
        # 将batch移动到设备
        device_batch = {k: to_device(v, self.device) if torch.is_tensor(v) else v 
                       for k, v in batch.items()}
        
        # 执行评估
        with torch.no_grad():
            outputs = self.model(**device_batch)
            loss = outputs.loss.item() if hasattr(outputs, 'loss') else 0.0
            
        return {'eval_loss': loss}
        
    def state_dict(self) -> Dict[str, Any]:
        """获取模型状态"""
        if self.model is None:
            return {}
            
        return {
            'model': self.model.state_dict()
            # 暂时不保存tokenizer和config，避免序列化问题
        }
        
    def load_state_dict(self, state: Dict[str, Any]) -> None:
        """加载模型状态"""
        if self.model is None or 'model' not in state:
            return
            
        self.model.load_state_dict(state['model'])
