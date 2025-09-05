#!/usr/bin/env python3
"""
Schema校验器 v1.2 - 支持ATAC, ToC, FT-Pref增强
严格校验Schema v1.2，包含新增字段验证和质量控制
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

class SchemaValidator:
    """Schema v1.2 校验器"""

    def __init__(self):
        self.schema_version = "1.2"
        # 礼貌语过滤规则
        self.politeness_patterns = [
            r'谢谢', r'请', r'对不起', r'抱歉', r'您好', r'再见',
            r'thank you', r'please', r'sorry', r'excuse me', r'hello', r'goodbye'
        ]

        # ATAC歧义类型枚举
        self.valid_ambiguity_types = {
            "person", "time", "location", "preference", "budget",
            "method", "scope", "context", "quantity", "quality"
        }

        # 推理连接词枚举
        self.valid_connectors = {
            "if", "then", "because", "therefore",
            "compare", "contrast", "and", "or", "but"
        }

    def validate_sample(self, sample: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        校验单个样本是否符合Schema v1.2

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

        # 新增v1.2字段校验
        if "clarify_tree" in sample:
            tree_valid, tree_errors = self._validate_clarify_tree(sample["clarify_tree"])
            errors.extend(tree_errors)

        if "evidence_ids" in sample:
            evidence_valid, evidence_errors = self._validate_evidence_ids(sample["evidence_ids"])
            errors.extend(evidence_errors)

        if "preference" in sample:
            pref_valid, pref_errors = self._validate_preference(sample["preference"])
            errors.extend(pref_errors)

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

        # 检查是否包含思维链
        if re.search(r'<think>|</think>', text):
            errors.append("model_target不能包含<think>思维链")

        # 检查礼貌语
        cleaned_text = self.strip_politeness(text)
        if cleaned_text != text:
            errors.append("model_target不能包含礼貌语")

        return len(errors) == 0, errors

    def _validate_labels(self, labels: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """校验labels字段"""
        errors = []

        # 检查必需字段
        if "ask_required" not in labels:
            errors.append("labels缺少ask_required字段")

        # 校验ambiguity_types (ATAC)
        if "ambiguity_types" in labels:
            amb_types = labels["ambiguity_types"]
            if not isinstance(amb_types, list):
                errors.append("ambiguity_types必须是数组")
            else:
                if len(amb_types) > 5:
                    errors.append("ambiguity_types不能超过5个")
                for amb_type in amb_types:
                    if amb_type not in self.valid_ambiguity_types:
                        errors.append(f"ambiguity_types包含无效值: {amb_type}")

        # 校验ask_options (ATAC)
        if "ask_options" in labels:
            ask_opts = labels["ask_options"]
            if not isinstance(ask_opts, list):
                errors.append("ask_options必须是数组")
            else:
                if len(ask_opts) > 5:
                    errors.append("ask_options不能超过5个")
                for opt in ask_opts:
                    if not isinstance(opt, str) or len(opt) > 100:
                        errors.append("ask_options中的选项必须是1-100字符的字符串")

        # 校验branch_map (ATAC)
        if "branch_map" in labels:
            branch_map = labels["branch_map"]
            if not isinstance(branch_map, list):
                errors.append("branch_map必须是数组")
            else:
                if len(branch_map) > 10:
                    errors.append("branch_map不能超过10个")
                for item in branch_map:
                    if not isinstance(item, dict):
                        errors.append("branch_map中的项必须是对象")
                    elif "option" not in item or "final_id" not in item:
                        errors.append("branch_map中的项必须包含option和final_id字段")

        return len(errors) == 0, errors

    def _validate_reasoning(self, reasoning: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """校验reasoning字段"""
        errors = []

        # 检查必需字段
        if "actions" not in reasoning:
            errors.append("reasoning缺少actions字段")

        # 校验actions
        if "actions" in reasoning:
            actions = reasoning["actions"]
            if not isinstance(actions, list):
                errors.append("reasoning.actions必须是数组")

        # 校验compact_rationale (新增)
        if "compact_rationale" in reasoning:
            rationale = reasoning["compact_rationale"]
            if not isinstance(rationale, dict):
                errors.append("compact_rationale必须是对象")
            else:
                if "connectors" in rationale:
                    connectors = rationale["connectors"]
                    if not isinstance(connectors, list):
                        errors.append("compact_rationale.connectors必须是数组")
                    else:
                        for conn in connectors:
                            if conn not in self.valid_connectors:
                                errors.append(f"无效的连接词: {conn}")

                if "steps" in rationale:
                    steps = rationale["steps"]
                    if not isinstance(steps, int) or steps < 1 or steps > 5:
                        errors.append("compact_rationale.steps必须是1-5的整数")

        return len(errors) == 0, errors

    def _validate_source(self, source: str) -> Tuple[bool, List[str]]:
        """校验source字段"""
        errors = []

        valid_sources = [
            "synthetic-gemini", "synthetic-deepseek", "human", "curated",
            "hotpotqa", "ambigqa", "asqa", "gsm8k"
        ]

        if source not in valid_sources:
            errors.append(f"source必须是以下值之一: {valid_sources}")

        return len(errors) == 0, errors

    def _validate_clarify_tree(self, clarify_tree: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """校验clarify_tree字段 (ToC)"""
        errors = []

        if not isinstance(clarify_tree, dict):
            return False, ["clarify_tree必须是对象"]

        # 校验depth
        if "depth" in clarify_tree:
            depth = clarify_tree["depth"]
            if not isinstance(depth, int) or depth < 0 or depth > 3:
                errors.append("clarify_tree.depth必须是0-3的整数")

        # 校验nodes
        if "nodes" in clarify_tree:
            nodes = clarify_tree["nodes"]
            if not isinstance(nodes, list):
                errors.append("clarify_tree.nodes必须是数组")
            else:
                for node in nodes:
                    if not isinstance(node, dict):
                        errors.append("clarify_tree.nodes中的项必须是对象")
                    elif "id" not in node:
                        errors.append("clarify_tree.nodes中的项必须包含id字段")

        return len(errors) == 0, errors

    def _validate_evidence_ids(self, evidence_ids: List[str]) -> Tuple[bool, List[str]]:
        """校验evidence_ids字段 (ToC)"""
        errors = []

        if not isinstance(evidence_ids, list):
            return False, ["evidence_ids必须是数组"]

        # 校验格式
        pattern = r'^[a-zA-Z0-9_:#-]+$'
        for evidence_id in evidence_ids:
            if not isinstance(evidence_id, str):
                errors.append("evidence_ids中的项必须是字符串")
            elif not re.match(pattern, evidence_id):
                errors.append(f"evidence_ids格式不正确: {evidence_id}")

        return len(errors) == 0, errors

    def _validate_preference(self, preference: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """校验preference字段 (FT-Pref)"""
        errors = []

        if not isinstance(preference, dict):
            return False, ["preference必须是对象"]

        # 校验direct_answer
        if "direct_answer" in preference:
            direct = preference["direct_answer"]
            if isinstance(direct, dict) and "score" in direct:
                score = direct["score"]
                if not isinstance(score, (int, float)) or score < 0.0 or score > 1.0:
                    errors.append("direct_answer.score必须是0.0-1.0的数值")

        # 校验clarify_then_answer
        if "clarify_then_answer" in preference:
            clarify = preference["clarify_then_answer"]
            if isinstance(clarify, dict) and "score" in clarify:
                score = clarify["score"]
                if not isinstance(score, (int, float)) or score < 0.0 or score > 1.0:
                    errors.append("clarify_then_answer.score必须是0.0-1.0的数值")

        # 校验label
        if "label" in preference:
            label = preference["label"]
            if label not in ["direct", "clarify"]:
                errors.append("preference.label必须是'direct'或'clarify'")

        return len(errors) == 0, errors

    def strip_politeness(self, text: str) -> str:
        """去除礼貌语"""
        for pattern in self.politeness_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        return text.strip()

    def extract_largest_json(self, text: str) -> Optional[str]:
        """从文本中提取最大的JSON对象"""
        try:
            # 寻找JSON对象的开始和结束
            start = text.find('{')
            end = text.rfind('}')

            if start == -1 or end == -1 or start >= end:
                return None

            candidate = text[start:end + 1]
            json.loads(candidate)  # 验证是否为有效JSON
            return candidate
        except json.JSONDecodeError:
            return None

    def minimal_completion(self, text: str, schema: Dict[str, Any]) -> str:
        """最小化补全不完整的JSON"""
        try:
            # 简单的补全策略
            if not text.strip().endswith('}'):
                text += '}'
            return text
        except Exception:
            return text
