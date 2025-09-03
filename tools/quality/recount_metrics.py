#!/usr/bin/env python3
"""
质量指标复算脚本
对 data/processed/active_qa_v1/ 目录下的数据进行重新计算和验证

功能：
1. 对齐验证：检查clarification_questions与assistant_response的一一对应关系
2. 去重统计：基于文本哈希计算重复样本
3. 证据重叠：计算clarification_questions与provided_context的词面重叠
4. 完整性统计：字段完备性检查
5. 许可合规：验证许可协议

输出：
- metrics.recount.json: 重新计算的指标
- metrics.diff.txt: 与现有metrics.json的差异
"""

import json
import os
import hashlib
import re
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
import difflib


def load_jsonl_file(filepath):
    """加载JSONL文件"""
    samples = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        sample = json.loads(line)
                        samples.append(sample)
                    except json.JSONDecodeError as e:
                        print(f"警告: {filepath}:{line_num} JSON解析错误: {e}")
    except FileNotFoundError:
        print(f"警告: 文件不存在 {filepath}")
    return samples


def validate_alignment(sample):
    """
    验证对齐：clarification_questions数量应与assistant_response中的枚举数量匹配

    返回：
    - is_aligned: 布尔值，表示是否对齐
    - error_reason: 如果不对齐，说明原因
    """
    questions = sample.get('clarification_questions', [])
    response = sample.get('assistant_response', '')

    if not questions:
        return False, "empty_questions"

    if not response:
        return False, "empty_response"

    # 提取response中的枚举答案数量
    # 匹配"若问题X则答案：XXX"的模式
    answer_pattern = r'若问题\d+则答案：'
    enumerated_answers = re.findall(answer_pattern, response)

    if len(questions) != len(enumerated_answers):
        return False, f"question_count_{len(questions)}_vs_answer_count_{len(enumerated_answers)}"

    return True, None


def calculate_text_hash(sample, fields=('user_query', 'clarification_questions', 'assistant_response')):
    """计算样本的文本哈希用于去重"""
    content_parts = []

    for field in fields:
        if field == 'clarification_questions':
            questions = sample.get(field, [])
            if isinstance(questions, list):
                content_parts.extend(questions)
            else:
                content_parts.append(str(questions))
        else:
            value = sample.get(field, '')
            content_parts.append(str(value))

    content = '|'.join(content_parts)
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def calculate_evidence_overlap(sample):
    """
    计算clarification_questions与provided_context的词面重叠率

    返回重叠词的比例 (0.0-1.0)
    """
    questions = sample.get('clarification_questions', [])
    context = sample.get('provided_context', '')

    if not questions or not context:
        return 0.0

    # 合并所有clarification_questions
    all_questions = ' '.join(questions) if isinstance(questions, list) else str(questions)

    # 简单分词（按空格分割，去掉标点）
    question_words = set(re.findall(r'\b\w+\b', all_questions.lower()))
    context_words = set(re.findall(r'\b\w+\b', context.lower()))

    if not question_words:
        return 0.0

    # 计算重叠词数
    overlap_words = question_words.intersection(context_words)
    return len(overlap_words) / len(question_words)


def validate_license(sample):
    """验证许可协议"""
    valid_licenses = {'cc-by-sa-3.0', 'cc-by-sa-4.0', 'mit', 'apache-2.0'}
    license_type = sample.get('licensing', '')

    return license_type in valid_licenses, license_type


def analyze_samples(samples):
    """分析样本集合，返回统计结果"""
    stats = {
        'total_samples': len(samples),
        'alignment_ok_count': 0,
        'alignment_errors': [],
        'duplicate_hashes': defaultdict(list),
        'license_errors': [],
        'field_completeness': defaultdict(int),
        'evidence_overlaps': [],
        'task_types': Counter(),
        'sources': Counter(),
        'licenses': Counter()
    }

    required_fields = ['uid', 'user_query', 'clarification_questions',
                      'assistant_response', 'task_type', 'source', 'licensing']

    for i, sample in enumerate(samples):
        # 字段完备性检查
        for field in required_fields:
            if field in sample and sample[field]:
                stats['field_completeness'][field] += 1

        # 对齐验证
        is_aligned, error_reason = validate_alignment(sample)
        if is_aligned:
            stats['alignment_ok_count'] += 1
        else:
            stats['alignment_errors'].append({
                'index': i,
                'uid': sample.get('uid', 'unknown'),
                'error': error_reason
            })

        # 去重哈希
        text_hash = calculate_text_hash(sample)
        stats['duplicate_hashes'][text_hash].append(i)

        # 证据重叠
        overlap_ratio = calculate_evidence_overlap(sample)
        stats['evidence_overlaps'].append(overlap_ratio)

        # 许可验证
        is_valid_license, license_type = validate_license(sample)
        if not is_valid_license:
            stats['license_errors'].append({
                'index': i,
                'uid': sample.get('uid', 'unknown'),
                'license': license_type
            })

        # 统计分类
        stats['task_types'][sample.get('task_type', 'unknown')] += 1
        stats['sources'][sample.get('source', 'unknown')] += 1
        stats['licenses'][sample.get('licensing', 'unknown')] += 1

    return stats


def calculate_deduplication_stats(duplicate_hashes):
    """计算去重统计"""
    original_count = sum(len(indices) for indices in duplicate_hashes.values())
    unique_count = len(duplicate_hashes)
    duplicates_removed = original_count - unique_count

    return {
        'original_count': original_count,
        'deduped_count': unique_count,
        'duplicates_removed': duplicates_removed,
        'deduplication_ratio': duplicates_removed / original_count if original_count > 0 else 0
    }


def generate_recounted_metrics(stats):
    """生成重新计算的指标文件"""
    total_samples = stats['total_samples']
    alignment_ok_count = stats['alignment_ok_count']
    alignment_error_count = total_samples - alignment_ok_count

    # 计算证据重叠统计（只计算HotpotQA/ASQA样本）
    evidence_overlaps = [overlap for overlap in stats['evidence_overlaps'] if overlap > 0]
    evidence_overlap_mean = sum(evidence_overlaps) / len(evidence_overlaps) if evidence_overlaps else 0

    metrics = {
        "timestamp": datetime.now().isoformat(),
        "total_samples": total_samples,
        "near_duplicates": {
            "duplicate_ratio": calculate_deduplication_stats(stats['duplicate_hashes'])['deduplication_ratio']
        },
        "alignment_stats": {
            "alignment_ok_count": alignment_ok_count,
            "alignment_error_count": alignment_error_count,
            "alignment_ok_percentage": (alignment_ok_count / total_samples * 100) if total_samples > 0 else 0
        },
        "shards": {
            # 这里需要从实际文件统计，暂时保持与原有结构一致
        },
        "by_shard": {
            # 这里需要从实际文件统计，暂时保持与原有结构一致
        },
        "license_whitelist_errors": stats['license_errors'],
        "summary": {
            "total_clarification_samples": total_samples,
            "total_alignment_errors": alignment_error_count,
            "field_completeness_avg": sum(stats['field_completeness'].values()) / (len(stats['field_completeness']) * total_samples) * 100 if total_samples > 0 else 0,
            "near_duplicates_avg": calculate_deduplication_stats(stats['duplicate_hashes'])['deduplication_ratio']
        },
        "evidence_overlap": {
            "mean": evidence_overlap_mean,
            "count": len(evidence_overlaps)
        },
        "recount_details": {
            "alignment_errors_detail": stats['alignment_errors'][:10],  # 只显示前10个错误详情
            "duplicate_clusters": {k: len(v) for k, v in list(stats['duplicate_hashes'].items())[:5] if len(v) > 1},  # 只显示前5个重复簇
            "task_type_distribution": dict(stats['task_types']),
            "source_distribution": dict(stats['sources']),
            "license_distribution": dict(stats['licenses'])
        }
    }

    return metrics


def compare_metrics(original_path, recounted_metrics):
    """比较原始metrics与重新计算的metrics"""
    try:
        with open(original_path, 'r', encoding='utf-8') as f:
            original = json.load(f)
    except FileNotFoundError:
        return "原始metrics.json文件不存在"

    # 比较关键指标
    differences = []

    def compare_values(path, orig_val, new_val):
        if orig_val != new_val:
            differences.append(f"{path}: {orig_val} → {new_val}")

    compare_values("total_samples", original.get('total_samples'), recounted_metrics['total_samples'])
    compare_values("alignment_stats.alignment_ok_count",
                   original.get('alignment_stats', {}).get('alignment_ok_count'),
                   recounted_metrics['alignment_stats']['alignment_ok_count'])
    compare_values("alignment_stats.alignment_error_count",
                   original.get('alignment_stats', {}).get('alignment_error_count'),
                   recounted_metrics['alignment_stats']['alignment_error_count'])
    compare_values("near_duplicates.duplicate_ratio",
                   original.get('near_duplicates', {}).get('duplicate_ratio'),
                   recounted_metrics['near_duplicates']['duplicate_ratio'])
    compare_values("evidence_overlap.mean",
                   original.get('evidence_overlap', {}).get('mean'),
                   recounted_metrics['evidence_overlap']['mean'])

    return differences if differences else ["✅ 所有关键指标一致"]


def main():
    """主函数"""
    print("🔍 Stage 2 质量指标复算 - 开始执行")
    print("=" * 60)

    # 数据目录
    data_dir = Path("data/processed/active_qa_v1")

    # 查找所有JSONL文件
    jsonl_files = list(data_dir.glob("*.jsonl"))
    print(f"📁 发现 {len(jsonl_files)} 个JSONL文件: {[f.name for f in jsonl_files]}")

    # 加载所有样本
    all_samples = []
    for jsonl_file in jsonl_files:
        print(f"📖 加载 {jsonl_file.name}...")
        samples = load_jsonl_file(jsonl_file)
        all_samples.extend(samples)
        print(f"   加载了 {len(samples)} 个样本")

    print(f"📊 总共加载了 {len(all_samples)} 个样本")

    # 分析样本
    print("🔬 开始分析样本...")
    stats = analyze_samples(all_samples)

    # 生成重新计算的指标
    print("📈 生成重新计算的指标...")
    recounted_metrics = generate_recounted_metrics(stats)

    # 保存重新计算的指标
    output_path = data_dir / "metrics.recount.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(recounted_metrics, f, indent=2, ensure_ascii=False)
    print(f"💾 保存重新计算的指标到 {output_path}")

    # 比较与原始指标
    print("⚖️ 比较与原始指标...")
    original_metrics_path = data_dir / "metrics.json"
    differences = compare_metrics(original_metrics_path, recounted_metrics)

    # 保存差异报告
    diff_report_path = data_dir / "metrics.diff.txt"
    with open(diff_report_path, 'w', encoding='utf-8') as f:
        f.write("质量指标复算差异报告\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"复算时间: {datetime.now().isoformat()}\n")
        f.write(f"原始文件: {original_metrics_path}\n")
        f.write(f"复算文件: {output_path}\n\n")
        f.write("关键指标差异:\n")
        for diff in differences:
            f.write(f"- {diff}\n")
    print(f"📋 保存差异报告到 {diff_report_path}")

    # 输出统计摘要
    print("\n" + "=" * 60)
    print("📊 复算结果摘要:")
    print(f"  总样本数: {recounted_metrics['total_samples']}")
    print(f"  对齐正确: {recounted_metrics['alignment_stats']['alignment_ok_count']}")
    print(f"  对齐错误: {recounted_metrics['alignment_stats']['alignment_error_count']}")
    print(".2f")
    print(f"  去重比例: {recounted_metrics['near_duplicates']['duplicate_ratio']:.4f}")
    print(f"  证据重叠均值: {recounted_metrics['evidence_overlap']['mean']:.3f}")
    print(f"  许可错误数: {len(recounted_metrics['license_whitelist_errors'])}")

    if differences and differences[0] != "✅ 所有关键指标一致":
        print("\n⚠️ 发现指标差异，请检查差异报告!")
        print(f"   差异报告: {diff_report_path}")
    else:
        print("\n✅ 复算完成，所有关键指标一致!")

    print("=" * 60)


if __name__ == "__main__":
    main()
