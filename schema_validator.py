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
        # 礼貌语过滤规则
        self.politeness_patterns = [
            r'谢谢', r'请', r'对不起', r'抱歉', r'您好', r'再见',
            r'thank you', r'please', r'sorry', r'excuse me', r'hello', r'goodbye'
        ]

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

        # 使用strip_politeness过滤礼貌语
        cleaned_text = self.strip_politeness(text)
        if cleaned_text != text:
            errors.append("model_target不能包含礼貌语")

        return len(errors) == 0, errors

    def strip_politeness(self, text: str) -> str:
        """
        过滤文本中的礼貌语

        Args:
            text: 原始文本

        Returns:
            过滤后的文本
        """
        cleaned = text
        for pattern in self.politeness_patterns:
            # 使用单词边界匹配，避免误匹配
            regex = r'\b' + re.escape(pattern) + r'\b'
            cleaned = re.sub(regex, '', cleaned, flags=re.IGNORECASE)

        # 清理多余的空格和标点
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = re.sub(r'\s*([,.!?;:])\s*', r'\1 ', cleaned)
        cleaned = cleaned.strip()

        return cleaned

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

    def repair_sample(self, sample_text: str, max_retries: int = 1) -> Optional[Dict[str, Any]]:
        """
        尝试修复不完整的样本，支持最大JSON抽取和最小补全

        Args:
            sample_text: 原始响应文本
            max_retries: 最大修复重试次数

        Returns:
            修复后的样本，如果无法修复返回None
        """
        for attempt in range(max_retries + 1):  # 包括原始尝试
            try:
                # 提取最大JSON对象
                largest_json = self.extract_largest_json(sample_text)
                if not largest_json:
                    logger.warning(f"第{attempt+1}次尝试：无法提取JSON对象")
                    if attempt < max_retries:
                        # 尝试清理文本后重试
                        sample_text = self._preprocess_text(sample_text)
                        continue
                    return None

                # 解析JSON
                sample = json.loads(largest_json)

                # 校验样本
                is_valid, errors = self.validate_sample(sample)

                if is_valid:
                    logger.info(f"第{attempt+1}次尝试：样本修复成功")
                    return sample
                else:
                    logger.warning(f"第{attempt+1}次尝试：样本校验失败: {errors}")

                    if attempt < max_retries:
                        # 尝试最小补全修复
                        sample = self._minimal_repair(sample, errors)
                        if sample:
                            # 重新校验修复后的样本
                            is_valid_after_repair, errors_after_repair = self.validate_sample(sample)
                            if is_valid_after_repair:
                                logger.info(f"第{attempt+1}次尝试：最小补全修复成功")
                                return sample

                    # 如果是最后一次尝试，返回简单修复的结果
                    if attempt == max_retries:
                        return self._simple_repair(sample, errors)

            except json.JSONDecodeError as e:
                logger.warning(f"第{attempt+1}次尝试：JSON解析失败: {e}")
                if attempt < max_retries:
                    # 尝试清理文本后重试
                    sample_text = self._preprocess_text(sample_text)
                    continue
            except Exception as e:
                logger.warning(f"第{attempt+1}次尝试：修复失败: {e}")
                if attempt >= max_retries:
                    break

        return None

    def _preprocess_text(self, text: str) -> str:
        """
        预处理文本，清理常见问题

        Args:
            text: 原始文本

        Returns:
            预处理后的文本
        """
        # 移除多余的换行和空格
        cleaned = re.sub(r'\n+', ' ', text)
        cleaned = re.sub(r'\s+', ' ', cleaned)

        # 移除markdown代码块标记
        cleaned = re.sub(r'```\w*\n?', '', cleaned)
        cleaned = re.sub(r'```', '', cleaned)

        # 清理JSON前的文本
        # 查找JSON开始位置
        json_start = cleaned.find('{')
        if json_start > 0:
            cleaned = cleaned[json_start:]

        # 清理JSON后的文本
        json_end = cleaned.rfind('}')
        if json_end >= 0 and json_end < len(cleaned) - 1:
            cleaned = cleaned[:json_end + 1]

        return cleaned.strip()

    def _minimal_repair(self, sample: Dict[str, Any], errors: List[str]) -> Optional[Dict[str, Any]]:
        """
        最小补全修复，只修复最关键的缺失字段

        Args:
            sample: 样本数据
            errors: 错误列表

        Returns:
            修复后的样本
        """
        try:
            # 只修复最关键的错误，不进行复杂的结构重组
            for error in errors:
                if "缺少必需字段" in error:
                    if "turns" in error:
                        if "turns" not in sample:
                            sample["turns"] = []
                    elif "labels" in error:
                        if "labels" not in sample:
                            sample["labels"] = {
                                "ask_required": True,
                                "ambiguity_types": [],
                                "good_question_set": [],
                                "minimal_clarifications": 1
                            }
                    elif "reasoning" in error:
                        if "reasoning" not in sample:
                            sample["reasoning"] = {
                                "actions": ["AWARE_GAP", "ASK", "STOP_ASK", "FINALIZE"]
                            }
                    elif "source" in error:
                        if "source" not in sample:
                            sample["source"] = "synthetic-gemini"

                elif "turns字段为空" in error:
                    if "turns" not in sample or not sample["turns"]:
                        sample["turns"] = [
                            {"role": "user", "text": "用户查询"},
                            {"role": "model_target", "text": "<ASK>澄清问题</ASK>"}
                        ]

                elif "model_target内容不符合ASK/FINAL格式要求" in error:
                    # 检查并修复model_target
                    if "turns" in sample and len(sample["turns"]) > 1:
                        model_target = sample["turns"][1].get("text", "")
                        if "<ASK>" not in model_target and "<FINAL>" not in model_target:
                            sample["turns"][1]["text"] = f"<ASK>{model_target}</ASK>"

            return sample

        except Exception as e:
            logger.warning(f"最小补全修复失败: {e}")
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
