#!/usr/bin/env python3
"""修正样本数据到Schema v1.1规范"""

import json
import os
import re
from pathlib import Path

def fix_sample_schema():
    """修正样本数据到v1.1规范"""
    print("🔧 开始修正样本数据到Schema v1.1...")

    data_dir = Path("data/gen/2025-09-03")

    # 处理ALC样本
    alc_file = data_dir / "ALC" / "part-001.jsonl"
    if alc_file.exists():
        print("📝 修正ALC样本...")
        fixed_alc_samples = fix_alc_samples(alc_file)
        save_fixed_samples(alc_file, fixed_alc_samples)

    # 处理RSD样本
    rsd_file = data_dir / "RSD" / "part-001.jsonl"
    if rsd_file.exists():
        print("📝 修正RSD样本...")
        fixed_rsd_samples = fix_rsd_samples(rsd_file)
        save_fixed_samples(rsd_file, fixed_rsd_samples)

    print("✅ 样本修正完成！")

def fix_alc_samples(file_path):
    """修正ALC样本"""
    fixed_samples = []

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                sample = json.loads(line)
                fixed_sample = fix_alc_sample(sample)
                fixed_samples.append(fixed_sample)
            except json.JSONDecodeError as e:
                print(f"❌ 解析错误: {e}")
                continue

    return fixed_samples

def fix_alc_sample(sample):
    """修正单个ALC样本"""
    # 1. 修正turns字段：speaker/utterance → role/text
    if "turns" in sample:
        fixed_turns = []
        for turn in sample["turns"]:
            fixed_turn = {
                "role": turn.get("speaker", "user") if "speaker" in turn else turn.get("role", "user"),
                "text": turn.get("utterance", "") if "utterance" in turn else turn.get("text", "")
            }
            fixed_turns.append(fixed_turn)
        sample["turns"] = fixed_turns

    # 2. 修正首回合助手的role为model_target
    for turn in sample["turns"]:
        if turn["role"] == "assistant":
            turn["role"] = "model_target"
            break

    # 3. 修正model_target内容：只保留ASK标签
    for turn in sample["turns"]:
        if turn["role"] == "model_target":
            text = turn["text"]
            # 提取<ASK>标签内容
            ask_match = re.search(r'<ASK>(.*?)</ASK>', text, re.DOTALL)
            if ask_match:
                # 只保留ASK标签内容，不包含礼貌语
                ask_content = ask_match.group(1).strip()
                # 清理礼貌语
                ask_content = ask_content.replace("为了更好地帮你规划，我需要一些信息。首先，", "")
                ask_content = ask_content.replace("这样我才能推荐合适的活动地点和方案。", "")
                ask_content = ask_content.replace("我们需要这些信息才能更好地推荐合适的户外活动地点和项目。", "")
                ask_content = ask_content.replace("其次，", "？")
                ask_content = ask_content.replace("  ", " ")
                ask_content = ask_content.strip()
                turn["text"] = f"<ASK>{ask_content}</ASK>"
            break

    # 4. 补齐labels字段
    if "labels" not in sample:
        sample["labels"] = {}

    sample["labels"].update({
        "ambiguity_types": ["preference", "budget", "context"],
        "ask_required": True,
        "good_question_set": ["活动类型", "预算范围", "时间安排"],
        "minimal_clarifications": 2
    })

    # 5. 补全reasoning.actions
    if "reasoning" not in sample:
        sample["reasoning"] = {}

    sample["reasoning"]["actions"] = [
        {"t": "AWARE_GAP", "vars": ["preference", "budget", "context"]},
        {"t": "ASK", "q": "请告诉我活动类型、预算和时间安排"},
        {"t": "STOP_ASK"}
    ]

    # 6. 修正source字段
    sample["source"] = "synthetic-gemini"

    return sample

def fix_rsd_samples(file_path):
    """修正RSD样本"""
    fixed_samples = []

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                sample = json.loads(line)
                fixed_sample = fix_rsd_sample(sample)
                fixed_samples.append(fixed_sample)
            except json.JSONDecodeError as e:
                print(f"❌ 解析错误: {e}")
                continue

    return fixed_samples

def fix_rsd_sample(sample):
    """修正单个RSD样本"""
    # 1. 修正turns字段（如果存在）
    if "turns" in sample:
        fixed_turns = []
        for turn in sample["turns"]:
            fixed_turn = {
                "role": turn.get("speaker", "user") if "speaker" in turn else turn.get("role", "user"),
                "text": turn.get("utterance", "") if "utterance" in turn else turn.get("text", "")
            }
            fixed_turns.append(fixed_turn)
        sample["turns"] = fixed_turns

        # 修正首回合助手的role
        for turn in sample["turns"]:
            if turn["role"] == "assistant":
                turn["role"] = "model_target"
                break

    # 2. 补齐labels字段
    if "labels" not in sample:
        sample["labels"] = {}

    sample["labels"].update({
        "ambiguity_types": ["method"],
        "ask_required": True,
        "good_question_set": ["推理方法"],
        "minimal_clarifications": 1
    })

    # 3. 补全reasoning字段
    if "reasoning" not in sample:
        sample["reasoning"] = {}

    # 确保actions字段存在并完整
    if "actions" not in sample["reasoning"]:
        sample["reasoning"]["actions"] = []

    # 如果actions为空，添加默认动作序列
    if not sample["reasoning"]["actions"]:
        sample["reasoning"]["actions"] = [
            {"t": "AWARE_GAP", "vars": ["method"]},
            {"t": "ASK", "q": "请说明推理方法"},
            {"t": "DERIVE", "note": "使用逻辑推理"},
            {"t": "VERIFY", "note": "检查推理正确性"},
            {"t": "FINALIZE"}
        ]

    # 4. 修正source字段
    sample["source"] = "r1-distill"

    return sample

def save_fixed_samples(file_path, samples):
    """保存修正后的样本"""
    with open(file_path, 'w', encoding='utf-8') as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')

    print(f"✅ 已保存 {len(samples)} 个修正后的样本到 {file_path}")

def validate_fixed_samples():
    """验证修正后的样本"""
    print("\n🔍 验证修正结果...")

    data_dir = Path("data/gen/2025-09-03")

    # 检查ALC样本
    alc_file = data_dir / "ALC" / "part-001.jsonl"
    if alc_file.exists():
        print("📋 检查ALC样本...")
        validate_sample_file(alc_file, "ALC")

    # 检查RSD样本
    rsd_file = data_dir / "RSD" / "part-001.jsonl"
    if rsd_file.exists():
        print("📋 检查RSD样本...")
        validate_sample_file(rsd_file, "RSD")

def validate_sample_file(file_path, sample_type):
    """验证样本文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print(f"   文件: {file_path}")
    print(f"   样本数: {len(lines)}")

    # 检查前3个样本
    for i, line in enumerate(lines[:3]):
        try:
            sample = json.loads(line.strip())

            # 检查基本字段
            required_fields = ["id", "domain", "source", "turns", "labels", "reasoning"]
            for field in required_fields:
                if field not in sample:
                    print(f"   ❌ 样本{i+1}缺少字段: {field}")

            # 检查turns格式
            if "turns" in sample and len(sample["turns"]) > 0:
                first_turn = sample["turns"][0]
                if "role" not in first_turn or "text" not in first_turn:
                    print(f"   ❌ 样本{i+1} turns格式错误")

            # 检查source值
            if sample_type == "ALC" and sample.get("source") != "synthetic-gemini":
                print(f"   ❌ 样本{i+1} source不正确: {sample.get('source')}")
            elif sample_type == "RSD" and sample.get("source") != "r1-distill":
                print(f"   ❌ 样本{i+1} source不正确: {sample.get('source')}")

            # 检查labels
            labels = sample.get("labels", {})
            required_labels = ["ambiguity_types", "ask_required", "good_question_set", "minimal_clarifications"]
            for label in required_labels:
                if label not in labels:
                    print(f"   ❌ 样本{i+1}缺少labels字段: {label}")

        except json.JSONDecodeError:
            print(f"   ❌ 样本{i+1} JSON格式错误")

    print("   ✅ 验证完成")

if __name__ == "__main__":
    fix_sample_schema()
    validate_fixed_samples()
