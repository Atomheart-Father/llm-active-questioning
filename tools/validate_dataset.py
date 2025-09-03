#!/usr/bin/env python3
"""Dataset Validation Tool for Schema v1.1

校验数据结构和质量，生成统计报告。
"""

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Any

from src.data.loader import DataLoader, Sample

def collect_statistics(samples: List[Sample]) -> Dict[str, Any]:
    """收集数据集统计信息"""
    stats = {
        "total_samples": len(samples),
        "domain_distribution": Counter(),
        "source_distribution": Counter(),
        "ask_required_distribution": Counter(),
        "ambiguity_types_distribution": Counter(),
        "action_types_distribution": Counter(),
        "turns_length_stats": {
            "min": float('inf'),
            "max": 0,
            "avg": 0,
            "total_turns": 0
        },
        "clarification_questions_stats": {
            "min": float('inf'),
            "max": 0,
            "avg": 0,
            "total_questions": 0
        },
        "minimal_clarifications_stats": {
            "min": float('inf'),
            "max": 0,
            "avg": 0
        }
    }

    total_turns = 0
    total_questions = 0
    total_min_clarifications = 0

    for sample in samples:
        # 基础分布统计
        stats["domain_distribution"][sample.domain] += 1
        stats["source_distribution"][sample.source] += 1

        if "ask_required" in sample.labels:
            stats["ask_required_distribution"][sample.labels["ask_required"]] += 1

        # 歧义类型统计
        if "ambiguity_types" in sample.labels:
            for amb_type in sample.labels["ambiguity_types"]:
                stats["ambiguity_types_distribution"][amb_type] += 1

        # 动作类型统计
        if "actions" in sample.reasoning:
            for action in sample.reasoning["actions"]:
                if isinstance(action, dict) and "t" in action:
                    stats["action_types_distribution"][action["t"]] += 1

        # 轮次长度统计
        turns_count = len(sample.turns)
        stats["turns_length_stats"]["min"] = min(stats["turns_length_stats"]["min"], turns_count)
        stats["turns_length_stats"]["max"] = max(stats["turns_length_stats"]["max"], turns_count)
        total_turns += turns_count

        # 澄清问题统计
        if "good_question_set" in sample.labels:
            questions_count = len(sample.labels["good_question_set"])
            stats["clarification_questions_stats"]["min"] = min(
                stats["clarification_questions_stats"]["min"], questions_count
            )
            stats["clarification_questions_stats"]["max"] = max(
                stats["clarification_questions_stats"]["max"], questions_count
            )
            total_questions += questions_count

        # 最少澄清数统计
        if "minimal_clarifications" in sample.labels:
            min_clar = sample.labels["minimal_clarifications"]
            stats["minimal_clarifications_stats"]["min"] = min(
                stats["minimal_clarifications_stats"]["min"], min_clar
            )
            stats["minimal_clarifications_stats"]["max"] = max(
                stats["minimal_clarifications_stats"]["max"], min_clar
            )
            total_min_clarifications += min_clar

    # 计算平均值
    if samples:
        stats["turns_length_stats"]["avg"] = total_turns / len(samples)
        stats["clarification_questions_stats"]["avg"] = total_questions / len(samples)
        stats["minimal_clarifications_stats"]["avg"] = total_min_clarifications / len(samples)

    # 处理边界情况
    if stats["turns_length_stats"]["min"] == float('inf'):
        stats["turns_length_stats"]["min"] = 0
    if stats["clarification_questions_stats"]["min"] == float('inf'):
        stats["clarification_questions_stats"]["min"] = 0
    if stats["minimal_clarifications_stats"]["min"] == float('inf'):
        stats["minimal_clarifications_stats"]["min"] = 0

    stats["turns_length_stats"]["total_turns"] = total_turns
    stats["clarification_questions_stats"]["total_questions"] = total_questions

    return stats

def generate_markdown_report(stats: Dict[str, Any], validation_report: Dict[str, Any]) -> str:
    """生成Markdown格式的报告"""
    report = []

    # 标题
    report.append("# 数据集校验报告")
    report.append("")
    report.append("## 数据集概览")
    report.append("")
    report.append(f"- **总样本数**: {stats['total_samples']}")
    report.append(f"- **校验错误**: {validation_report['error_count']}")
    report.append(f"- **校验警告**: {validation_report['warning_count']}")
    report.append("")

    # 分布统计
    report.append("## 分布统计")
    report.append("")

    # 领域分布
    report.append("### 领域分布")
    for domain, count in sorted(stats["domain_distribution"].items()):
        percentage = (count / stats["total_samples"]) * 100 if stats["total_samples"] > 0 else 0
        report.append(f"- **{domain}**: {count} ({percentage:.1f}%)")
    report.append("")

    # 来源分布
    report.append("### 来源分布")
    for source, count in sorted(stats["source_distribution"].items()):
        percentage = (count / stats["total_samples"]) * 100 if stats["total_samples"] > 0 else 0
        report.append(f"- **{source}**: {count} ({percentage:.1f}%)")
    report.append("")

    # 澄清需求分布
    report.append("### 澄清需求分布")
    for ask_required, count in sorted(stats["ask_required_distribution"].items()):
        percentage = (count / stats["total_samples"]) * 100 if stats["total_samples"] > 0 else 0
        report.append(f"- **需要澄清: {ask_required}**: {count} ({percentage:.1f}%)")
    report.append("")

    # 歧义类型分布
    report.append("### 歧义类型分布")
    for amb_type, count in sorted(stats["ambiguity_types_distribution"].items()):
        percentage = (count / stats["total_samples"]) * 100 if stats["total_samples"] > 0 else 0
        report.append(f"- **{amb_type}**: {count} ({percentage:.1f}%)")
    report.append("")

    # 动作类型分布
    report.append("### 推理动作分布")
    for action_type, count in sorted(stats["action_types_distribution"].items()):
        total_actions = sum(stats["action_types_distribution"].values())
        percentage = (count / total_actions) * 100 if total_actions > 0 else 0
        report.append(f"- **{action_type}**: {count} ({percentage:.1f}%)")
    report.append("")

    # 数值统计
    report.append("## 数值统计")
    report.append("")

    # 轮次长度
    turns_stats = stats["turns_length_stats"]
    report.append("### 对话轮次统计")
    report.append(f"- **最小轮次**: {turns_stats['min']}")
    report.append(f"- **最大轮次**: {turns_stats['max']}")
    report.append(f"- **平均轮次**: {turns_stats['avg']:.1f}")
    report.append(f"- **总轮次数**: {turns_stats['total_turns']}")
    report.append("")

    # 澄清问题
    questions_stats = stats["clarification_questions_stats"]
    report.append("### 澄清问题统计")
    report.append(f"- **最小问题数**: {questions_stats['min']}")
    report.append(f"- **最大问题数**: {questions_stats['max']}")
    report.append(f"- **平均问题数**: {questions_stats['avg']:.1f}")
    report.append(f"- **总问题数**: {questions_stats['total_questions']}")
    report.append("")

    # 最少澄清数
    min_clar_stats = stats["minimal_clarifications_stats"]
    report.append("### 最少澄清数统计")
    report.append(f"- **最小值**: {min_clar_stats['min']}")
    report.append(f"- **最大值**: {min_clar_stats['max']}")
    report.append(f"- **平均值**: {min_clar_stats['avg']:.1f}")
    report.append("")

    # 校验问题
    if validation_report["errors"]:
        report.append("## 校验问题")
        report.append("")
        report.append("### 错误")
        for error in validation_report["errors"][:10]:  # 只显示前10个
            report.append(f"- **{error['sample_id']}.{error['field']}**: {error['message']}")
        if len(validation_report["errors"]) > 10:
            report.append(f"- ... 还有 {len(validation_report['errors']) - 10} 个错误")
        report.append("")

    # 注意：详细的warnings信息在loader.errors中，需要进一步处理

    return "\n".join(report)

def main():
    if len(sys.argv) != 2:
        print("用法: python tools/validate_dataset.py <数据文件路径>")
        print("示例: python tools/validate_dataset.py data/seed/ALC/seed.jsonl")
        sys.exit(1)

    file_path = sys.argv[1]
    output_path = "reports/data_overview.md"

    try:
        # 加载数据
        loader = DataLoader(strict_mode=False)
        samples = list(loader.load_jsonl(file_path))

        # 收集统计信息
        stats = collect_statistics(samples)
        validation_report = loader.get_validation_report()

        # 生成报告
        report = generate_markdown_report(stats, validation_report)

        # 写入文件
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)

        # 控制台输出摘要
        print("✅ 数据集校验完成")
        print(f"📊 总样本数: {stats['total_samples']}")
        print(f"❌ 校验错误: {validation_report['error_count']}")
        print(f"⚠️  校验警告: {validation_report['warning_count']}")
        print(f"📝 报告已保存至: {output_path}")

        # 如果有严重错误，退出码非零
        if validation_report["error_count"] > 0:
            print("\n⚠️  发现校验错误，请检查数据质量")
            sys.exit(1)

    except Exception as e:
        print(f"❌ 校验失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
