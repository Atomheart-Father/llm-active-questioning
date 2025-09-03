#!/usr/bin/env python3
"""测试Schema修正后的数据生成"""

import sys
import os
import json
sys.path.append('.')

from tools.data_generator import DataGenerator, GenerationConfig

def test_generation():
    """测试数据生成流程"""
    print("🚀 测试Schema修正后的数据生成...")

    # 创建配置 - 只生成少量样本测试
    config = GenerationConfig(
        batch_date="2025-09-03",
        alc_count=2,  # 只生成2个ALC样本测试
        ar_count=1,   # 只生成1个AR样本测试
        rsd_count=1   # 只生成1个RSD样本测试
    )

    # 创建生成器
    generator = DataGenerator(config)

    print("📝 生成测试数据...")

    # 生成少量数据测试
    alc_samples = []
    ar_samples = []
    rsd_samples = []

    # 生成ALC数据
    print("  生成ALC数据...")
    for i in range(config.alc_count):
        # 使用默认数据测试格式化
        default_data = generator._get_default_data_for_type("ALC")
        sample = generator._format_sample("ALC", default_data, i)
        alc_samples.append(sample)
        print(f"    ALC-{i:04d}: ✅")

    # 生成AR数据
    print("  生成AR数据...")
    for i in range(config.ar_count):
        default_data = generator._get_default_data_for_type("AR")
        sample = generator._format_sample("AR", default_data, i)
        ar_samples.append(sample)
        print(f"    AR-{i:04d}: ✅")

    # 生成RSD数据
    print("  生成RSD数据...")
    for i in range(config.rsd_count):
        default_data = generator._get_default_data_for_type("RSD")
        sample = generator._format_sample("RSD", default_data, i)
        rsd_samples.append(sample)
        print(f"    RSD-{i:04d}: ✅")

    # 保存测试结果
    print("💾 保存测试结果...")

    # 保存ALC
    alc_file = generator.output_dir / "ALC" / "test_part-001.jsonl"
    alc_file.parent.mkdir(parents=True, exist_ok=True)
    with open(alc_file, 'w', encoding='utf-8') as f:
        for sample in alc_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    print(f"  ALC保存到: {alc_file}")

    # 保存AR
    ar_file = generator.output_dir / "AR" / "test_part-001.jsonl"
    ar_file.parent.mkdir(parents=True, exist_ok=True)
    with open(ar_file, 'w', encoding='utf-8') as f:
        for sample in ar_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    print(f"  AR保存到: {ar_file}")

    # 保存RSD
    rsd_file = generator.output_dir / "RSD" / "test_part-001.jsonl"
    rsd_file.parent.mkdir(parents=True, exist_ok=True)
    with open(rsd_file, 'w', encoding='utf-8') as f:
        for sample in rsd_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    print(f"  RSD保存到: {rsd_file}")

    # 验证生成的样本
    print("\n🔍 验证生成的样本...")
    validate_generated_samples(alc_file, ar_file, rsd_file)

def validate_generated_samples(alc_file, ar_file, rsd_file):
    """验证生成的样本"""
    import re

    def validate_file(file_path, data_type):
        print(f"  验证{data_type}文件: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                sample = json.loads(line.strip())

                # 检查基本字段
                assert "id" in sample, f"样本{line_num}缺少id"
                assert "source" in sample, f"样本{line_num}缺少source"

                # 检查source值
                if data_type in ["ALC", "AR"]:
                    assert sample["source"] == "synthetic-gemini", f"source错误: {sample['source']}"
                else:
                    assert sample["source"] == "r1-distill", f"source错误: {sample['source']}"

                # 检查turns格式
                assert "turns" in sample, f"样本{line_num}缺少turns"
                for turn in sample["turns"]:
                    assert "role" in turn and "text" in turn, f"turns格式错误: {turn}"

                # 检查model_target
                model_target_found = False
                for turn in sample["turns"]:
                    if turn["role"] == "model_target":
                        model_target_found = True
                        assert turn["text"].startswith("<ASK>") and turn["text"].endswith("</ASK>"), f"model_target格式错误: {turn['text']}"
                        # 检查是否只包含ASK内容
                        ask_match = re.search(r'<ASK>(.*?)</ASK>', turn["text"])
                        if ask_match:
                            ask_content = ask_match.group(1)
                            assert "为了更好地" not in ask_content, f"包含礼貌语: {ask_content}"
                            assert "这样我才能" not in ask_content, f"包含礼貌语: {ask_content}"
                        break
                assert model_target_found, f"样本{line_num}缺少model_target"

                # 检查labels
                assert "labels" in sample, f"样本{line_num}缺少labels"
                labels = sample["labels"]
                assert "ambiguity_types" in labels, f"labels缺少ambiguity_types"
                assert "ask_required" in labels, f"labels缺少ask_required"
                assert "good_question_set" in labels, f"labels缺少good_question_set"
                assert "minimal_clarifications" in labels, f"labels缺少minimal_clarifications"

                if data_type == "AR":
                    assert "oracle_answer" in labels, f"AR类型labels缺少oracle_answer"

                # 检查reasoning
                assert "reasoning" in sample, f"样本{line_num}缺少reasoning"
                reasoning = sample["reasoning"]
                assert "actions" in reasoning, f"reasoning缺少actions"
                assert len(reasoning["actions"]) > 0, f"reasoning.actions为空"

                print(f"    样本{line_num}: ✅ 验证通过")

    try:
        validate_file(alc_file, "ALC")
        validate_file(ar_file, "AR")
        validate_file(rsd_file, "RSD")
        print("✅ 所有样本验证通过！")
    except AssertionError as e:
        print(f"❌ 验证失败: {e}")
        return False

    return True

if __name__ == "__main__":
    test_generation()
