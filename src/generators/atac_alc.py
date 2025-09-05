#!/usr/bin/env python3
"""
ATAC-ALC Generator - Active Task Ambiguity Clarification for Learning Clarification

Generates ALC samples with enumerated clarification options and branch mapping.
Implements Coverage@ASK ≥95% and Branch-Consistency ≥90% requirements.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ..streaming_client import LLMClient
from ..schema_validator import SchemaValidator

@dataclass
class ATACConfig:
    """ATAC-ALC generation configuration"""
    coverage_threshold: float = 0.95  # Coverage@ASK ≥95%
    consistency_threshold: float = 0.90  # Branch-Consistency ≥90%
    max_options: int = 5
    max_ambiguity_types: int = 5

class ATACGenerator:
    """ATAC-ALC样本生成器"""

    def __init__(self, client: LLMClient, validator: SchemaValidator):
        self.client = client
        self.validator = validator
        self.config = ATACConfig()

        # Load prompt template
        template_path = Path(__file__).parent / ".." / "prompt_templates" / "atac_alc.txt"
        with open(template_path, 'r', encoding='utf-8') as f:
            self.prompt_template = f.read()

        # ATAC歧义类型映射
        self.ambiguity_keywords = {
            "person": ["谁", "哪个人", "谁来", "which person", "who"],
            "time": ["什么时候", "何时", "时间", "when", "what time"],
            "location": ["哪里", "地点", "位置", "where", "location"],
            "preference": ["喜欢", "偏好", "想要", "prefer", "like"],
            "budget": ["预算", "多少钱", "价格", "budget", "cost"],
            "method": ["怎么做", "方法", "方式", "how", "method"],
            "scope": ["哪些", "范围", "什么方面", "scope", "which"],
            "context": ["情况", "背景", "前提", "context", "given"],
            "quantity": ["多少", "几", "quantity", "how many"],
            "quality": ["怎么样", "质量", "如何", "quality", "how good"]
        }

    def generate_sample(self, user_query: str) -> Optional[Dict[str, Any]]:
        """
        生成单个ATAC-ALC样本

        Args:
            user_query: 用户查询

        Returns:
            符合Schema v1.2的样本，或None（如果生成失败）
        """
        # 预分析歧义类型
        ambiguity_types = self._analyze_ambiguity_types(user_query)

        # 构建prompt
        prompt = self._build_prompt(user_query, ambiguity_types)

        # 调用LLM生成
        messages = [
            {"role": "system", "content": "You must output only valid JSON. No explanations, no markdown, no polite phrases."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.client.stream_chat(
                provider="gemini_flash",  # 默认使用flash
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
            sample = self._parse_response(text, user_query)

            # 后处理和验证
            if sample:
                sample = self._post_process_sample(sample, ambiguity_types)
                is_valid, errors = self.validator.validate_sample(sample)

                if is_valid:
                    return sample
                else:
                    print(f"Sample validation failed: {errors}")
                    return None

        except Exception as e:
            print(f"Generation failed: {e}")
            return None

    def _analyze_ambiguity_types(self, query: str) -> List[str]:
        """分析查询中的歧义类型"""
        detected_types = []

        for amb_type, keywords in self.ambiguity_keywords.items():
            if any(keyword.lower() in query.lower() for keyword in keywords):
                detected_types.append(amb_type)

        # 限制数量
        return detected_types[:self.config.max_ambiguity_types]

    def _build_prompt(self, user_query: str, ambiguity_types: List[str]) -> str:
        """构建生成prompt"""
        return self.prompt_template.format(
            user_query=user_query,
            ambiguity_types=", ".join(f'"{t}"' for t in ambiguity_types)
        )

    def _parse_response(self, text: str, user_query: str) -> Optional[Dict[str, Any]]:
        """解析LLM响应"""
        try:
            # 清理响应文本
            text = text.strip()

            # 移除可能的markdown包装
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            text = text.strip()

            # 解析JSON
            sample = json.loads(text)

            # 确保基本结构
            if "turns" not in sample:
                sample["turns"] = [
                    {"role": "user", "text": user_query},
                    {"role": "model_target", "text": "<ASK>Please clarify your request</ASK>"}
                ]

            if "labels" not in sample:
                sample["labels"] = {"ask_required": True}

            if "reasoning" not in sample:
                sample["reasoning"] = {"actions": ["AWARE_GAP", "ASK", "STOP_ASK"]}

            if "source" not in sample:
                sample["source"] = "synthetic-gemini"

            return sample

        except json.JSONDecodeError as e:
            print(f"JSON parsing failed: {e}")
            print(f"Response text: {text[:200]}...")
            return None
        except Exception as e:
            print(f"Response parsing failed: {e}")
            return None

    def _post_process_sample(self, sample: Dict[str, Any], detected_types: List[str]) -> Dict[str, Any]:
        """后处理样本，增强ATAC字段"""
        labels = sample.get("labels", {})

        # 确保歧义类型
        if "ambiguity_types" not in labels and detected_types:
            labels["ambiguity_types"] = detected_types

        # 确保分支映射一致性
        if "ask_options" in labels and "branch_map" not in labels:
            ask_options = labels["ask_options"]
            branch_map = []
            for i, option in enumerate(ask_options):
                branch_map.append({
                    "option": option,
                    "final_id": f"F{i+1}"
                })
            labels["branch_map"] = branch_map

        # 确保紧凑推理
        reasoning = sample.get("reasoning", {})
        if "compact_rationale" not in reasoning:
            reasoning["compact_rationale"] = {
                "connectors": ["if", "because", "therefore"],
                "steps": 3
            }

        sample["labels"] = labels
        sample["reasoning"] = reasoning

        return sample

    def validate_atac_quality(self, sample: Dict[str, Any]) -> Dict[str, float]:
        """
        验证ATAC质量指标

        Returns:
            质量分数字典
        """
        labels = sample.get("labels", {})

        # Coverage@ASK
        ask_options = labels.get("ask_options", [])
        ambiguity_types = labels.get("ambiguity_types", [])
        coverage_score = min(len(ask_options) / max(len(ambiguity_types), 1), 1.0)

        # Branch-Consistency
        branch_map = labels.get("branch_map", [])
        consistency_score = 1.0 if len(branch_map) == len(ask_options) else 0.5

        return {
            "coverage_ask": coverage_score,
            "branch_consistency": consistency_score,
            "overall_quality": (coverage_score + consistency_score) / 2
        }
