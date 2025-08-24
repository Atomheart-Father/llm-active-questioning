import json
import jsonlines
from typing import List, Dict, Any, Iterator
from pathlib import Path

class JSONLReader:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        
    def read_samples(self) -> List[Dict[str, Any]]:
        """读取所有样本"""
        if not self.file_path.exists():
            raise FileNotFoundError(f"数据文件不存在: {self.file_path}")
            
        samples = []
        with jsonlines.open(self.file_path) as reader:
            for obj in reader:
                samples.append(obj)
                
        return samples
        
    def iter_samples(self) -> Iterator[Dict[str, Any]]:
        """迭代读取样本"""
        if not self.file_path.exists():
            raise FileNotFoundError(f"数据文件不存在: {self.file_path}")
            
        with jsonlines.open(self.file_path) as reader:
            for obj in reader:
                yield obj
                
    def __len__(self) -> int:
        """返回样本数量"""
        if not self.file_path.exists():
            return 0
            
        count = 0
        with jsonlines.open(self.file_path) as reader:
            for _ in reader:
                count += 1
        return count
