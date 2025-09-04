#!/usr/bin/env python3
"""
测试Schema校验器的礼貌语过滤和控制符检测
"""

import pytest
from schema_validator import SchemaValidator


def test_politeness_filtering():
    """测试礼貌语过滤"""
    validator = SchemaValidator()

    # 测试中文礼貌语
    text_with_polite = "请帮我回答这个问题，谢谢！"
    cleaned = validator.strip_politeness(text_with_polite)

    # 应该移除礼貌语
    assert "请" not in cleaned, "应该过滤中文'请'"
    assert "谢谢" not in cleaned, "应该过滤中文'谢谢'"

    # 测试英文礼貌语
    text_with_polite_en = "Please help me with this, thank you!"
    cleaned_en = validator.strip_politeness(text_with_polite_en)

    assert "Please" not in cleaned_en, "应该过滤英文'Please'"
    assert "thank you" not in cleaned_en, "应该过滤英文'thank you'"


def test_multiple_control_symbols():
    """测试多控制符检测"""
    validator = SchemaValidator()

    # 测试单个控制符（应该通过）
    single_ask = "<ASK>请问时间是什么时候？</ASK>"
    is_valid, errors = validator._validate_control_symbols(single_ask)
    assert is_valid, f"单个ASK应该有效: {errors}"

    # 测试多个控制符（应该失败）
    multiple_symbols = "<ASK>请问时间？</ASK><FINAL>时间是下午</FINAL>"
    is_valid, errors = validator._validate_control_symbols(multiple_symbols)
    assert not is_valid, "多个控制符应该无效"
    assert any("只能包含一个控制符" in error for error in errors), "应该检测到多控制符问题"


def test_polite_in_model_target():
    """测试model_target中的礼貌语检测"""
    validator = SchemaValidator()

    # 包含礼貌语的model_target
    model_target_with_polite = "<ASK>请帮我回答这个问题，谢谢</ASK>"
    is_valid, errors = validator._validate_control_symbols(model_target_with_polite)

    assert not is_valid, "包含礼貌语的model_target应该无效"
    assert any("不能包含礼貌语" in error for error in errors), "应该检测到礼貌语问题"


def test_json_repair_with_polite():
    """测试JSON修复时移除礼貌语"""
    validator = SchemaValidator()

    # 模拟包含礼貌语的JSON响应
    json_text = '''{
        "turns": [
            {"role": "user", "text": "请问时间"},
            {"role": "model_target", "text": "<ASK>请告诉我时间，谢谢</ASK>"}
        ],
        "labels": {"ask_required": true},
        "reasoning": {"actions": ["ASK"]},
        "source": "test"
    }'''

    repaired = validator.repair_sample(json_text, max_retries=1)

    if repaired:
        # 检查是否移除了礼貌语
        model_target = repaired["turns"][1]["text"]
        assert "请" not in model_target or "<ASK>" in model_target, "应该在有效控制符中保留功能性内容"
        assert "谢谢" not in model_target, "应该移除礼貌语"


def test_minimal_repair():
    """测试最小补全修复"""
    validator = SchemaValidator()

    # 缺失关键字段的样本
    incomplete_sample = {
        "turns": [],
        "labels": {},
        "reasoning": {}
        # 缺少source
    }

    errors = ["缺少必需字段: source", "turns字段为空"]
    repaired = validator._minimal_repair(incomplete_sample, errors)

    assert repaired is not None, "应该能够修复"
    assert "source" in repaired, "应该补全source字段"
    assert len(repaired["turns"]) > 0, "应该补全turns字段"


def test_text_preprocessing():
    """测试文本预处理"""
    validator = SchemaValidator()

    # 包含markdown和多余文本的JSON
    messy_text = '''一些说明文字
```json
{
    "turns": [{"role": "user", "text": "test"}]
}
```
更多说明文字'''

    cleaned = validator._preprocess_text(messy_text)

    # 应该只保留JSON部分
    assert cleaned.startswith("{"), "应该以JSON开始"
    assert cleaned.endswith("}"), "应该以JSON结束"
    assert "```" not in cleaned, "应该移除markdown标记"
    assert "一些说明文字" not in cleaned, "应该移除多余文本"


if __name__ == "__main__":
    test_politeness_filtering()
    test_multiple_control_symbols()
    test_polite_in_model_target()
    test_json_repair_with_polite()
    test_minimal_repair()
    test_text_preprocessing()
    print("所有Schema测试通过!")
