import torch
from typing import Dict, Any, List
from transformers import PreTrainedTokenizer

class DefaultCollator:
    def __init__(self, tokenizer: PreTrainedTokenizer, max_length: int = 1024):
        self.tokenizer = tokenizer
        self.max_length = max_length
        
    def __call__(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """整理batch数据"""
        # 提取输入和输出
        inputs = [s.get('input', '') for s in samples]
        outputs = [s.get('output', '') for s in samples]
        
        # 构建完整文本（input + output）
        texts = [f"{inp}{out}" for inp, out in zip(inputs, outputs)]
        
        # Tokenize
        tokenized = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors='pt'
        )
        
        # 创建labels（与input_ids相同，用于语言模型训练）
        labels = tokenized['input_ids'].clone()
        
        return {
            'input_ids': tokenized['input_ids'],
            'attention_mask': tokenized['attention_mask'],
            'labels': labels,
            'meta': [s.get('meta', {}) for s in samples]
        }
