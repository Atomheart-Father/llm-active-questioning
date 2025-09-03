"""Data Loader for Schema v1.1

负责加载和校验v1.1格式的数据文件。
对不符合schema的样本进行显式报错。
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterator
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Schema v1.1 常量定义
VALID_DOMAINS = {"planning", "qa", "reasoning", "creative"}
VALID_SOURCES = {"synthetic-gemini", "curated", "r1-distill", "human"}
VALID_AMBIGUITY_TYPES = {
    "location", "budget", "diet", "time", "quantity", "quality",
    "preference", "constraint", "context", "scope", "method"
}
VALID_ACTION_TYPES = {"AWARE_GAP", "ASK", "STOP_ASK", "DERIVE", "VERIFY", "FINALIZE"}

# CoT泄漏检测常量
COT_INDICATORS = [
    # 中文推理关键词
    "首先", "其次", "然后", "最后", "接下来",
    "因为", "所以", "因此", "由于", "根据",
    "分析", "考虑", "思考", "推理", "判断",
    "步骤", "过程", "阶段", "环节", "方法",
    "综上所述", "总的来说", "也就是说", "换句话说",
    "让我想想", "我需要", "应该", "可以",

    # 英文推理关键词
    "first", "second", "then", "finally", "next",
    "because", "so", "therefore", "since", "according to",
    "analyze", "consider", "think", "reason", "judge",
    "step", "process", "stage", "phase", "method",
    "in conclusion", "overall", "in other words",
    "let me think", "I need", "should", "can",

    # 特定CoT模式
    "Let's think", "Chain-of-Thought", "CoT",
    "Step by step", "Break it down",
    "推理过程", "思考过程", "分析过程", "决策过程",
    "让我来分析", "我来思考", "需要考虑",
]

ALLOWED_IN_THINK = [
    "首先", "其次", "然后", "最后", "因为", "所以", "因此",
    "分析", "考虑", "思考", "推理", "步骤", "过程",
    "Let's think", "let me think", "I need to think",
]

@dataclass
class ValidationError:
    """数据校验错误"""
    sample_id: str
    field: str
    message: str
    severity: str = "error"  # error, warning

@dataclass
class Sample:
    """Schema v1.1 数据样本"""
    id: str
    domain: str
    source: str
    turns: List[Dict[str, str]]
    labels: Dict[str, Any]
    reasoning: Dict[str, Any]

class DataLoader:
    """Schema v1.1 数据加载器"""

    def __init__(self, strict_mode: bool = True):
        """
        Args:
            strict_mode: 严格模式，遇到错误立即抛出
        """
        self.strict_mode = strict_mode
        self.errors: List[ValidationError] = []

    def load_jsonl(self, file_path: str) -> Iterator[Sample]:
        """加载JSONL格式文件

        Args:
            file_path: 文件路径

        Yields:
            Sample: 校验通过的样本

        Raises:
            ValueError: 严格模式下遇到校验错误
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    sample = self._parse_sample(data)
                    errors = self._validate_sample(sample)

                    if errors:
                        self.errors.extend(errors)
                        if self.strict_mode:
                            error_msg = f"Validation errors in {file_path}:{line_num}\n"
                            for error in errors:
                                error_msg += f"  {error.severity.upper()}: {error.field} - {error.message}\n"
                            raise ValueError(error_msg)

                    if not any(e.severity == "error" for e in errors):
                        yield sample

                except json.JSONDecodeError as e:
                    error = ValidationError(
                        sample_id=f"line_{line_num}",
                        field="json",
                        message=f"Invalid JSON: {e}",
                        severity="error"
                    )
                    self.errors.append(error)
                    if self.strict_mode:
                        raise ValueError(f"JSON parse error in {file_path}:{line_num}: {e}")

    def _parse_sample(self, data: Dict[str, Any]) -> Sample:
        """解析JSON数据为Sample对象"""
        return Sample(
            id=data.get("id", ""),
            domain=data.get("domain", ""),
            source=data.get("source", ""),
            turns=data.get("turns", []),
            labels=data.get("labels", {}),
            reasoning=data.get("reasoning", {})
        )

    def _validate_sample(self, sample: Sample) -> List[ValidationError]:
        """校验样本数据"""
        errors = []

        # 基础字段校验
        if not sample.id:
            errors.append(ValidationError(
                sample.id, "id", "ID不能为空", "error"
            ))

        if sample.domain not in VALID_DOMAINS:
            errors.append(ValidationError(
                sample.id, "domain", f"无效的domain: {sample.domain}，应为: {VALID_DOMAINS}", "error"
            ))

        if sample.source not in VALID_SOURCES:
            errors.append(ValidationError(
                sample.id, "source", f"无效的source: {sample.source}，应为: {VALID_SOURCES}", "error"
            ))

        # turns校验
        if not sample.turns:
            errors.append(ValidationError(
                sample.id, "turns", "turns不能为空", "error"
            ))

        user_count = sum(1 for turn in sample.turns if turn.get("role") == "user")
        model_count = sum(1 for turn in sample.turns if turn.get("role") == "model_target")

        if user_count == 0:
            errors.append(ValidationError(
                sample.id, "turns", "至少需要一个user轮次", "error"
            ))

        if model_count == 0:
            errors.append(ValidationError(
                sample.id, "turns", "至少需要一个model_target轮次", "error"
            ))

        # 检查model_target中是否包含思维链
        for turn in sample.turns:
            if turn.get("role") == "model_target":
                text = turn.get("text", "")
                if self._contains_cot_leakage(text):
                    errors.append(ValidationError(
                        sample.id, "turns.model_target",
                        "model_target中包含思维链文本，违反schema约束", "error"
                    ))

        # labels校验
        if "ask_required" not in sample.labels:
            errors.append(ValidationError(
                sample.id, "labels.ask_required", "缺少必需字段ask_required", "error"
            ))

        if "ambiguity_types" in sample.labels:
            invalid_types = set(sample.labels["ambiguity_types"]) - VALID_AMBIGUITY_TYPES
            if invalid_types:
                errors.append(ValidationError(
                    sample.id, "labels.ambiguity_types",
                    f"无效的ambiguity_types: {invalid_types}", "warning"
                ))

        if "good_question_set" in sample.labels:
            question_count = len(sample.labels["good_question_set"])
            if question_count > 3:
                errors.append(ValidationError(
                    sample.id, "labels.good_question_set",
                    f"good_question_set数量({question_count})超过上限3", "warning"
                ))

        # reasoning校验
        if "actions" not in sample.reasoning:
            errors.append(ValidationError(
                sample.id, "reasoning.actions", "缺少必需字段actions", "error"
            ))

        if "actions" in sample.reasoning:
            for i, action in enumerate(sample.reasoning["actions"]):
                if not isinstance(action, dict):
                    errors.append(ValidationError(
                        sample.id, f"reasoning.actions[{i}]",
                        "action必须是字典格式", "error"
                    ))
                    continue

                if "t" not in action:
                    errors.append(ValidationError(
                        sample.id, f"reasoning.actions[{i}].t",
                        "action缺少必需字段t", "error"
                    ))
                    continue

                if action["t"] not in VALID_ACTION_TYPES:
                    errors.append(ValidationError(
                        sample.id, f"reasoning.actions[{i}].t",
                        f"无效的action类型: {action['t']}，应为: {VALID_ACTION_TYPES}", "error"
                    ))

        return errors

    def _contains_cot_leakage(self, text: str) -> bool:
        """检查文本是否包含思维链泄漏"""
        if not text:
            return False

        text_lower = text.lower()

        # 提取think内容（如果有）
        think_content = ""
        think_start = -1
        think_end = -1

        if "<think>" in text and "</think>" in text:
            think_match = re.search(r'<think>(.*?)</think>', text, re.DOTALL | re.IGNORECASE)
            if think_match:
                think_content = think_match.group(1).lower()
                think_start = text.lower().find("<think>")
                think_end = text.lower().find("</think>") + len("</think>")

        # 检查每个CoT指标
        for indicator in COT_INDICATORS:
            indicator_lower = indicator.lower()

            # 如果指标出现在文本中
            if indicator_lower in text_lower:
                # 如果有think标签，检查泄漏是否在标签外
                if think_start >= 0 and think_end > 0:
                    # 在标签前的内容
                    before_think = text[:think_start]
                    # 在标签后的内容
                    after_think = text[think_end:]

                    # 如果泄漏指标在标签外出现，则为违规
                    if (indicator_lower in before_think.lower() or
                        indicator_lower in after_think.lower()):
                        return True

                    # 如果在think内容中，但不是允许的关键词，也算泄漏
                    if (indicator_lower in think_content and
                        indicator not in ALLOWED_IN_THINK):
                        return True
                else:
                    # 没有think标签，任何CoT关键词都算泄漏
                    return True

        return False

    def get_validation_report(self) -> Dict[str, Any]:
        """获取校验报告"""
        error_count = sum(1 for e in self.errors if e.severity == "error")
        warning_count = sum(1 for e in self.errors if e.severity == "warning")

        return {
            "total_errors": len(self.errors),
            "error_count": error_count,
            "warning_count": warning_count,
            "errors": [
                {
                    "sample_id": e.sample_id,
                    "field": e.field,
                    "message": e.message,
                    "severity": e.severity
                }
                for e in self.errors
            ]
        }


def load_dataset(file_path: str, strict_mode: bool = True) -> List[Sample]:
    """便捷函数：加载整个数据集到内存

    Args:
        file_path: 数据文件路径
        strict_mode: 严格模式

    Returns:
        List[Sample]: 样本列表
    """
    loader = DataLoader(strict_mode=strict_mode)
    samples = list(loader.load_jsonl(file_path))

    if loader.errors:
        logger.warning(f"Found {len(loader.errors)} validation issues")
        for error in loader.errors:
            logger.warning(f"[{error.severity.upper()}] {error.sample_id}.{error.field}: {error.message}")

    return samples


if __name__ == "__main__":
    # 示例用法
    import sys
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        samples = load_dataset(file_path, strict_mode=False)
        print(f"Loaded {len(samples)} samples")

        loader = DataLoader(strict_mode=False)
        list(loader.load_jsonl(file_path))  # 触发校验
        report = loader.get_validation_report()
        print(f"Validation report: {report['error_count']} errors, {report['warning_count']} warnings")
