#!/usr/bin/env python3
"""
FT-Pref Pair Generator - Fine-tuning Preferences Pair Generation

Generates preference pairs for DPO/IPO training by creating direct_answer vs clarify_then_answer variants.
Implements scoring and winner selection for preference learning.
"""

import json
import copy
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from ..streaming_client import LLMClient
from ..schema_validator import SchemaValidator

@dataclass
class PrefConfig:
    """FT-Pref generation configuration"""
    clarify_win_threshold: float = 0.6  # Clarify-Win-Rate目标
    score_difference_margin: float = 0.1  # 胜者分数差最小阈值

class PrefPairGenerator:
    """FT-Pref偏好对生成器"""

    def __init__(self, client: LLMClient, validator: SchemaValidator):
        self.client = client
        self.validator = validator
        self.config = PrefConfig()

    def generate_preference_pair(self, user_query: str) -> Optional[Dict[str, Any]]:
        """
        生成包含偏好数据的样本

        Args:
            user_query: 用户查询

        Returns:
            包含preference字段的样本，或None
        """
        # 并行生成两个版本
        direct_sample = self._generate_direct_answer(user_query)
        clarify_sample = self._generate_clarify_answer(user_query)

        if not direct_sample or not clarify_sample:
            return None

        # 合并并添加偏好数据
        combined_sample = self._merge_samples_with_preference(
            direct_sample, clarify_sample, user_query
        )

        # 验证合并后的样本
        is_valid, errors = self.validator.validate_sample(combined_sample)
        if is_valid:
            return combined_sample
        else:
            print(f"Preference pair validation failed: {errors}")
            return None

    def _generate_direct_answer(self, user_query: str) -> Optional[Dict[str, Any]]:
        """生成直接回答版本"""
        prompt = f"""Given this user query: "{user_query}"

Generate a direct answer without asking for clarification. Output only JSON:

{{
  "turns": [
    {{"role": "user", "text": "{user_query}"}},
    {{"role": "model_target", "text": "<FINAL>[Direct answer here]</FINAL>"}}
  ],
  "labels": {{
    "ask_required": false,
    "good_question_set": []
  }},
  "reasoning": {{
    "actions": ["AWARE_GAP", "STOP_ASK", "FINALIZE"]
  }},
  "source": "synthetic-gemini"
}}"""

        return self._generate_single_response(prompt, "direct")

    def _generate_clarify_answer(self, user_query: str) -> Optional[Dict[str, Any]]:
        """生成澄清后回答版本"""
        prompt = f"""Given this user query: "{user_query}"

First ask for clarification, then provide an answer. Output only JSON:

{{
  "turns": [
    {{"role": "user", "text": "{user_query}"}},
    {{"role": "model_target", "text": "<ASK>[Clarification question]</ASK>"}}
  ],
  "labels": {{
    "ask_required": true,
    "good_question_set": ["[Clarification question]"]
  }},
  "reasoning": {{
    "actions": ["AWARE_GAP", "ASK", "STOP_ASK", "FINALIZE"]
  }},
  "source": "synthetic-gemini"
}}"""

        return self._generate_single_response(prompt, "clarify")

    def _generate_single_response(self, prompt: str, response_type: str) -> Optional[Dict[str, Any]]:
        """生成单个响应"""
        messages = [
            {"role": "system", "content": "You must output only valid JSON. No explanations, no markdown, no polite phrases."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.client.stream_chat(
                provider="gemini_flash",
                model="gemini_flash",
                messages=messages,
                max_tokens=1024,
                json_only=True
            )

            if isinstance(response, dict) and "text" in response:
                text = response["text"]
            else:
                text = str(response)

            # 解析JSON
            sample = json.loads(text.strip())
            return sample

        except Exception as e:
            print(f"Single response generation failed for {response_type}: {e}")
            return None

    def _merge_samples_with_preference(self, direct_sample: Dict[str, Any],
                                      clarify_sample: Dict[str, Any],
                                      user_query: str) -> Dict[str, Any]:
        """合并两个样本并添加偏好数据"""
        # 使用澄清版本作为基础
        merged_sample = copy.deepcopy(clarify_sample)

        # 计算偏好分数（简化算法）
        direct_score, clarify_score = self._calculate_preference_scores(
            direct_sample, clarify_sample, user_query
        )

        # 添加preference字段
        merged_sample["preference"] = {
            "direct_answer": {
                "score": direct_score
            },
            "clarify_then_answer": {
                "score": clarify_score
            },
            "label": "clarify" if clarify_score > direct_score else "direct"
        }

        return merged_sample

    def _calculate_preference_scores(self, direct_sample: Dict[str, Any],
                                   clarify_sample: Dict[str, Any],
                                   user_query: str) -> Tuple[float, float]:
        """
        计算偏好分数

        使用简化的启发式算法：
        - 基于查询复杂度
        - 基于回答完整性
        - 基于澄清必要性
        """
        # 分析查询复杂度
        query_complexity = self._analyze_query_complexity(user_query)

        # 分析直接回答质量
        direct_quality = self._analyze_answer_quality(direct_sample)

        # 分析澄清回答质量
        clarify_quality = self._analyze_answer_quality(clarify_sample)

        # 计算分数
        if query_complexity > 0.7:  # 复杂查询
            direct_score = direct_quality * 0.6  # 直接回答分数较低
            clarify_score = clarify_quality * 0.9  # 澄清回答分数较高
        else:  # 简单查询
            direct_score = direct_quality * 0.8  # 直接回答分数较高
            clarify_score = clarify_quality * 0.7  # 澄清回答分数较低

        # 确保分数在0-1范围内
        direct_score = max(0.0, min(1.0, direct_score))
        clarify_score = max(0.0, min(1.0, clarify_score))

        # 如果分数差距太小，放大差异
        if abs(direct_score - clarify_score) < self.config.score_difference_margin:
            if query_complexity > 0.5:
                clarify_score = min(1.0, clarify_score + 0.1)
            else:
                direct_score = min(1.0, direct_score + 0.1)

        return direct_score, clarify_score

    def _analyze_query_complexity(self, query: str) -> float:
        """分析查询复杂度"""
        complexity_indicators = [
            len(query.split()),  # 词数
            query.count("?"),    # 问号数量
            len([w for w in query.split() if len(w) > 6]),  # 长词数量
            1 if any(word in query.lower() for word in ["怎么", "如何", "为什么", "how", "why"]) else 0
        ]

        # 归一化到0-1
        complexity_score = sum(complexity_indicators) / 10.0
        return min(1.0, complexity_score)

    def _analyze_answer_quality(self, sample: Dict[str, Any]) -> float:
        """分析回答质量"""
        quality_score = 0.5  # 基础分数

        # 检查turns完整性
        turns = sample.get("turns", [])
        if len(turns) >= 2:
            quality_score += 0.2

        # 检查reasoning完整性
        reasoning = sample.get("reasoning", {})
        if "actions" in reasoning and len(reasoning["actions"]) >= 2:
            quality_score += 0.2

        # 检查labels完整性
        labels = sample.get("labels", {})
        if "ask_required" in labels:
            quality_score += 0.1

        return min(1.0, quality_score)

    def validate_preference_quality(self, sample: Dict[str, Any]) -> Dict[str, float]:
        """
        验证偏好质量指标

        Returns:
            质量分数字典
        """
        preference = sample.get("preference", {})

        if not preference:
            return {"preference_completeness": 0.0, "score_validity": 0.0, "label_consistency": 0.0}

        # 检查completeness
        required_keys = ["direct_answer", "clarify_then_answer", "label"]
        completeness_score = sum(1 for key in required_keys if key in preference) / len(required_keys)

        # 检查分数有效性
        direct_score = preference.get("direct_answer", {}).get("score", 0)
        clarify_score = preference.get("clarify_then_answer", {}).get("score", 0)
        score_validity = 1.0 if (0 <= direct_score <= 1 and 0 <= clarify_score <= 1) else 0.0

        # 检查标签一致性
        label = preference.get("label", "")
        expected_label = "clarify" if clarify_score > direct_score else "direct"
        label_consistency = 1.0 if label == expected_label else 0.0

        return {
            "preference_completeness": completeness_score,
            "score_validity": score_validity,
            "label_consistency": label_consistency,
            "overall_quality": (completeness_score + score_validity + label_consistency) / 3
        }
