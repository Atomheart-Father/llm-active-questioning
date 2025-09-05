#!/usr/bin/env python3
"""
CompactnessScore Calculator - Reasoning Structure Compactness Evaluation

Calculates compactness score based on connector usage and reasoning steps.
Rewards concise reasoning without verbose thinking traces.
"""

from typing import Dict, Any, List
from collections import defaultdict

class CompactnessScoreCalculator:
    """CompactnessScore计算器"""

    def __init__(self):
        # 定义推理连接词权重
        self.connector_weights = {
            "if": 0.8,      # 条件连接词
            "then": 0.8,    # 结果连接词
            "because": 0.9, # 因果连接词
            "therefore": 0.9, # 结论连接词
            "and": 0.6,     # 并列连接词
            "or": 0.6,      # 选择连接词
            "but": 0.7,     # 转折连接词
            "compare": 0.8, # 比较连接词
            "contrast": 0.8  # 对照连接词
        }

        self.max_steps = 5
        self.ideal_connector_ratio = 0.4  # 理想的连接词比例

    def calculate_compactness_score(self, sample: Dict[str, Any]) -> float:
        """
        计算单个样本的紧凑性分数

        Args:
            sample: 样本数据

        Returns:
            紧凑性分数 (0.0-1.0)
        """
        reasoning = sample.get("reasoning", {})
        compact_rationale = reasoning.get("compact_rationale", {})

        if not compact_rationale:
            return 0.0

        connectors = compact_rationale.get("connectors", [])
        steps = compact_rationale.get("steps", 0)

        # 计算连接词得分
        connector_score = self._calculate_connector_score(connectors)

        # 计算步骤得分
        step_score = self._calculate_step_score(steps)

        # 计算综合得分
        compactness_score = (connector_score + step_score) / 2

        return min(1.0, max(0.0, compactness_score))

    def _calculate_connector_score(self, connectors: List[str]) -> float:
        """计算连接词得分"""
        if not connectors:
            return 0.0

        # 计算连接词质量得分
        total_weight = 0.0
        for connector in connectors:
            weight = self.connector_weights.get(connector.lower(), 0.5)
            total_weight += weight

        avg_weight = total_weight / len(connectors)

        # 计算连接词多样性得分
        unique_connectors = set(c.lower() for c in connectors)
        diversity_score = len(unique_connectors) / len(connectors)

        # 计算比例合理性得分
        connector_ratio = len(connectors) / max(1, len(connectors) * 2)  # 期望每个连接词对应约2个步骤
        ratio_score = 1.0 - abs(connector_ratio - self.ideal_connector_ratio)

        # 综合评分
        connector_score = (avg_weight + diversity_score + ratio_score) / 3

        return connector_score

    def _calculate_step_score(self, steps: int) -> float:
        """计算步骤得分"""
        if steps == 0:
            return 0.0

        # 理想步骤范围：2-4步
        if 2 <= steps <= 4:
            step_score = 1.0
        elif steps == 1 or steps == 5:
            step_score = 0.8
        else:
            step_score = 0.5

        # 惩罚过多步骤（降低紧凑性）
        if steps > self.max_steps:
            penalty = (steps - self.max_steps) / self.max_steps
            step_score = max(0.1, step_score - penalty)

        return step_score

    def calculate_batch_compactness(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        计算批次的紧凑性统计

        Args:
            samples: 样本列表

        Returns:
            紧凑性统计
        """
        if not samples:
            return {"avg_score": 0.0, "distribution": {}, "connector_usage": {}}

        scores = []
        connector_usage = defaultdict(int)

        for sample in samples:
            score = self.calculate_compactness_score(sample)
            scores.append(score)

            # 统计连接词使用
            reasoning = sample.get("reasoning", {})
            compact_rationale = reasoning.get("compact_rationale", {})
            connectors = compact_rationale.get("connectors", [])

            for connector in connectors:
                connector_usage[connector.lower()] += 1

        # 计算平均分
        avg_score = sum(scores) / len(scores) if scores else 0.0

        # 计算分数分布
        distribution = self._calculate_score_distribution(scores)

        # 计算连接词使用统计
        total_connector_usage = sum(connector_usage.values())
        connector_stats = {}
        for connector, count in connector_usage.items():
            connector_stats[connector] = {
                "count": count,
                "percentage": count / total_connector_usage if total_connector_usage > 0 else 0
            }

        return {
            "avg_score": avg_score,
            "distribution": distribution,
            "connector_usage": dict(connector_stats),
            "total_samples": len(samples)
        }

    def _calculate_score_distribution(self, scores: List[float]) -> Dict[str, int]:
        """计算分数分布"""
        distribution = defaultdict(int)

        for score in scores:
            if score >= 0.8:
                distribution["excellent"] += 1
            elif score >= 0.6:
                distribution["good"] += 1
            elif score >= 0.4:
                distribution["fair"] += 1
            else:
                distribution["poor"] += 1

        return dict(distribution)

    def analyze_compactness_patterns(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析紧凑性模式

        Args:
            samples: 样本列表

        Returns:
            模式分析
        """
        patterns = {
            "by_task_type": defaultdict(list),
            "by_source": defaultdict(list),
            "correlation_with_quality": {"scores": [], "quality_indicators": []}
        }

        for sample in samples:
            score = self.calculate_compactness_score(sample)
            source = sample.get("source", "unknown")

            # 推断任务类型
            task_type = self._infer_task_type(sample)

            patterns["by_task_type"][task_type].append(score)
            patterns["by_source"][source].append(score)

            # 收集质量相关指标
            patterns["correlation_with_quality"]["scores"].append(score)

            # 简单的质量指标（是否有完整字段）
            quality_score = self._calculate_simple_quality(sample)
            patterns["correlation_with_quality"]["quality_indicators"].append(quality_score)

        # 计算各模式的平均分
        for pattern_type in ["by_task_type", "by_source"]:
            for key, scores in patterns[pattern_type].items():
                if scores:
                    patterns[pattern_type][key] = sum(scores) / len(scores)
                else:
                    patterns[pattern_type][key] = 0.0

        # 计算相关性
        scores = patterns["correlation_with_quality"]["scores"]
        quality_indicators = patterns["correlation_with_quality"]["quality_indicators"]

        if scores and quality_indicators:
            correlation = self._calculate_correlation(scores, quality_indicators)
            patterns["correlation_with_quality"]["correlation"] = correlation

        return patterns

    def _infer_task_type(self, sample: Dict[str, Any]) -> str:
        """推断任务类型"""
        labels = sample.get("labels", {})

        if "oracle_answer" in labels:
            return "AR"
        elif "prediction" in sample:
            return "RSD"
        elif "ask_options" in labels or "branch_map" in labels:
            return "ALC"
        else:
            return "unknown"

    def _calculate_simple_quality(self, sample: Dict[str, Any]) -> float:
        """计算简单的质量指标"""
        quality_indicators = [
            1 if sample.get("turns") else 0,
            1 if sample.get("labels", {}).get("ask_required") is not None else 0,
            1 if sample.get("reasoning", {}).get("actions") else 0,
            1 if sample.get("source") else 0
        ]

        return sum(quality_indicators) / len(quality_indicators)

    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """计算皮尔逊相关系数"""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi * xi for xi in x)
        sum_y2 = sum(yi * yi for yi in y)

        numerator = n * sum_xy - sum_x * sum_y
        denominator = ((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y)) ** 0.5

        if denominator == 0:
            return 0.0

        return numerator / denominator
