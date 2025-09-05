#!/usr/bin/env python3
"""
RSD PreAct-lite Generator - Reasoning Step Demonstration with PreAction Prediction

Generates RSD samples with next observation prediction and action forecasting.
Implements compact reasoning without natural language thinking traces.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ..streaming_client import LLMClient
from ..schema_validator import SchemaValidator

@dataclass
class RSDConfig:
    """RSD PreAct-lite generation configuration"""
    next_actions = ["ASK", "STOP_ASK", "FINALIZE"]
    observation_formats = ["boolean", "categorical", "numerical", "text"]
    max_reasoning_steps: int = 5

class RSDGenerator:
    """RSD PreAct-lite样本生成器"""

    def __init__(self, client: LLMClient, validator: SchemaValidator):
        self.client = client
        self.validator = validator
        self.config = RSDConfig()

        # Load prompt template
        template_path = Path(__file__).parent / ".." / "prompt_templates" / "rsd_preaction.txt"
        with open(template_path, 'r', encoding='utf-8') as f:
            self.prompt_template = f.read()

    def generate_sample(self, user_query: str) -> Optional[Dict[str, Any]]:
        """
        生成单个RSD PreAct-lite样本

        Args:
            user_query: 用户查询

        Returns:
            符合Schema v1.2的样本，或None（如果生成失败）
        """
        # 构建prompt
        prompt = self._build_prompt(user_query)

        # 调用LLM生成
        messages = [
            {"role": "system", "content": "You must output only valid JSON. No explanations, no markdown, no polite phrases. No <think> tags."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.client.stream_chat(
                provider="deepseek_reasoner",  # RSD使用reasoner
                model="deepseek_reasoner",
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
                sample = self._post_process_sample(sample)
                is_valid, errors = self.validator.validate_sample(sample)

                if is_valid:
                    return sample
                else:
                    print(f"Sample validation failed: {errors}")
                    return None

        except Exception as e:
            print(f"Generation failed: {e}")
            return None

    def _build_prompt(self, user_query: str) -> str:
        """构建生成prompt"""
        return self.prompt_template.format(user_query=user_query)

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
                    {"role": "model_target", "text": "<ASK>Please clarify</ASK>"}
                ]

            if "labels" not in sample:
                sample["labels"] = {"ask_required": True}

            if "reasoning" not in sample:
                sample["reasoning"] = {"actions": ["AWARE_GAP", "ASK", "STOP_ASK"]}

            if "source" not in sample:
                sample["source"] = "synthetic-deepseek"

            return sample

        except json.JSONDecodeError as e:
            print(f"JSON parsing failed: {e}")
            print(f"Response text: {text[:200]}...")
            return None
        except Exception as e:
            print(f"Response parsing failed: {e}")
            return None

    def _post_process_sample(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """后处理样本，增强RSD字段"""
        # 确保prediction字段
        if "prediction" not in sample:
            sample["prediction"] = {
                "next_observation": self._generate_structured_observation(sample),
                "confidence": 0.8
            }

        # 确保reasoning包含next_action预测
        reasoning = sample.get("reasoning", {})
        actions = reasoning.get("actions", [])

        if len(actions) >= 3:  # 已经有基础actions
            # 添加预测的下一个action
            next_action = self._predict_next_action(actions)
            if next_action not in actions:  # 避免重复
                reasoning["actions"] = actions + [next_action]

        # 确保紧凑推理
        if "compact_rationale" not in reasoning:
            reasoning["compact_rationale"] = {
                "connectors": ["if", "then"],
                "steps": min(len(actions), self.config.max_reasoning_steps)
            }

        sample["reasoning"] = reasoning

        return sample

    def _generate_structured_observation(self, sample: Dict[str, Any]) -> str:
        """生成结构化的下一个观察"""
        user_query = ""
        for turn in sample.get("turns", []):
            if turn.get("role") == "user":
                user_query = turn.get("text", "")
                break

        # 基于查询类型生成结构化观察
        if any(word in user_query.lower() for word in ["多少", "几", "how many", "what number"]):
            return "numerical_value: {value}"
        elif any(word in user_query.lower() for word in ["是否", "是不是", "is", "are"]):
            return "boolean_answer: {true|false}"
        elif any(word in user_query.lower() for word in ["哪个", "哪种", "which", "what type"]):
            return "categorical_choice: {option_a|option_b|option_c}"
        else:
            return "text_response: {clarification_text}"

    def _predict_next_action(self, current_actions: List[str]) -> str:
        """预测下一个action"""
        # 基于当前actions序列预测下一个
        if "FINALIZE" in current_actions:
            return "STOP_ASK"  # 如果已经finalize，下一个可能是停止询问
        elif "STOP_ASK" in current_actions:
            return "FINALIZE"  # 如果停止询问，下一个可能是最终回答
        elif "ASK" in current_actions:
            return "STOP_ASK"  # 如果询问过，下一个可能是停止
        else:
            return "ASK"  # 默认开始询问

    def validate_rsd_quality(self, sample: Dict[str, Any]) -> Dict[str, float]:
        """
        验证RSD质量指标

        Returns:
            质量分数字典
        """
        # 检查prediction结构
        prediction = sample.get("prediction", {})
        pred_score = 1.0 if "next_observation" in prediction else 0.0

        # 检查reasoning紧凑性
        reasoning = sample.get("reasoning", {})
        compact = reasoning.get("compact_rationale", {})
        connectors = compact.get("connectors", [])
        steps = compact.get("steps", 0)

        # Compactness score: 奖励使用连接词和合理步骤数
        compactness_score = min((len(connectors) + steps) / 8.0, 1.0)

        # 检查是否包含思维链泄漏
        turns_text = " ".join([turn.get("text", "") for turn in sample.get("turns", [])])
        cot_leak_score = 0.0 if "<think>" in turns_text else 1.0

        # Action prediction准确性（简化评估）
        actions = reasoning.get("actions", [])
        action_score = 1.0 if len(actions) >= 3 else 0.5

        return {
            "prediction_structure": pred_score,
            "compactness_score": compactness_score,
            "cot_leak_free": cot_leak_score,
            "action_prediction": action_score,
            "overall_quality": (pred_score + compactness_score + cot_leak_score + action_score) / 4
        }
