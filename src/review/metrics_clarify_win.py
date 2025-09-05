#!/usr/bin/env python3
"""
Clarify-Win-Rate Calculator - Preference-based Clarification Effectiveness

Calculates the rate at which clarification approaches win over direct answers.
Implements preference analysis for FT-Pref pairs.
"""

from typing import Dict, Any, List
from collections import defaultdict

class ClarifyWinRateCalculator:
    """Clarify-Win-Rate计算器"""

    def __init__(self):
        self.win_threshold = 0.6  # Clarify-Win-Rate目标阈值

    def calculate_clarify_win_rate(self, samples: List[Dict[str, Any]]) -> float:
        """
        计算Clarify-Win-Rate

        Args:
            samples: 样本列表（包含preference字段）

        Returns:
            Clarify-Win-Rate (0.0-1.0)
        """
        clarify_wins = 0
        total_with_preference = 0

        for sample in samples:
            preference = sample.get("preference")
            if not preference:
                continue

            total_with_preference += 1

            # 检查clarify是否获胜
            if self._clarify_wins_preference(preference):
                clarify_wins += 1

        if total_with_preference == 0:
            return 0.0

        win_rate = clarify_wins / total_with_preference
        return win_rate

    def _clarify_wins_preference(self, preference: Dict[str, Any]) -> bool:
        """检查clarify是否在偏好中获胜"""
        clarify_score = preference.get("clarify_then_answer", {}).get("score", 0)
        direct_score = preference.get("direct_answer", {}).get("score", 0)
        label = preference.get("label", "")

        # 基于分数比较
        if clarify_score > direct_score:
            return True

        # 基于标签
        if label == "clarify":
            return True

        return False

    def calculate_preference_distribution(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        计算偏好分布统计

        Args:
            samples: 样本列表

        Returns:
            分布统计
        """
        stats = {
            "total_samples": len(samples),
            "samples_with_preference": 0,
            "clarify_wins": 0,
            "direct_wins": 0,
            "ties": 0,
            "avg_clarify_score": 0.0,
            "avg_direct_score": 0.0,
            "score_ranges": defaultdict(int)
        }

        clarify_scores = []
        direct_scores = []

        for sample in samples:
            preference = sample.get("preference")
            if not preference:
                continue

            stats["samples_with_preference"] += 1

            clarify_score = preference.get("clarify_then_answer", {}).get("score", 0)
            direct_score = preference.get("direct_answer", {}).get("score", 0)

            clarify_scores.append(clarify_score)
            direct_scores.append(direct_score)

            # 统计胜负
            if clarify_score > direct_score:
                stats["clarify_wins"] += 1
            elif direct_score > clarify_score:
                stats["direct_wins"] += 1
            else:
                stats["ties"] += 1

            # 统计分数范围
            score_diff = abs(clarify_score - direct_score)
            if score_diff < 0.1:
                stats["score_ranges"]["tie"] += 1
            elif score_diff < 0.3:
                stats["score_ranges"]["close"] += 1
            else:
                stats["score_ranges"]["clear"] += 1

        # 计算平均分
        if clarify_scores:
            stats["avg_clarify_score"] = sum(clarify_scores) / len(clarify_scores)
        if direct_scores:
            stats["avg_direct_score"] = sum(direct_scores) / len(direct_scores)

        # 计算win rate
        total_decisions = stats["clarify_wins"] + stats["direct_wins"]
        if total_decisions > 0:
            stats["clarify_win_rate"] = stats["clarify_wins"] / total_decisions
        else:
            stats["clarify_win_rate"] = 0.0

        return stats

    def analyze_preference_patterns(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析偏好模式

        Args:
            samples: 样本列表

        Returns:
            模式分析结果
        """
        patterns = {
            "by_source": defaultdict(lambda: {"clarify_wins": 0, "total": 0}),
            "by_complexity": defaultdict(lambda: {"clarify_wins": 0, "total": 0}),
            "by_ambiguity_count": defaultdict(lambda: {"clarify_wins": 0, "total": 0})
        }

        for sample in samples:
            preference = sample.get("preference")
            if not preference:
                continue

            source = sample.get("source", "unknown")
            labels = sample.get("labels", {})

            # 按来源统计
            patterns["by_source"][source]["total"] += 1
            if self._clarify_wins_preference(preference):
                patterns["by_source"][source]["clarify_wins"] += 1

            # 按复杂度统计（基于歧义类型数量）
            ambiguity_count = len(labels.get("ambiguity_types", []))
            complexity_level = "low" if ambiguity_count <= 1 else "medium" if ambiguity_count <= 3 else "high"
            patterns["by_complexity"][complexity_level]["total"] += 1
            if self._clarify_wins_preference(preference):
                patterns["by_complexity"][complexity_level]["clarify_wins"] += 1

            # 按歧义数量统计
            patterns["by_ambiguity_count"][ambiguity_count]["total"] += 1
            if self._clarify_wins_preference(preference):
                patterns["by_ambiguity_count"][ambiguity_count]["clarify_wins"] += 1

        # 计算各模式的win rate
        for pattern_type, pattern_data in patterns.items():
            for key, data in pattern_data.items():
                if data["total"] > 0:
                    data["win_rate"] = data["clarify_wins"] / data["total"]
                else:
                    data["win_rate"] = 0.0

        return dict(patterns)
