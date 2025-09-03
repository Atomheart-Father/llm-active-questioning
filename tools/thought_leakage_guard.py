#!/usr/bin/env python3
"""Thought Leakage Guard - 思维链泄漏防护

确保<think>标签不会泄漏到对话历史中。
提供研究模式的开关控制。
"""

import os
import re
from typing import Optional, Dict, Any
from pathlib import Path

# 全局配置
THOUGHT_IN_HISTORY = os.getenv("THOUGHT_IN_HISTORY", "false").lower() == "true"

class ThoughtLeakageGuard:
    """思维链泄漏防护器"""

    def __init__(self, thought_in_history: bool = False):
        self.thought_in_history = thought_in_history or THOUGHT_IN_HISTORY

    def strip_thought_for_history(self, text: str) -> str:
        """为对话历史剥离思考流

        Args:
            text: 原始文本，可能包含<think>标签

        Returns:
            str: 适合写入对话历史的文本
        """
        if self.thought_in_history:
            # 研究模式：保留思考流
            return text
        else:
            # 生产模式：移除思考流
            return self._remove_think_tags(text)

    def _remove_think_tags(self, text: str) -> str:
        """移除<think>标签及其内容"""
        # 使用正则表达式移除所有<think>...</think>块
        pattern = r'<think>.*?</think>'
        return re.sub(pattern, '', text, flags=re.DOTALL).strip()

    def detect_thought_leakage(self, text: str) -> Dict[str, Any]:
        """检测思维链泄漏

        Args:
            text: 待检查的文本

        Returns:
            dict: 检测结果
        """
        result = {
            "has_leakage": False,
            "leakage_positions": [],
            "recommendation": ""
        }

        # 检查是否包含<think>标签
        think_pattern = r'<think>(.*?)</think>'
        matches = list(re.finditer(think_pattern, text, re.DOTALL))

        if matches:
            result["has_leakage"] = True
            result["leakage_positions"] = [
                {"start": match.start(), "end": match.end(), "content": match.group(1)[:50] + "..."}
                for match in matches
            ]
            result["recommendation"] = "检测到思维链泄漏，建议使用strip_thought_for_history()处理"

        return result

    def validate_history_entry(self, history_entry: str) -> bool:
        """验证历史条目是否安全

        Args:
            history_entry: 历史条目文本

        Returns:
            bool: 是否安全（不包含思维链）
        """
        leakage = self.detect_thought_leakage(history_entry)
        return not leakage["has_leakage"]

    def safe_history_append(self, history: list, new_entry: str) -> list:
        """安全地添加到对话历史

        Args:
            history: 现有历史列表
            new_entry: 新条目

        Returns:
            list: 更新后的历史列表
        """
        safe_entry = self.strip_thought_for_history(new_entry)

        # 验证处理后的条目
        if not self.validate_history_entry(safe_entry):
            raise ValueError("即使经过处理，新条目仍包含思维链泄漏")

        history.append(safe_entry)
        return history

def create_guard(thought_in_history: Optional[bool] = None) -> ThoughtLeakageGuard:
    """创建思维链防护器

    Args:
        thought_in_history: 是否在历史中包含思考流，默认为None（使用环境变量）

    Returns:
        ThoughtLeakageGuard: 配置好的防护器
    """
    if thought_in_history is None:
        thought_in_history = THOUGHT_IN_HISTORY

    return ThoughtLeakageGuard(thought_in_history=thought_in_history)

def main():
    """演示和测试功能"""
    print("🛡️  思维链泄漏防护演示")
    print("=" * 50)

    # 创建防护器
    guard = create_guard()

    # 测试文本
    test_texts = [
        # 包含思考流的文本
        "<think>用户问了一个复杂问题，我需要仔细分析</think><ASK> 您能提供更多上下文吗？ </ASK>",
        # 普通文本
        "<FINAL> 这是最终回答 </FINAL>",
        # 混合内容
        "<think>这是一个测试</think>正常内容<ASK> 测试问题 </ASK><think>另一个思考</think>"
    ]

    for i, text in enumerate(test_texts, 1):
        print(f"\n测试 {i}:")
        print(f"原始: {text}")

        # 处理历史
        safe_text = guard.strip_thought_for_history(text)
        print(f"安全: {safe_text}")

        # 检测泄漏
        leakage = guard.detect_thought_leakage(text)
        if leakage["has_leakage"]:
            print(f"⚠️  检测到泄漏: {len(leakage['leakage_positions'])} 处")
        else:
            print("✅ 无泄漏")

    print("\n" + "=" * 50)
    print(f"当前模式: {'研究模式（保留思考流）' if THOUGHT_IN_HISTORY else '生产模式（移除思考流）'}")
    print("要切换到研究模式，请设置环境变量: THOUGHT_IN_HISTORY=true")

if __name__ == "__main__":
    main()
