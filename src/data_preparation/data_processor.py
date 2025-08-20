"""
数据处理模块
负责数据格式统一、混合和预处理
"""

import random
from typing import Dict, List, Any, Tuple
from datasets import Dataset, concatenate_datasets
import numpy as np

from ..utils.config import get_config
from ..utils.logging import get_logger


class DataProcessor:
    """数据处理器"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        self.dataset_weights = self.config.get("data.dataset_weights", {})
    
    def format_conversation(self, sample: Dict[str, Any]) -> Dict[str, str]:
        """
        将样本转换为统一的对话格式
        
        Args:
            sample: 原始样本
            
        Returns:
            格式化后的对话样本
        """
        dataset_type = sample.get('dataset', 'unknown')
        
        if dataset_type == 'ambigqa':
            return self._format_ambigqa(sample)
        elif dataset_type == 'gsm8k':
            return self._format_gsm8k(sample)
        elif dataset_type == 'hotpotqa':
            return self._format_hotpotqa(sample)
        elif dataset_type == 'lima':
            return self._format_lima(sample)
        else:
            return self._format_generic(sample)
    
    def _format_ambigqa(self, sample: Dict[str, Any]) -> Dict[str, str]:
        """格式化AmbigQA样本"""
        question = sample['question']
        context = sample.get('context', '')
        answers = sample.get('answers', [])
        
        # 构建用户提示
        if context:
            user_input = f"基于以下上下文回答问题，如果问题有歧义，请指出并给出不同理解下的答案。\n\n上下文: {context}\n\n问题: {question}"
        else:
            user_input = f"请回答以下问题，如果问题有歧义，请指出并给出不同理解下的答案。\n\n问题: {question}"
        
        # 构建助手回答
        if len(answers) > 1:
            assistant_output = "这个问题存在歧义，以下是不同理解下的答案：\n"
            for i, answer in enumerate(answers, 1):
                assistant_output += f"{i}. {answer}\n"
        elif len(answers) == 1:
            assistant_output = f"答案：{answers[0]}"
        else:
            assistant_output = "很抱歉，我无法基于提供的信息回答这个问题。"
        
        return {
            'user': user_input,
            'assistant': assistant_output,
            'dataset': 'ambigqa',
            'type': 'ambiguous_qa'
        }
    
    def _format_gsm8k(self, sample: Dict[str, Any]) -> Dict[str, str]:
        """格式化GSM8K样本"""
        question = sample['question']
        answer = sample.get('answer', '')
        
        user_input = f"请解决以下数学问题，给出详细的解题步骤：\n\n{question}"
        
        # 解析答案中的推理步骤和最终答案
        if '####' in answer:
            reasoning, final_answer = answer.split('####')
            assistant_output = f"让我逐步解决这个问题：\n\n{reasoning.strip()}\n\n因此，最终答案是：{final_answer.strip()}"
        else:
            assistant_output = f"解答：{answer}"
        
        return {
            'user': user_input,
            'assistant': assistant_output,
            'dataset': 'gsm8k',
            'type': 'math_problem'
        }
    
    def _format_hotpotqa(self, sample: Dict[str, Any]) -> Dict[str, str]:
        """格式化HotpotQA样本"""
        question = sample['question']
        answer = sample.get('answer', '')
        context = sample.get('context', '')
        
        if context:
            user_input = f"基于以下信息回答问题，需要进行多步推理：\n\n{context}\n\n问题: {question}"
        else:
            user_input = f"请回答以下需要多步推理的问题：\n\n{question}"
        
        assistant_output = f"通过分析提供的信息，答案是：{answer}"
        
        return {
            'user': user_input,
            'assistant': assistant_output,
            'dataset': 'hotpotqa',
            'type': 'multi_hop_qa'
        }
    
    def _format_lima(self, sample: Dict[str, Any]) -> Dict[str, str]:
        """格式化LIMA样本"""
        question = sample['question']
        answer = sample.get('answer', '')
        
        return {
            'user': question,
            'assistant': answer,
            'dataset': 'lima',
            'type': 'general_qa'
        }
    
    def _format_generic(self, sample: Dict[str, Any]) -> Dict[str, str]:
        """格式化通用样本"""
        question = sample.get('question', sample.get('input', ''))
        answer = sample.get('answer', sample.get('output', ''))
        
        return {
            'user': question,
            'assistant': answer,
            'dataset': sample.get('dataset', 'unknown'),
            'type': sample.get('type', 'general')
        }
    
    def sample_dataset(self, dataset: Dataset, max_samples: int, split: str = 'train') -> Dataset:
        """
        从数据集中采样指定数量的样本
        
        Args:
            dataset: 原始数据集
            max_samples: 最大样本数
            split: 数据集分割（train/validation/test）
            
        Returns:
            采样后的数据集
        """
        # 过滤指定分割的数据
        filtered_data = [item for item in dataset if item.get('split', 'train') == split]
        
        if len(filtered_data) <= max_samples:
            return Dataset.from_list(filtered_data)
        
        # 随机采样
        sampled_indices = random.sample(range(len(filtered_data)), max_samples)
        sampled_data = [filtered_data[i] for i in sampled_indices]
        
        return Dataset.from_list(sampled_data)
    
    def mix_datasets(self, datasets: Dict[str, Dataset], split: str = 'train') -> Dataset:
        """
        按配置比例混合数据集
        
        Args:
            datasets: 数据集字典
            split: 数据集分割
            
        Returns:
            混合后的数据集
        """
        self.logger.info(f"开始混合{split}数据集...")
        
        max_samples_per_dataset = self.config.get("data.max_samples_per_dataset", 10000)
        mixed_data = []
        
        # 计算每个数据集的样本数
        total_weight = sum(self.dataset_weights.values())
        dataset_samples = {}
        
        for dataset_name, weight in self.dataset_weights.items():
            if dataset_name in datasets:
                target_samples = int((weight / total_weight) * max_samples_per_dataset)
                dataset_samples[dataset_name] = target_samples
                self.logger.info(f"{dataset_name}: 目标样本数 {target_samples}")
        
        # 从每个数据集采样并格式化
        for dataset_name, target_samples in dataset_samples.items():
            if dataset_name in datasets:
                # 采样
                sampled_dataset = self.sample_dataset(
                    datasets[dataset_name], 
                    target_samples, 
                    split
                )
                
                # 格式化
                formatted_samples = []
                for sample in sampled_dataset:
                    try:
                        formatted_sample = self.format_conversation(sample)
                        formatted_samples.append(formatted_sample)
                    except Exception as e:
                        self.logger.warning(f"格式化样本失败: {e}")
                        continue
                
                mixed_data.extend(formatted_samples)
                self.logger.info(f"已添加{dataset_name}数据集: {len(formatted_samples)}条样本")
        
        # 随机打乱
        random.shuffle(mixed_data)
        
        self.logger.info(f"数据集混合完成，总样本数: {len(mixed_data)}")
        return Dataset.from_list(mixed_data)
    
    def split_dataset(self, dataset: Dataset, train_ratio: float = None, val_ratio: float = None) -> Tuple[Dataset, Dataset]:
        """
        分割数据集为训练集和验证集
        
        Args:
            dataset: 原始数据集
            train_ratio: 训练集比例
            val_ratio: 验证集比例
            
        Returns:
            (训练集, 验证集)
        """
        if train_ratio is None:
            train_ratio = self.config.get("data.train_split", 0.9)
        if val_ratio is None:
            val_ratio = self.config.get("data.val_split", 0.1)
        
        # 确保比例和为1
        total_ratio = train_ratio + val_ratio
        if total_ratio != 1.0:
            train_ratio = train_ratio / total_ratio
            val_ratio = val_ratio / total_ratio
        
        dataset_size = len(dataset)
        train_size = int(dataset_size * train_ratio)
        
        # 随机分割
        indices = list(range(dataset_size))
        random.shuffle(indices)
        
        train_indices = indices[:train_size]
        val_indices = indices[train_size:]
        
        train_data = [dataset[i] for i in train_indices]
        val_data = [dataset[i] for i in val_indices]
        
        self.logger.info(f"数据集分割完成: 训练集 {len(train_data)} 条，验证集 {len(val_data)} 条")
        
        return Dataset.from_list(train_data), Dataset.from_list(val_data)
    
    def prepare_training_data(self, datasets: Dict[str, Dataset], use_validation: bool = True) -> Tuple[Dataset, Dataset]:
        """
        准备训练数据
        
        Args:
            datasets: 原始数据集字典
            use_validation: 是否创建验证集
            
        Returns:
            (训练集, 验证集)
        """
        self.logger.info("开始准备训练数据...")
        
        # 混合训练数据
        train_dataset = self.mix_datasets(datasets, split='train')
        
        if use_validation:
            # 如果有现成的验证集，使用它们；否则从训练集分割
            val_datasets_exist = any(
                any(item.get('split') == 'validation' for item in dataset)
                for dataset in datasets.values()
            )
            
            if val_datasets_exist:
                val_dataset = self.mix_datasets(datasets, split='validation')
            else:
                # 从训练集分割验证集
                train_dataset, val_dataset = self.split_dataset(train_dataset)
        else:
            val_dataset = Dataset.from_list([])
        
        self.logger.info(f"训练数据准备完成: 训练集 {len(train_dataset)} 条，验证集 {len(val_dataset)} 条")
        
        return train_dataset, val_dataset
