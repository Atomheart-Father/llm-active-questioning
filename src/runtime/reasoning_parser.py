"""Reasoning Parser for Schema v1.1

提供统一的推理解析功能，支持Qwen和DeepSeek的<think>格式。
负责切分思考流和内容，以及历史写回时的内容剥离。
"""

import re
from typing import Tuple, Optional

# 配置开关
THOUGHT_IN_HISTORY = False  # 默认不将思考流写回历史

class ReasoningParser:
    """推理解析器"""

    def __init__(self, thought_in_history: bool = False):
        """
        Args:
            thought_in_history: 是否在历史中包含思考流（研究模式）
        """
        self.thought_in_history = thought_in_history

    def split_reasoning_and_content(self, text: str) -> Tuple[str, str]:
        """切分思考流和内容

        Args:
            text: 原始文本，格式如 "<think>思考内容</think>实际内容"

        Returns:
            Tuple[str, str]: (思考流, 内容)
        """
        # 匹配 <think>...</think> 标签
        think_pattern = r'<think>(.*?)</think>'
        match = re.search(think_pattern, text, re.DOTALL)

        if match:
            think_content = match.group(1).strip()
            # 移除think标签，保留其余内容
            content = re.sub(think_pattern, '', text, flags=re.DOTALL).strip()
            return think_content, content
        else:
            # 没有think标签，整个内容作为content
            return "", text

    def strip_reasoning_for_history(self, text: str) -> str:
        """为历史写回剥离推理内容

        Args:
            text: 原始文本

        Returns:
            str: 适合写回历史的内容
        """
        if self.thought_in_history:
            # 研究模式：保留思考流
            return text
        else:
            # 生产模式：移除思考流，只保留内容和控制符
            think_content, content = self.split_reasoning_and_content(text)
            return content

    def extract_control_symbols(self, text: str) -> dict:
        """提取控制符信息

        Args:
            text: 文本内容

        Returns:
            dict: 控制符信息
        """
        result = {
            "has_ask": False,
            "has_final": False,
            "ask_content": None,
            "final_content": None
        }

        # 提取 <ASK> 内容
        ask_match = re.search(r'<ASK>(.*?)</ASK>', text, re.DOTALL)
        if ask_match:
            result["has_ask"] = True
            result["ask_content"] = ask_match.group(1).strip()

        # 提取 <FINAL> 内容
        final_match = re.search(r'<FINAL>(.*?)</FINAL>', text, re.DOTALL)
        if final_match:
            result["has_final"] = True
            result["final_content"] = final_match.group(1).strip()

        return result

    def validate_reasoning_format(self, text: str) -> dict:
        """校验推理格式

        Args:
            text: 待校验文本

        Returns:
            dict: 校验结果
        """
        result = {
            "is_valid": True,
            "errors": [],
            "warnings": []
        }

        # 检查标签匹配
        think_open = text.count('<think>')
        think_close = text.count('</think>')

        if think_open != think_close:
            result["is_valid"] = False
            result["errors"].append(f"think标签不匹配: {think_open}个开始, {think_close}个结束")

        if think_open > 1:
            result["warnings"].append("多个think标签，可能需要检查格式")

        # 检查控制符
        ask_count = text.count('<ASK>')
        ask_close_count = text.count('</ASK>')
        final_count = text.count('<FINAL>')
        final_close_count = text.count('</FINAL>')

        if ask_count != ask_close_count:
            result["is_valid"] = False
            result["errors"].append(f"ASK标签不匹配: {ask_count}个开始, {ask_close_count}个结束")

        if final_count != final_close_count:
            result["is_valid"] = False
            result["errors"].append(f"FINAL标签不匹配: {final_count}个开始, {final_close_count}个结束")

        # 检查是否有内容
        think_part, content_part = self.split_reasoning_and_content(text)
        if not content_part.strip():
            result["warnings"].append("内容部分为空")

        return result


def split_reasoning_and_content(text: str) -> Tuple[str, str]:
    """便捷函数：切分思考流和内容"""
    parser = ReasoningParser()
    return parser.split_reasoning_and_content(text)


def strip_reasoning_for_history(text: str, thought_in_history: bool = False) -> str:
    """便捷函数：为历史写回剥离推理内容"""
    parser = ReasoningParser(thought_in_history=thought_in_history)
    return parser.strip_reasoning_for_history(text)


def validate_reasoning_format(text: str) -> dict:
    """便捷函数：校验推理格式"""
    parser = ReasoningParser()
    return parser.validate_reasoning_format(text)


if __name__ == "__main__":
    # 测试用例
    test_cases = [
        # 正常情况
        "<think>用户没说城市和预算，需要澄清</think><ASK>你在哪个城市？预算多少？</ASK>",
        # 无思考流
        "<ASK>请提供更多信息</ASK>",
        # 只有思考流
        "<think>这是一个测试</think>",
        # 复杂内容
        "<think>分析用户需求：位置和预算都是关键信息</think><ASK>你在哪个城市？预算范围是多少？</ASK><FINAL>根据你的信息，我推荐以下餐厅...</FINAL>",
        # 标签不匹配
        "<think>思考内容<ASK>问题</ASK>",
        # 多标签
        "<think>第一部分</think>中间内容<think>第二部分</think><ASK>问题</ASK>",
    ]

    for i, test_text in enumerate(test_cases, 1):
        print(f"\n=== 测试用例 {i} ===")
        print(f"输入: {test_text}")

        # 切分测试
        think, content = split_reasoning_and_content(test_text)
        print(f"思考流: '{think}'")
        print(f"内容: '{content}'")

        # 历史写回测试
        history_content = strip_reasoning_for_history(test_text)
        print(f"历史内容: '{history_content}'")

        # 校验测试
        validation = validate_reasoning_format(test_text)
        print(f"校验结果: {validation}")

        # 控制符提取
        symbols = ReasoningParser().extract_control_symbols(test_text)
        print(f"控制符: {symbols}")
