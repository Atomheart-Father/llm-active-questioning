"""
配置管理模块
用于加载和管理项目配置
"""

import os
from pathlib import Path
from typing import Dict, Any
from omegaconf import OmegaConf, DictConfig


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为 configs/default_config.yaml
        """
        if config_path is None:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "configs" / "default_config.yaml"
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> DictConfig:
        """加载配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        config = OmegaConf.load(self.config_path)
        
        # 解析环境变量
        config = self._resolve_environment_variables(config)
        
        return config
    
    def _resolve_environment_variables(self, config: DictConfig) -> DictConfig:
        """解析配置中的环境变量"""
        # 设置OpenAI API Key
        if "simulation" in config and "openai_api_key" in config.simulation:
            if not config.simulation.openai_api_key:
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    config.simulation.openai_api_key = api_key
        
        return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键，支持嵌套访问如 'model.name'
            default: 默认值
            
        Returns:
            配置值
        """
        try:
            return OmegaConf.select(self.config, key, default=default)
        except Exception:
            return default
    
    def update(self, updates: Dict[str, Any]) -> None:
        """
        更新配置
        
        Args:
            updates: 更新的配置字典
        """
        update_config = OmegaConf.create(updates)
        self.config = OmegaConf.merge(self.config, update_config)
    
    def save(self, save_path: str = None) -> None:
        """
        保存配置到文件
        
        Args:
            save_path: 保存路径，默认覆盖原配置文件
        """
        if save_path is None:
            save_path = self.config_path
        
        OmegaConf.save(self.config, save_path)
    
    @property
    def model_config(self) -> DictConfig:
        """模型配置"""
        return self.config.model
    
    @property
    def data_config(self) -> DictConfig:
        """数据配置"""
        return self.config.data
    
    @property
    def training_config(self) -> DictConfig:
        """训练配置"""
        return self.config.training
    
    @property
    def simulation_config(self) -> DictConfig:
        """模拟配置"""
        return self.config.simulation
    
    @property
    def reward_config(self) -> DictConfig:
        """奖励配置"""
        return self.config.reward
    
    @property
    def evaluation_config(self) -> DictConfig:
        """评估配置"""
        return self.config.evaluation
    
    @property
    def logging_config(self) -> DictConfig:
        """日志配置"""
        return self.config.logging


# 全局配置实例
config_manager = ConfigManager()


def get_config() -> ConfigManager:
    """获取配置管理器实例"""
    return config_manager
