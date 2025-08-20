"""
数据加载模块
负责加载和预处理各种数据集
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datasets import load_dataset, Dataset
import numpy as np

from ..utils.config import get_config
from ..utils.logging import get_logger


class DatasetLoader:
    """数据集加载器"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        self.data_dir = Path(self.config.get("data.data_dir", "./data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def load_ambigqa(self) -> Dataset:
        """
        加载AmbigQA数据集
        
        Returns:
            处理后的Dataset
        """
        try:
            self.logger.info("正在加载AmbigQA数据集...")
            
            # 从Hugging Face加载
            dataset = load_dataset("ambig_qa", "light")
            
            # 处理数据格式
            processed_data = []
            for split_name in ['train', 'validation']:
                if split_name in dataset:
                    for item in dataset[split_name]:
                        # 构建标准格式
                        processed_item = {
                            'dataset': 'ambigqa',
                            'question': item['question'],
                            'context': item.get('context', ''),
                            'answers': item.get('answers', []),
                            'annotations': item.get('annotations', []),
                            'type': 'ambiguous_qa',
                            'split': split_name
                        }
                        processed_data.append(processed_item)
            
            self.logger.info(f"AmbigQA数据集加载完成，共{len(processed_data)}条样本")
            return Dataset.from_list(processed_data)
            
        except Exception as e:
            self.logger.error(f"加载AmbigQA数据集失败: {e}")
            return Dataset.from_list([])
    
    def load_gsm8k(self) -> Dataset:
        """
        加载GSM8K数学问题数据集
        
        Returns:
            处理后的Dataset
        """
        try:
            self.logger.info("正在加载GSM8K数据集...")
            
            # 从Hugging Face加载
            dataset = load_dataset("gsm8k", "main")
            
            processed_data = []
            for split_name in ['train', 'test']:
                if split_name in dataset:
                    for item in dataset[split_name]:
                        processed_item = {
                            'dataset': 'gsm8k',
                            'question': item['question'],
                            'answer': item['answer'],
                            'type': 'math_problem',
                            'split': split_name
                        }
                        processed_data.append(processed_item)
            
            self.logger.info(f"GSM8K数据集加载完成，共{len(processed_data)}条样本")
            return Dataset.from_list(processed_data)
            
        except Exception as e:
            self.logger.error(f"加载GSM8K数据集失败: {e}")
            return Dataset.from_list([])
    
    def load_hotpotqa(self) -> Dataset:
        """
        加载HotpotQA多跳推理数据集
        
        Returns:
            处理后的Dataset
        """
        try:
            self.logger.info("正在加载HotpotQA数据集...")
            
            # 从Hugging Face加载
            dataset = load_dataset("hotpot_qa", "fullwiki")
            
            processed_data = []
            for split_name in ['train', 'validation']:
                if split_name in dataset:
                    for item in dataset[split_name]:
                        # 构建上下文
                        context_parts = []
                        if 'context' in item and 'sentences' in item['context']:
                            for title, sentences in item['context']['sentences']:
                                context_parts.append(f"## {title}\n" + "\n".join(sentences))
                        
                        processed_item = {
                            'dataset': 'hotpotqa',
                            'question': item['question'],
                            'answer': item.get('answer', ''),
                            'context': "\n\n".join(context_parts),
                            'supporting_facts': item.get('supporting_facts', []),
                            'type': 'multi_hop_qa',
                            'split': split_name
                        }
                        processed_data.append(processed_item)
            
            self.logger.info(f"HotpotQA数据集加载完成，共{len(processed_data)}条样本")
            return Dataset.from_list(processed_data)
            
        except Exception as e:
            self.logger.error(f"加载HotpotQA数据集失败: {e}")
            return Dataset.from_list([])
    
    def load_lima(self) -> Dataset:
        """
        加载LIMA高质量对话数据集
        
        Returns:
            处理后的Dataset
        """
        try:
            self.logger.info("正在加载LIMA数据集...")
            
            # 从Hugging Face加载
            dataset = load_dataset("GAIR/lima", trust_remote_code=True)
            
            processed_data = []
            for split_name in dataset.keys():
                for item in dataset[split_name]:
                    conversations = item.get('conversations', [])
                    if len(conversations) >= 2:
                        processed_item = {
                            'dataset': 'lima',
                            'question': conversations[0],  # 用户输入
                            'answer': conversations[1],    # 助手回答
                            'type': 'general_qa',
                            'split': split_name
                        }
                        processed_data.append(processed_item)
            
            self.logger.info(f"LIMA数据集加载完成，共{len(processed_data)}条样本")
            return Dataset.from_list(processed_data)
            
        except Exception as e:
            self.logger.error(f"加载LIMA数据集失败: {e}")
            return Dataset.from_list([])
    
    def create_mock_datasets(self) -> Dict[str, Dataset]:
        """
        创建模拟数据集（用于测试）
        
        Returns:
            模拟数据集字典
        """
        self.logger.info("创建模拟数据集用于测试...")
        
        # AmbigQA模拟数据
        ambigqa_data = [
            {
                'dataset': 'ambigqa',
                'question': 'What is the capital of France?',
                'context': 'France is a country in Western Europe.',
                'answers': ['Paris'],
                'type': 'ambiguous_qa',
                'split': 'train'
            },
            {
                'dataset': 'ambigqa', 
                'question': 'Who wrote Romeo and Juliet?',
                'context': 'Romeo and Juliet is a tragedy written by William Shakespeare.',
                'answers': ['William Shakespeare', 'Shakespeare'],
                'type': 'ambiguous_qa',
                'split': 'train'
            }
        ]
        
        # GSM8K模拟数据
        gsm8k_data = [
            {
                'dataset': 'gsm8k',
                'question': 'Janet has 3 ducks. Each duck lays 1 egg per day. How many eggs does Janet collect in a week?',
                'answer': 'Janet has 3 ducks that each lay 1 egg per day, so she gets 3*1 = 3 eggs per day. In a week (7 days), she gets 3*7 = 21 eggs. #### 21',
                'type': 'math_problem',
                'split': 'train'
            }
        ]
        
        # HotpotQA模拟数据
        hotpotqa_data = [
            {
                'dataset': 'hotpotqa',
                'question': 'What is the birth year of the director of Titanic?',
                'answer': '1954',
                'context': '## Titanic (1997 film)\nTitanic is a 1997 American epic romance and disaster film directed by James Cameron.\n\n## James Cameron\nJames Francis Cameron (born August 16, 1954) is a Canadian filmmaker.',
                'type': 'multi_hop_qa',
                'split': 'train'
            }
        ]
        
        # LIMA模拟数据
        lima_data = [
            {
                'dataset': 'lima',
                'question': 'Explain the concept of artificial intelligence.',
                'answer': 'Artificial Intelligence (AI) refers to the simulation of human intelligence in machines that are programmed to think and learn like humans.',
                'type': 'general_qa',
                'split': 'train'
            }
        ]
        
        return {
            'ambigqa': Dataset.from_list(ambigqa_data),
            'gsm8k': Dataset.from_list(gsm8k_data),
            'hotpotqa': Dataset.from_list(hotpotqa_data),
            'lima': Dataset.from_list(lima_data)
        }
    
    def load_all_datasets(self, use_mock: bool = False) -> Dict[str, Dataset]:
        """
        加载所有数据集
        
        Args:
            use_mock: 是否使用模拟数据
            
        Returns:
            数据集字典
        """
        if use_mock:
            self.logger.info("使用模拟数据集进行测试")
            return self.create_mock_datasets()
        
        datasets = {}
        
        # 加载各个数据集
        loaders = {
            'ambigqa': self.load_ambigqa,
            'gsm8k': self.load_gsm8k,
            'hotpotqa': self.load_hotpotqa,
            'lima': self.load_lima
        }
        
        for name, loader_func in loaders.items():
            try:
                dataset = loader_func()
                if len(dataset) > 0:
                    datasets[name] = dataset
                    self.logger.info(f"成功加载{name}数据集: {len(dataset)}条样本")
                else:
                    self.logger.warning(f"{name}数据集为空")
            except Exception as e:
                self.logger.error(f"加载{name}数据集失败: {e}")
        
        return datasets
