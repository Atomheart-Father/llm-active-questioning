#!/usr/bin/env python3
"""
Schema校验器 - 修复解析失败问题
严格校验v1.1 Schema，处理空turns等结构问题
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

class SchemaValidator:
    """Schema v1.1 校验器"""

    def __init__(self):
        self.schema_version = "1.1"

    def validate_sample(self, sample: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        校验单个样本是否符合Schema v1.1

        Args:
            sample: 样本数据

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # 检查必需字段
        required_fields = ["turns", "labels", "reasoning", "source"]
        for field in required_fields:
            if field not in sample:
                errors.append(f"缺少必需字段: {field}")

        if errors:
            return False, errors

        # 校验turns字段
        turns_valid, turns_errors = self._validate_turns(sample["turns"])
        errors.extend(turns_errors)

        # 校验labels字段
        labels_valid, labels_errors = self._validate_labels(sample["labels"])
        errors.extend(labels_errors)

        # 校验reasoning字段
        reasoning_valid, reasoning_errors = self._validate_reasoning(sample["reasoning"])
        errors.extend(reasoning_errors)

        # 校验source字段
        source_valid, source_errors = self._validate_source(sample["source"])
        errors.extend(source_errors)

        return len(errors) == 0, errors

    def _validate_turns(self, turns: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """校验turns字段"""
        errors = []

        if not isinstance(turns, list):
            return False, ["turns字段必须是列表"]

        if len(turns) == 0:
            return False, ["turns字段不能为空"]

        if len(turns) < 2:
            return False, ["turns至少需要包含user和assistant两条消息"]

        # 校验第一个turn
        first_turn = turns[0]
        if first_turn.get("role") != "user":
            errors.append("turns[0].role必须是'user'")

        if "text" not in first_turn:
            errors.append("turns[0]缺少text字段")

        # 校验第二个turn（model_target）
        if len(turns) > 1:
            second_turn = turns[1]
            if second_turn.get("role") != "model_target":
                errors.append("turns[1].role必须是'model_target'")

            if "text" not in second_turn:
                errors.append("turns[1]缺少text字段")
            else:
                # 校验model_target内容
                text = second_turn["text"]
                control_valid, control_errors = self._validate_control_symbols(text)
                if not control_valid:
                    errors.extend(control_errors)

        # 校验其他turn的role
        valid_roles = {"user", "model_target", "assistant"}
        for i, turn in enumerate(turns):
            if "role" not in turn:
                errors.append(f"turns[{i}]缺少role字段")
            elif turn["role"] not in valid_roles:
                errors.append(f"turns[{i}].role必须是{valid_roles}之一")

            if "text" not in turn:
                errors.append(f"turns[{i}]缺少text字段")

        return len(errors) == 0, errors

    def _validate_control_symbols(self, text: str) -> Tuple[bool, List[str]]:
        """校验控制符格式"""
        errors = []

        # 检查是否只包含一个控制符
        ask_pattern = r'<ASK>.*?</ASK>'
        final_pattern = r'<FINAL>.*?</FINAL>'

        ask_matches = re.findall(ask_pattern, text, re.DOTALL)
        final_matches = re.findall(final_pattern, text, re.DOTALL)

        total_control_symbols = len(ask_matches) + len(final_matches)

        if total_control_symbols == 0:
            errors.append("model_target必须包含<ASK>或<FINAL>控制符")
        elif total_control_symbols > 1:
            errors.append(f"model_target只能包含一个控制符，当前有{total_control_symbols}个")

        # 检查格式是否正确
        if ask_matches:
            for match in ask_matches:
                if not re.match(r'^\s*<ASK>.+?</ASK>\s*$', match):
                    errors.append("ASK控制符格式不正确")

        if final_matches:
            for match in final_matches:
                if not re.match(r'^\s*<FINAL>.+?</FINAL>\s*$', match):
                    errors.append("FINAL控制符格式不正确")

        # 检查是否包含礼貌语或思维链
        if re.search(r'<think>|</think>', text):
            errors.append("model_target不能包含<think>思维链")

        if re.search(r'(谢谢|请|对不起|抱歉|您好|再见)', text):
            errors.append("model_target不能包含礼貌语")

        return len(errors) == 0, errors

    def _validate_labels(self, labels: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """校验labels字段"""
        errors = []

        # 检查必需字段
        required_label_fields = ["ask_required", "ambiguity_types", "good_question_set", "minimal_clarifications"]
        for field in required_label_fields:
            if field not in labels:
                errors.append(f"labels缺少必需字段: {field}")

        if errors:
            return False, errors

        # 校验ask_required
        if not isinstance(labels["ask_required"], bool):
            errors.append("ask_required必须是布尔值")

        # 校验ambiguity_types
        if not isinstance(labels["ambiguity_types"], list):
            errors.append("ambiguity_types必须是列表")
        else:
            for item in labels["ambiguity_types"]:
                if not isinstance(item, str):
                    errors.append("ambiguity_types的元素必须是字符串")

        # 校验good_question_set
        if not isinstance(labels["good_question_set"], list):
            errors.append("good_question_set必须是列表")
        else:
            if len(labels["good_question_set"]) > 3:
                errors.append("good_question_set最多只能有3个问题")

        # 校验minimal_clarifications
        if labels["minimal_clarifications"] not in [1, 2]:
            errors.append("minimal_clarifications必须是1或2")

        return len(errors) == 0, errors

    def _validate_reasoning(self, reasoning: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """校验reasoning字段"""
        errors = []

        if "actions" not in reasoning:
            errors.append("reasoning缺少actions字段")
            return False, errors

        if not isinstance(reasoning["actions"], list):
            errors.append("reasoning.actions必须是列表")
            return False, errors

        required_actions = {"AWARE_GAP", "ASK", "STOP_ASK", "FINALIZE"}
        actions_set = set(reasoning["actions"])

        missing_actions = required_actions - actions_set
        if missing_actions:
            errors.append(f"reasoning.actions缺少必需动作: {missing_actions}")

        return len(errors) == 0, errors

    def _validate_source(self, source: str) -> Tuple[bool, List[str]]:
        """校验source字段"""
        valid_sources = {"synthetic-gemini", "r1-distill", "curated", "human"}

        if source not in valid_sources:
            return False, [f"source必须是{valid_sources}之一，当前是: {source}"]

        return True, []

    def extract_largest_json(self, text: str) -> Optional[str]:
        """从文本中提取最大的JSON对象"""
        import re

        # 查找所有的JSON对象
        json_pattern = r'\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)

        if not matches:
            return None

        # 返回最大的JSON对象
        return max(matches, key=len)

    def repair_sample(self, sample_text: str) -> Optional[Dict[str, Any]]:
        """
        尝试修复不完整的样本

        Args:
            sample_text: 原始响应文本

        Returns:
            修复后的样本，如果无法修复返回None
        """
        try:
            # 提取最大JSON
            largest_json = self.extract_largest_json(sample_text)
            if not largest_json:
                logger.warning("无法提取JSON对象")
                return None

            # 解析JSON
            sample = json.loads(largest_json)

            # 校验并修复
            is_valid, errors = self.validate_sample(sample)

            if is_valid:
                return sample
            else:
                logger.warning(f"样本校验失败: {errors}")
                # 尝试简单修复
                return self._simple_repair(sample, errors)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")
            return None
        except Exception as e:
            logger.warning(f"修复失败: {e}")
            return None

    def _simple_repair(self, sample: Dict[str, Any], errors: List[str]) -> Optional[Dict[str, Any]]:
        """简单修复常见问题"""
        try:
            # 修复空turns
            if "turns字段为空" in str(errors):
                if "turns" not in sample:
                    sample["turns"] = []

            # 修复缺失的role
            if sample.get("turns"):
                for i, turn in enumerate(sample["turns"]):
                    if "role" not in turn:
                        if i == 0:
                            turn["role"] = "user"
                        elif i == 1:
                            turn["role"] = "model_target"
                        else:
                            turn["role"] = "assistant"

                    if "text" not in turn:
                        turn["text"] = ""

            # 修复缺失的labels字段
            if "labels" not in sample:
                sample["labels"] = {
                    "ask_required": True,
                    "ambiguity_types": [],
                    "good_question_set": [],
                    "minimal_clarifications": 1
                }

            # 修复缺失的reasoning字段
            if "reasoning" not in sample:
                sample["reasoning"] = {
                    "actions": ["AWARE_GAP", "ASK", "STOP_ASK", "FINALIZE"]
                }

            # 修复缺失的source字段
            if "source" not in sample:
                sample["source"] = "synthetic-gemini"

            return sample

        except Exception as e:
            logger.warning(f"简单修复失败: {e}")
            return None

# 测试函数
def test_validator():
    """测试校验器"""
    validator = SchemaValidator()

    # 测试有效样本
    valid_sample = {
        "turns": [
            {"role": "user", "text": "你好"},
            {"role": "model_target", "text": "<ASK>请问你的名字是什么？</ASK>"},
            {"role": "assistant", "text": "我是AI助手"}
        ],
        "labels": {
            "ask_required": True,
            "ambiguity_types": ["unclear_reference"],
            "good_question_set": ["你想问什么？"],
            "minimal_clarifications": 1
        },
        "reasoning": {
            "actions": ["AWARE_GAP", "ASK", "STOP_ASK", "FINALIZE"]
        },
        "source": "synthetic-gemini"
    }

    is_valid, errors = validator.validate_sample(valid_sample)
    print(f"有效样本校验: {is_valid}, 错误: {errors}")

    # 测试无效样本
    invalid_sample = {
        "turns": [],
        "labels": {},
        "reasoning": {},
        "source": "invalid"
    }

    is_valid, errors = validator.validate_sample(invalid_sample)
    print(f"无效样本校验: {is_valid}, 错误: {errors}")

if __name__ == "__main__":
    test_validator()
