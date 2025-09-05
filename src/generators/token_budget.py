#!/usr/bin/env python3
"""
Token Budget Allocator - Adaptive Token Allocation System

Dynamically allocates token budgets based on sample complexity scoring.
Prioritizes FINAL/clarify_tree fields and handles truncation recovery.
"""

import re
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class TokenBudgetConfig:
    """Token配额配置"""
    min_tokens: int = 512
    max_tokens: int = 3072
    base_tokens_alc: int = 768
    base_tokens_ar: int = 1536
    base_tokens_rsd: int = 1024

    # 复杂度权重
    source_weights = {
        "hotpotqa": 1.2,    # 多跳推理
        "asqa": 1.1,        # 答案选择
        "ambigqa": 1.0,     # 歧义消除
        "gsm8k": 0.9,       # 数学推理
        "synthetic": 1.0    # 合成数据
    }

class TokenBudgetAllocator:
    """自适应Token配额分配器"""

    def __init__(self):
        self.config = TokenBudgetConfig()

    def calculate_complexity_score(self, sample: Dict[str, Any]) -> float:
        """
        计算样本复杂度分数

        Args:
            sample: 样本数据

        Returns:
            复杂度分数 (0.0-1.0)
        """
        score_components = []

        # 1. 来源权重
        source = sample.get("source", "synthetic")
        source_weight = self._get_source_weight(source)
        score_components.append(source_weight)

        # 2. 查询长度复杂度
        user_query = self._extract_user_query(sample)
        length_score = self._calculate_length_complexity(user_query)
        score_components.append(length_score)

        # 3. 歧义类型复杂度
        ambiguity_score = self._calculate_ambiguity_complexity(sample)
        score_components.append(ambiguity_score)

        # 4. 多跳/数值复杂度
        structural_score = self._calculate_structural_complexity(sample)
        score_components.append(structural_score)

        # 5. 特殊字段复杂度
        field_score = self._calculate_field_complexity(sample)
        score_components.append(field_score)

        # 计算加权平均
        final_score = sum(score_components) / len(score_components)

        # 归一化到0-1
        return max(0.0, min(1.0, final_score))

    def allocate_tokens(self, task: str, complexity_score: float) -> int:
        """
        根据任务类型和复杂度分配token

        Args:
            task: 任务类型 (ALC/AR/RSD)
            complexity_score: 复杂度分数

        Returns:
            分配的token数量
        """
        # 获取基础token数
        base_tokens = self._get_base_tokens(task)

        # 根据复杂度调整
        if complexity_score > 0.8:  # 高复杂度
            allocated = int(base_tokens * 1.5)
        elif complexity_score > 0.6:  # 中高复杂度
            allocated = int(base_tokens * 1.25)
        elif complexity_score < 0.3:  # 低复杂度
            allocated = int(base_tokens * 0.8)
        else:  # 中等复杂度
            allocated = base_tokens

        # 确保在范围内
        return max(self.config.min_tokens, min(self.config.max_tokens, allocated))

    def allocate_tokens_for_sample(self, sample: Dict[str, Any]) -> int:
        """
        为单个样本分配token（完整流程）

        Args:
            sample: 样本数据

        Returns:
            分配的token数量
        """
        # 从样本中推断任务类型
        task = self._infer_task_type(sample)

        # 计算复杂度
        complexity_score = self.calculate_complexity_score(sample)

        # 分配token
        allocated_tokens = self.allocate_tokens(task, complexity_score)

        return allocated_tokens

    def handle_truncation_recovery(self, original_allocation: int,
                                  is_final_field: bool = False) -> int:
        """
        处理截断恢复的token重新分配

        Args:
            original_allocation: 原始分配
            is_final_field: 是否为FINAL/clarify_tree字段

        Returns:
            新的token分配
        """
        if is_final_field:
            # 优先给FINAL/clarify_tree升配
            recovery_tokens = int(original_allocation * 1.5)
        else:
            # 普通字段升配
            recovery_tokens = int(original_allocation * 1.25)

        return min(recovery_tokens, self.config.max_tokens)

    def _get_source_weight(self, source: str) -> float:
        """获取来源权重"""
        # 标准化来源名称
        source_key = source.lower().replace("synthetic-", "")

        for key, weight in self.config.source_weights.items():
            if key in source_key:
                return weight

        return 1.0  # 默认权重

    def _extract_user_query(self, sample: Dict[str, Any]) -> str:
        """提取用户查询"""
        turns = sample.get("turns", [])
        for turn in turns:
            if turn.get("role") == "user":
                return turn.get("text", "")
        return ""

    def _calculate_length_complexity(self, query: str) -> float:
        """计算查询长度复杂度"""
        word_count = len(query.split())
        char_count = len(query)

        # 基于词数和字符数的复杂度
        length_score = (word_count / 50.0) + (char_count / 200.0)
        return min(1.0, length_score / 2.0)

    def _calculate_ambiguity_complexity(self, sample: Dict[str, Any]) -> float:
        """计算歧义复杂度"""
        labels = sample.get("labels", {})
        ambiguity_types = labels.get("ambiguity_types", [])

        # 歧义类型数量
        type_count = len(ambiguity_types)

        # 特殊歧义类型的权重
        high_complexity_types = ["scope", "context", "method"]
        high_count = sum(1 for t in ambiguity_types if t in high_complexity_types)

        ambiguity_score = (type_count / 5.0) + (high_count / 3.0)
        return min(1.0, ambiguity_score)

    def _calculate_structural_complexity(self, sample: Dict[str, Any]) -> float:
        """计算结构复杂度（多跳/数值）"""
        query = self._extract_user_query(sample)

        structural_indicators = [
            query.count("然后") + query.count("接下来") + query.count("之后"),  # 序列指示
            query.count("多少") + query.count("几") + query.count("几时"),     # 数值问题
            len(re.findall(r'\d+', query)),  # 数字出现次数
            1 if "比较" in query or "对比" in query else 0,  # 比较操作
        ]

        structural_score = sum(structural_indicators) / 10.0
        return min(1.0, structural_score)

    def _calculate_field_complexity(self, sample: Dict[str, Any]) -> float:
        """计算特殊字段复杂度"""
        complexity_bonus = 0.0

        # clarify_tree深度
        clarify_tree = sample.get("clarify_tree", {})
        depth = clarify_tree.get("depth", 0)
        complexity_bonus += depth / 5.0

        # evidence_ids数量
        evidence_count = len(sample.get("evidence_ids", []))
        complexity_bonus += evidence_count / 10.0

        # reasoning steps
        reasoning = sample.get("reasoning", {})
        compact = reasoning.get("compact_rationale", {})
        steps = compact.get("steps", 0)
        complexity_bonus += steps / 8.0

        return min(0.5, complexity_bonus)  # 字段复杂度不超过0.5

    def _get_base_tokens(self, task: str) -> int:
        """获取任务的基础token数"""
        task = task.upper()
        if task == "ALC":
            return self.config.base_tokens_alc
        elif task == "AR":
            return self.config.base_tokens_ar
        elif task == "RSD":
            return self.config.base_tokens_rsd
        else:
            return self.config.base_tokens_alc  # 默认

    def _infer_task_type(self, sample: Dict[str, Any]) -> str:
        """从样本推断任务类型"""
        labels = sample.get("labels", {})

        # 基于字段特征推断
        if "oracle_answer" in labels:
            return "AR"  # 有oracle_answer的通常是AR
        elif "prediction" in sample:
            return "RSD"  # 有prediction的是RSD
        elif "ask_options" in labels or "branch_map" in labels:
            return "ALC"  # 有ATAC字段的是ALC
        else:
            return "ALC"  # 默认

    def get_allocation_stats(self, samples: list) -> Dict[str, Any]:
        """
        计算分配统计

        Args:
            samples: 样本列表

        Returns:
            分配统计信息
        """
        allocations = []
        complexities = []

        for sample in samples:
            complexity = self.calculate_complexity_score(sample)
            allocation = self.allocate_tokens_for_sample(sample)

            complexities.append(complexity)
            allocations.append(allocation)

        return {
            "total_samples": len(samples),
            "avg_complexity": sum(complexities) / len(complexities) if complexities else 0,
            "avg_allocation": sum(allocations) / len(allocations) if allocations else 0,
            "min_allocation": min(allocations) if allocations else 0,
            "max_allocation": max(allocations) if allocations else 0,
            "allocation_distribution": self._calculate_distribution(allocations)
        }

    def _calculate_distribution(self, values: list) -> Dict[str, int]:
        """计算分配分布"""
        if not values:
            return {}

        distribution = {}
        ranges = [(0, 512), (512, 1024), (1024, 1536), (1536, 2048), (2048, 3072), (3072, float('inf'))]

        for start, end in ranges:
            if end == float('inf'):
                count = sum(1 for v in values if v >= start)
                key = f"{start}+"
            else:
                count = sum(1 for v in values if start <= v < end)
                key = f"{start}-{end-1}"
            distribution[key] = count

        return distribution
