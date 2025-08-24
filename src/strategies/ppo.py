from typing import Dict, Any
from src.core.api import Engine

class PPOStrategy:
    def __init__(self):
        self.engine = None
        
    def attach_engine(self, engine: Engine) -> None:
        """附加训练引擎"""
        self.engine = engine
        
    def on_batch(self, batch: Dict[str, Any]) -> Dict[str, float]:
        """处理一个batch"""
        if self.engine is None:
            raise RuntimeError("引擎未附加，请先调用attach_engine()")
            
        # 执行训练步骤
        return self.engine.train_step(batch)
