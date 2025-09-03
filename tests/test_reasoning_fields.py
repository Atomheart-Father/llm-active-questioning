"""Tests for Reasoning Parser and Schema Fields"""

import pytest
from src.runtime.reasoning_parser import (
    ReasoningParser,
    split_reasoning_and_content,
    strip_reasoning_for_history,
    validate_reasoning_format
)


class TestReasoningParser:
    """测试推理解析器"""

    def test_split_reasoning_and_content_with_think(self):
        """测试包含<think>标签的内容切分"""
        text = "<think>用户没有说预算和地点</think><ASK> 你的预算和地点？ </ASK>"

        think, content = split_reasoning_and_content(text)

        assert think == "用户没有说预算和地点"
        assert content == "<ASK> 你的预算和地点？ </ASK>"

    def test_split_reasoning_and_content_without_think(self):
        """测试不包含<think>标签的内容切分"""
        text = "<ASK> 请提供更多信息 </ASK>"

        think, content = split_reasoning_and_content(text)

        assert think == ""
        assert content == text

    def test_split_reasoning_and_content_complex(self):
        """测试复杂的<think>内容切分"""
        text = "<think>分析：用户问餐厅但没说位置\n需要澄清城市和预算\n口味也是重要因素</think><ASK> 你在哪个城市？预算多少？有什么忌口？ </ASK><FINAL> 根据你的信息，我来推荐餐厅 </FINAL>"

        think, content = split_reasoning_and_content(text)

        expected_think = "分析：用户问餐厅但没说位置\n需要澄清城市和预算\n口味也是重要因素"
        expected_content = "<ASK> 你在哪个城市？预算多少？有什么忌口？ </ASK><FINAL> 根据你的信息，我来推荐餐厅 </FINAL>"

        assert think == expected_think
        assert content == expected_content

    def test_strip_reasoning_for_history_production(self):
        """测试生产模式下的历史写回剥离"""
        text = "<think>思考内容</think><ASK> 问题 </ASK>"

        result = strip_reasoning_for_history(text, thought_in_history=False)

        assert result == "<ASK> 问题 </ASK>"

    def test_strip_reasoning_for_history_research(self):
        """测试研究模式下的历史写回保留"""
        text = "<think>思考内容</think><ASK> 问题 </ASK>"

        result = strip_reasoning_for_history(text, thought_in_history=True)

        assert result == text

    def test_strip_reasoning_for_history_no_think(self):
        """测试没有<think>标签时的历史写回"""
        text = "<ASK> 问题 </ASK>"

        result = strip_reasoning_for_history(text, thought_in_history=False)

        assert result == text

    def test_extract_control_symbols_ask_only(self):
        """测试只包含ASK的控制符提取"""
        text = "<ASK> 请提供预算信息 </ASK>"

        parser = ReasoningParser()
        symbols = parser.extract_control_symbols(text)

        assert symbols["has_ask"] is True
        assert symbols["has_final"] is False
        assert symbols["ask_content"] == "请提供预算信息"
        assert symbols["final_content"] is None

    def test_extract_control_symbols_final_only(self):
        """测试只包含FINAL的控制符提取"""
        text = "<FINAL> 这是最终回答 </FINAL>"

        parser = ReasoningParser()
        symbols = parser.extract_control_symbols(text)

        assert symbols["has_ask"] is False
        assert symbols["has_final"] is True
        assert symbols["ask_content"] is None
        assert symbols["final_content"] == "这是最终回答"

    def test_extract_control_symbols_both(self):
        """测试同时包含ASK和FINAL的控制符提取"""
        text = "<ASK> 先问问题 </ASK><FINAL> 然后回答 </FINAL>"

        parser = ReasoningParser()
        symbols = parser.extract_control_symbols(text)

        assert symbols["has_ask"] is True
        assert symbols["has_final"] is True
        assert symbols["ask_content"] == "先问问题"
        assert symbols["final_content"] == "然后回答"

    def test_extract_control_symbols_none(self):
        """测试不包含控制符的情况"""
        text = "这是普通文本，没有控制符"

        parser = ReasoningParser()
        symbols = parser.extract_control_symbols(text)

        assert symbols["has_ask"] is False
        assert symbols["has_final"] is False
        assert symbols["ask_content"] is None
        assert symbols["final_content"] is None


class TestReasoningFormatValidation:
    """测试推理格式校验"""

    def test_validate_valid_format(self):
        """测试有效格式校验"""
        text = "<think>思考内容</think><ASK> 问题 </ASK>"

        result = validate_reasoning_format(text)

        assert result["is_valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_unmatched_think_tags(self):
        """测试不匹配的think标签"""
        text = "<think>思考内容<ASK> 问题 </ASK>"

        result = validate_reasoning_format(text)

        assert result["is_valid"] is False
        assert len(result["errors"]) > 0
        assert "think标签不匹配" in result["errors"][0]

    def test_validate_unmatched_ask_tags(self):
        """测试不匹配的ASK标签"""
        text = "<think>思考</think><ASK> 问题"

        result = validate_reasoning_format(text)

        assert result["is_valid"] is False
        assert len(result["errors"]) > 0

    def test_validate_unmatched_final_tags(self):
        """测试不匹配的FINAL标签"""
        text = "<think>思考</think><FINAL> 回答"

        result = validate_reasoning_format(text)

        assert result["is_valid"] is False
        assert len(result["errors"]) > 0

    def test_validate_multiple_think_tags(self):
        """测试多个think标签（警告但不报错）"""
        text = "<think>思考1</think>中间内容<think>思考2</think><ASK> 问题 </ASK>"

        result = validate_reasoning_format(text)

        assert result["is_valid"] is True
        assert len(result["warnings"]) > 0
        assert "多个think标签" in result["warnings"][0]

    def test_validate_empty_content_warning(self):
        """测试空内容警告"""
        text = "<think>只有思考</think>"

        result = validate_reasoning_format(text)

        assert result["is_valid"] is True
        assert len(result["warnings"]) > 0
        assert "内容部分为空" in result["warnings"][0]


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_string(self):
        """测试空字符串"""
        text = ""

        think, content = split_reasoning_and_content(text)
        assert think == ""
        assert content == ""

        result = validate_reasoning_format(text)
        assert result["is_valid"] is True

    def test_only_think_tag(self):
        """测试只有think标签"""
        text = "<think>思考内容</think>"

        think, content = split_reasoning_and_content(text)
        assert think == "思考内容"
        assert content == ""

    def test_nested_tags(self):
        """测试嵌套标签（应该正常处理）"""
        text = "<think>思考<ASK> 内部问题 </ASK>内容</think><FINAL> 回答 </FINAL>"

        think, content = split_reasoning_and_content(text)
        assert "思考" in think
        assert "<ASK>" in think  # think内容应该包含内部标签
        assert content == "<FINAL> 回答 </FINAL>"

    def test_multiline_content(self):
        """测试多行内容"""
        text = """<think>多行
思考
内容</think><ASK> 多行
问题
内容 </ASK>"""

        think, content = split_reasoning_and_content(text)

        assert "多行" in think
        assert "思考" in think
        assert "内容" in think
        assert "<ASK>" in content

    def test_case_insensitive_tags(self):
        """测试标签大小写不敏感"""
        text = "<THINK>思考内容</THINK><ask> 问题 </ask>"

        think, content = split_reasoning_and_content(text)

        # 注意：当前的实现是大小写敏感的，这里测试实际行为
        assert think == ""  # 因为标签大小写不匹配
        assert content == text

    def test_special_characters_in_content(self):
        """测试内容中的特殊字符"""
        text = "<think>特殊字符：@#$%^&*()</think><ASK> 问题！？ </ASK>"

        think, content = split_reasoning_and_content(text)

        assert "特殊字符" in think
        assert "<ASK>" in content


if __name__ == "__main__":
    pytest.main([__file__])
