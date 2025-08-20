"""
日志管理模块
统一管理项目日志和实验追踪
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import wandb
from rich.console import Console
from rich.logging import RichHandler

from .config import get_config


class Logger:
    """统一日志管理器"""
    
    def __init__(self, name: str = "llm_collaboration", use_wandb: bool = None):
        """
        初始化日志器
        
        Args:
            name: 日志器名称
            use_wandb: 是否使用wandb，None时从配置读取
        """
        self.name = name
        self.config = get_config()
        
        if use_wandb is None:
            use_wandb = self.config.get("logging.use_wandb", False)
        
        self.use_wandb = use_wandb
        self.console = Console()
        
        # 设置基本日志
        self._setup_basic_logging()
        
        # 初始化wandb（如果启用）
        if self.use_wandb:
            self._setup_wandb()
    
    def _setup_basic_logging(self):
        """设置基本日志配置"""
        # 创建日志目录
        log_dir = Path(self.config.get("logging.log_dir", "./logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成日志文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"{self.name}_{timestamp}.log"
        
        # 配置日志格式
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        # 创建logger
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.INFO)
        
        # 清除现有handlers
        self.logger.handlers.clear()
        
        # 文件handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(log_format)
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Rich console handler
        rich_handler = RichHandler(console=self.console, rich_tracebacks=True)
        rich_handler.setLevel(logging.INFO)
        self.logger.addHandler(rich_handler)
        
        self.logger.info(f"日志系统初始化完成，日志文件: {log_file}")
    
    def _setup_wandb(self):
        """设置wandb实验追踪"""
        try:
            project_name = self.config.get("logging.project_name", "llm_human_collaboration")
            experiment_name = self.config.get("logging.experiment_name", "default_experiment")
            
            # 生成唯一的run名称
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_name = f"{experiment_name}_{timestamp}"
            
            wandb.init(
                project=project_name,
                name=run_name,
                config=dict(self.config.config),
                reinit=True
            )
            
            self.logger.info(f"WandB实验追踪初始化完成: {project_name}/{run_name}")
            
        except Exception as e:
            self.logger.warning(f"WandB初始化失败: {e}")
            self.use_wandb = False
    
    def info(self, message: str, **kwargs):
        """记录info级别日志"""
        self.logger.info(message)
        if self.use_wandb and kwargs:
            wandb.log(kwargs)
    
    def warning(self, message: str, **kwargs):
        """记录warning级别日志"""
        self.logger.warning(message)
        if self.use_wandb and kwargs:
            wandb.log(kwargs)
    
    def error(self, message: str, **kwargs):
        """记录error级别日志"""
        self.logger.error(message)
        if self.use_wandb and kwargs:
            wandb.log(kwargs)
    
    def debug(self, message: str, **kwargs):
        """记录debug级别日志"""
        self.logger.debug(message)
        if self.use_wandb and kwargs:
            wandb.log(kwargs)
    
    def log_metrics(self, metrics: Dict[str, Any], step: Optional[int] = None):
        """
        记录指标
        
        Args:
            metrics: 指标字典
            step: 步数
        """
        # 本地日志
        metrics_str = ", ".join([f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}" 
                                for k, v in metrics.items()])
        self.logger.info(f"Metrics - {metrics_str}")
        
        # WandB日志
        if self.use_wandb:
            wandb.log(metrics, step=step)
    
    def log_config(self, config: Dict[str, Any]):
        """记录配置信息"""
        self.logger.info("=" * 50)
        self.logger.info("实验配置:")
        for key, value in config.items():
            self.logger.info(f"  {key}: {value}")
        self.logger.info("=" * 50)
    
    def close(self):
        """关闭日志器"""
        if self.use_wandb:
            wandb.finish()
        
        # 关闭所有handlers
        for handler in self.logger.handlers:
            handler.close()


# 全局日志实例
_global_logger = None


def get_logger(name: str = "llm_collaboration", use_wandb: bool = None) -> Logger:
    """
    获取全局日志器实例
    
    Args:
        name: 日志器名称
        use_wandb: 是否使用wandb
        
    Returns:
        Logger实例
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = Logger(name=name, use_wandb=use_wandb)
    return _global_logger
