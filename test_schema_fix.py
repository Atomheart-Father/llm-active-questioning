#!/usr/bin/env python3
"""测试Schema v1.1修正是否生效"""

import sys
import os
sys.path.append('.')

from tools.data_generator import DataGenerator, GenerationConfig

def test_schema_fix():
    """测试修正后的样本格式"""
    print("🔧 测试Schema v1.1修正...")

    # 创建配置
    config = GenerationConfig(
        batch_date="2025-09-03",
        alc_count=1,
        ar_count=1,
        rsd_count=1
    )

    # 创建生成器
    generator = DataGenerator(config)

    # 测试不同类型的默认数据
    test_types = ["ALC", "AR", "RSD"]

    for data_type in test_types:
        print(f"\n📋 测试{data_type}类型...")

        # 获取默认数据
        default_data = generator._get_default_data_for_type(data_type)

        # 格式化样本
        sample = generator._format_sample(data_type, default_data, 0)

        # 验证Schema v1.1
        validate_sample(data_type, sample)

def validate_sample(data_type, sample):
    """验证样本是否符合v1.1规范"""
    errors = []

    # 1. 检查基本字段
    required_fields = ["id", "domain", "source", "turns", "labels", "reasoning"]
    for field in required_fields:
        if field not in sample:
            errors.append(f"缺少字段: {field}")

    # 2. 检查turns格式
    if "turns" in sample:
        for i, turn in enumerate(sample["turns"]):
            if "role" not in turn or "text" not in turn:
                errors.append(f"turns[{i}]缺少role或text字段")
            # 检查首个助手回合是否为model_target
            if turn["role"] == "assistant":
                errors.append("发现assistant角色，应该改为model_target")

    # 3. 检查model_target内容
    for turn in sample["turns"]:
        if turn["role"] == "model_target":
            if not turn["text"].startswith("<ASK>") or not turn["text"].endswith("</ASK>"):
                errors.append("model_target内容格式错误")
            # 检查是否只包含ASK标签
            if "为了更好地" in turn["text"] or "这样我才能" in turn["text"]:
                errors.append("model_target包含礼貌语")

    # 4. 检查source值
    expected_source = "synthetic-gemini" if data_type in ["ALC", "AR"] else "r1-distill"
    if sample.get("source") != expected_source:
        errors.append(f"source值错误: {sample.get('source')}，期望: {expected_source}")

    # 5. 检查labels字段
    labels = sample.get("labels", {})
    required_labels = ["ambiguity_types", "ask_required", "good_question_set", "minimal_clarifications"]
    for label in required_labels:
        if label not in labels:
            errors.append(f"labels缺少字段: {label}")

    # AR类型额外检查oracle_answer
    if data_type == "AR" and "oracle_answer" not in labels:
        errors.append("AR类型labels缺少oracle_answer字段")

    # 6. 检查reasoning字段
    reasoning = sample.get("reasoning", {})
    if "actions" not in reasoning:
        errors.append("reasoning缺少actions字段")
    elif not reasoning["actions"]:
        errors.append("reasoning.actions为空")

    # 输出结果
    if errors:
        print("❌ 发现错误:")
        for error in errors:
            print(f"   - {error}")
    else:
        print("✅ 验证通过")

    return len(errors) == 0

if __name__ == "__main__":
    test_schema_fix()
