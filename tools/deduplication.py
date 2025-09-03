#!/usr/bin/env python3
"""Data Deduplication Tool

检测和移除重复样本，支持多种去重策略。
使用SimHash进行相似度检测。
"""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class DuplicateGroup:
    """重复组"""
    representative: Dict[str, Any]
    duplicates: List[Dict[str, Any]]
    similarity_score: float

class SimHashDeduplicator:
    """基于SimHash的去重器"""

    def __init__(self, similarity_threshold: float = 0.92):
        self.similarity_threshold = similarity_threshold
        self.hash_size = 64

    def compute_simhash(self, text: str) -> int:
        """计算SimHash值"""
        # 简单的SimHash实现
        words = self._tokenize(text)
        if not words:
            return 0

        # 初始化向量
        vector = [0] * self.hash_size

        for word in words:
            word_hash = int(hashlib.md5(word.encode()).hexdigest()[:16], 16)
            for i in range(self.hash_size):
                if word_hash & (1 << i):
                    vector[i] += 1
                else:
                    vector[i] -= 1

        # 生成指纹
        fingerprint = 0
        for i in range(self.hash_size):
            if vector[i] >= 0:
                fingerprint |= (1 << i)

        return fingerprint

    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        # 简单分词：按空格和标点分割
        import re
        words = re.findall(r'\w+', text.lower())
        return words

    def hamming_distance(self, hash1: int, hash2: int) -> int:
        """计算汉明距离"""
        return bin(hash1 ^ hash2).count('1')

    def similarity(self, hash1: int, hash2: int) -> float:
        """计算相似度"""
        distance = self.hamming_distance(hash1, hash2)
        return 1 - (distance / self.hash_size)

    def find_duplicates(self, samples: List[Dict[str, Any]]) -> List[DuplicateGroup]:
        """查找重复样本"""
        hash_to_samples = defaultdict(list)

        # 计算每个样本的SimHash
        for sample in samples:
            # 使用用户查询和助手回复作为去重依据
            text = self._extract_text_for_hashing(sample)
            simhash = self.compute_simhash(text)
            hash_to_samples[simhash].append(sample)

        duplicate_groups = []

        # 查找相似哈希
        processed_hashes = set()
        for hash1, samples1 in hash_to_samples.items():
            if hash1 in processed_hashes:
                continue

            similar_samples = []
            similar_samples.extend(samples1)

            # 查找相似的其他哈希
            for hash2, samples2 in hash_to_samples.items():
                if hash1 == hash2:
                    continue

                similarity = self.similarity(hash1, hash2)
                if similarity >= self.similarity_threshold:
                    similar_samples.extend(samples2)
                    processed_hashes.add(hash2)

            if len(similar_samples) > 1:
                # 选择最长的样本作为代表
                representative = max(similar_samples, key=lambda s: len(self._extract_text_for_hashing(s)))
                duplicates = [s for s in similar_samples if s != representative]

                group = DuplicateGroup(
                    representative=representative,
                    duplicates=duplicates,
                    similarity_score=self.similarity_threshold
                )
                duplicate_groups.append(group)

            processed_hashes.add(hash1)

        return duplicate_groups

    def _extract_text_for_hashing(self, sample: Dict[str, Any]) -> str:
        """提取用于哈希计算的文本"""
        texts = []

        # 用户查询
        for turn in sample.get("turns", []):
            if turn.get("role") == "user":
                texts.append(turn.get("text", ""))

        # 标签信息
        labels = sample.get("labels", {})
        if "good_question_set" in labels:
            texts.extend(labels["good_question_set"])

        if "ambiguity_types" in labels:
            texts.extend(labels["ambiguity_types"])

        return " ".join(texts)

class DataDeduplicator:
    """数据去重器（分域自适应阈值）"""

    def __init__(self):
        # 分域阈值配置
        self.domain_thresholds = {
            "planning": 0.90,  # ALC: 生活对话表述同义多，放宽阈值
            "qa": 0.95,        # AR: 题干短，轻微变化也视为重复
            "reasoning": 0.88, # RSD: 动作序列模板化风险高
            "creative": 0.90   # 默认值
        }

        self.stats = {
            "total_samples": 0,
            "unique_samples": 0,
            "duplicate_groups": 0,
            "removed_samples": 0,
            "domain_stats": {}  # 按域统计
        }

    def process_directory(self, input_dir: str, output_dir: str = None) -> Dict[str, Any]:
        """处理目录中的所有JSONL文件（分域去重）"""
        input_path = Path(input_dir)
        if not input_path.exists():
            raise FileNotFoundError(f"输入目录不存在: {input_dir}")

        all_samples = []
        file_samples = {}

        # 读取所有样本
        for jsonl_file in input_path.rglob("*.jsonl"):
            samples = self._load_jsonl(str(jsonl_file))
            all_samples.extend(samples)
            file_samples[str(jsonl_file)] = samples

        self.stats["total_samples"] = len(all_samples)

        # 分域去重
        unique_samples, duplicate_groups = self._domain_aware_deduplication(all_samples)

        # 统计信息
        self.stats["duplicate_groups"] = len(duplicate_groups)
        self.stats["removed_samples"] = sum(len(group.duplicates) for group in duplicate_groups)
        self.stats["unique_samples"] = len(unique_samples)

        # 保存去重结果
        if output_dir:
            self._save_deduplicated_samples(unique_samples, duplicate_groups, output_dir)

        # 生成报告
        report = self._generate_report(duplicate_groups)

        return {
            "stats": self.stats,
            "duplicate_groups": duplicate_groups,
            "report": report,
            "unique_samples": unique_samples
        }

    def _domain_aware_deduplication(self, samples: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[DuplicateGroup]]:
        """分域去重"""
        # 按域分组
        domain_samples = {}
        for sample in samples:
            domain = sample.get("domain", "general")
            if domain not in domain_samples:
                domain_samples[domain] = []
            domain_samples[domain].append(sample)

        all_unique = []
        all_duplicates = []

        # 对每个域分别去重
        for domain, domain_sample_list in domain_samples.items():
            threshold = self.domain_thresholds.get(domain, 0.92)
            deduplicator = SimHashDeduplicator(threshold)

            # 查找该域的重复
            duplicates = deduplicator.find_duplicates(domain_sample_list)

            # 保留唯一样本
            duplicate_ids = set()
            for group in duplicates:
                for duplicate in group.duplicates:
                    duplicate_ids.add(duplicate.get("id", ""))

            unique_in_domain = [
                s for s in domain_sample_list
                if s.get("id", "") not in duplicate_ids
            ]

            all_unique.extend(unique_in_domain)
            all_duplicates.extend(duplicates)

            # 记录域统计
            self.stats["domain_stats"][domain] = {
                "total": len(domain_sample_list),
                "unique": len(unique_in_domain),
                "duplicates": len(duplicates),
                "removed": len(domain_sample_list) - len(unique_in_domain),
                "threshold": threshold
            }

        return all_unique, all_duplicates

    def _load_jsonl(self, file_path: str) -> List[Dict[str, Any]]:
        """加载JSONL文件"""
        samples = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        samples.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return samples

    def _save_deduplicated_samples(self, all_samples: List[Dict[str, Any]],
                                 duplicate_groups: List[DuplicateGroup],
                                 output_dir: str):
        """保存去重后的样本"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 收集所有重复样本ID
        duplicate_ids = set()
        for group in duplicate_groups:
            for duplicate in group.duplicates:
                duplicate_ids.add(duplicate.get("id", ""))

        # 保存唯一样本
        unique_samples = [s for s in all_samples if s.get("id", "") not in duplicate_ids]

        output_file = output_path / "deduplicated.jsonl"
        with open(output_file, 'w', encoding='utf-8') as f:
            for sample in unique_samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')

        print(f"去重后样本已保存到: {output_file}")

    def _generate_report(self, duplicate_groups: List[DuplicateGroup]) -> str:
        """生成去重报告"""
        duplicate_rate = (self.stats["removed_samples"] / self.stats["total_samples"]) * 100 if self.stats["total_samples"] > 0 else 0

        report = f"""# 数据去重报告

## 统计信息
- **总样本数**: {self.stats["total_samples"]}
- **唯一样本数**: {self.stats["unique_samples"]}
- **重复组数**: {self.stats["duplicate_groups"]}
- **移除样本数**: {self.stats["removed_samples"]}
- **重复率**: {duplicate_rate:.2f}%

## 相似度设置
- **相似度阈值**: {self.similarity_threshold}
- **哈希大小**: {self.deduplicator.hash_size}位

## 重复详情
"""

        if duplicate_groups:
            for i, group in enumerate(duplicate_groups[:10], 1):  # 只显示前10组
                report += f"""
### 重复组 {i}
- **代表样本ID**: {group.representative.get('id', 'N/A')}
- **重复样本数**: {len(group.duplicates)}
- **相似度**: {group.similarity_score:.3f}

重复样本ID:
"""
                for duplicate in group.duplicates:
                    report += f"- {duplicate.get('id', 'N/A')}\n"

        if len(duplicate_groups) > 10:
            report += f"\n... 还有 {len(duplicate_groups) - 10} 个重复组"

        return report

def main():
    """主入口"""
    import sys

    if len(sys.argv) < 2:
        print("用法: python tools/deduplication.py <输入目录> [输出目录]")
        print("示例:")
        print("  python tools/deduplication.py data/gen/2025-09-03/")
        print("  python tools/deduplication.py data/gen/2025-09-03/ data/gen/2025-09-03/deduped/")
        sys.exit(1)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    similarity_threshold = float(os.getenv("DEDUPLICATION_THRESHOLD", "0.92"))

    deduplicator = DataDeduplicator(similarity_threshold)
    result = deduplicator.process_directory(input_dir, output_dir)

    # 保存报告
    report_file = Path("reports/deduplication_report.md")
    report_file.parent.mkdir(parents=True, exist_ok=True)

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(result["report"])

    print("
去重完成！"    print(f"总样本: {result['stats']['total_samples']}")
    print(f"唯一样本: {result['stats']['unique_samples']}")
    print(f"移除样本: {result['stats']['removed_samples']}")
    print(f"重复率: {(result['stats']['removed_samples'] / result['stats']['total_samples'] * 100):.2f}%" if result['stats']['total_samples'] > 0 else "0.00%")
    print(f"报告已保存: {report_file}")

if __name__ == "__main__":
    main()
