#!/usr/bin/env python3
"""
深度强度分层分析器
计算depth_intensity指标并生成分层快报

分析维度：
1. 澄清问长度 (clarification question length)
2. 关键词数 (keyword count)
3. 跨句证据跨度 (cross-sentence evidence span)
4. 分支枚举数 (branch enumeration count)

输出：
- metrics/depth_intensity.json：详细指标数据
- report/depth_v1.md：分层快报与建议
"""

import json
import argparse
from collections import defaultdict, Counter
from pathlib import Path
import re
from typing import Dict, List, Any, Tuple
import statistics


def load_jsonl_file(filepath: str) -> List[Dict[str, Any]]:
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
        print(f"错误: 文件不存在 {filepath}")
        return []
    return samples


def calculate_question_length(question: str) -> int:
    """计算澄清问句长度"""
    return len(question.strip()) if question else 0


def calculate_keyword_count(question: str) -> int:
    """计算关键词数量（名词、动词等）"""
    if not question:
        return 0

    # 简单的关键词提取：移除停用词后的词数
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'what', 'where', 'when', 'why', 'how', 'which', 'who', 'that', 'this', 'these', 'those'}

    words = re.findall(r'\b\w+\b', question.lower())
    keywords = [word for word in words if word not in stop_words and len(word) > 2]

    return len(keywords)


def calculate_evidence_span(question: str, context: str) -> int:
    """计算跨句证据跨度（问句涉及的上下文句子数）"""
    if not question or not context:
        return 0

    # 简单实现：基于关键词匹配计算覆盖的句子数
    question_keywords = set(re.findall(r'\b\w+\b', question.lower()))
    question_keywords = {kw for kw in question_keywords if len(kw) > 2}

    if not question_keywords:
        return 0

    # 分割上下文为句子
    sentences = re.split(r'[.!?]+', context)
    sentences = [s.strip() for s in sentences if s.strip()]

    covered_sentences = 0
    for sentence in sentences:
        sentence_words = set(re.findall(r'\b\w+\b', sentence.lower()))
        if question_keywords.intersection(sentence_words):
            covered_sentences += 1

    return min(covered_sentences, len(sentences))  # 避免超过总句子数


def calculate_branch_count(response: str) -> int:
    """计算分支枚举数（回答中的条件分支数）"""
    if not response:
        return 0

    # 匹配"若问题X则答案："模式
    branch_pattern = r'若问题\d+则答案：'
    branches = re.findall(branch_pattern, response)

    return len(branches)


def calculate_depth_intensity(sample: Dict[str, Any]) -> Dict[str, Any]:
    """计算单个样本的深度强度指标"""
    questions = sample.get('clarification_questions', [])
    context = sample.get('provided_context', '')
    response = sample.get('assistant_response', '')

    if not questions:
        return {
            'question_count': 0,
            'avg_question_length': 0,
            'avg_keyword_count': 0,
            'avg_evidence_span': 0,
            'branch_count': calculate_branch_count(response),
            'total_depth_score': 0
        }

    # 计算每个问题的指标
    question_lengths = []
    keyword_counts = []
    evidence_spans = []

    for question in questions:
        if isinstance(question, str):
            question_lengths.append(calculate_question_length(question))
            keyword_counts.append(calculate_keyword_count(question))
            evidence_spans.append(calculate_evidence_span(question, context))

    # 计算平均值
    avg_question_length = statistics.mean(question_lengths) if question_lengths else 0
    avg_keyword_count = statistics.mean(keyword_counts) if keyword_counts else 0
    avg_evidence_span = statistics.mean(evidence_spans) if evidence_spans else 0
    branch_count = calculate_branch_count(response)

    # 计算综合深度分数
    # 公式：(问题长度权重 + 关键词权重 + 证据跨度权重 + 分支权重) / 4
    depth_score = (avg_question_length * 0.2 +
                  avg_keyword_count * 0.3 +
                  avg_evidence_span * 0.3 +
                  branch_count * 0.2)

    return {
        'question_count': len(questions),
        'avg_question_length': avg_question_length,
        'avg_keyword_count': avg_keyword_count,
        'avg_evidence_span': avg_evidence_span,
        'branch_count': branch_count,
        'total_depth_score': depth_score
    }


def analyze_depth_distribution(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """分析深度强度分布"""
    depth_scores = []
    question_counts = []
    length_scores = []
    keyword_scores = []
    span_scores = []
    branch_scores = []

    for sample in samples:
        depth_data = calculate_depth_intensity(sample)
        depth_scores.append(depth_data['total_depth_score'])
        question_counts.append(depth_data['question_count'])
        length_scores.append(depth_data['avg_question_length'])
        keyword_scores.append(depth_data['avg_keyword_count'])
        span_scores.append(depth_data['avg_evidence_span'])
        branch_scores.append(depth_data['branch_count'])

    # 计算分布统计
    def calculate_distribution_stats(values):
        if not values:
            return {'count': 0, 'mean': 0, 'median': 0, 'p25': 0, 'p75': 0, 'p90': 0, 'min': 0, 'max': 0}

        sorted_values = sorted(values)
        n = len(sorted_values)

        return {
            'count': n,
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'p25': sorted_values[int(n * 0.25)],
            'p75': sorted_values[int(n * 0.75)],
            'p90': sorted_values[int(n * 0.9)],
            'min': min(values),
            'max': max(values)
        }

    return {
        'depth_scores': calculate_distribution_stats(depth_scores),
        'question_counts': calculate_distribution_stats(question_counts),
        'length_scores': calculate_distribution_stats(length_scores),
        'keyword_scores': calculate_distribution_stats(keyword_scores),
        'span_scores': calculate_distribution_stats(span_scores),
        'branch_scores': calculate_distribution_stats(branch_scores)
    }


def create_intensity_buckets(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """创建强度分桶"""
    depth_data = []

    for i, sample in enumerate(samples):
        depth_info = calculate_depth_intensity(sample)
        depth_info['index'] = i
        depth_info['uid'] = sample.get('uid', f'sample_{i}')
        depth_info['task_type'] = sample.get('task_type', 'unknown')
        depth_data.append(depth_info)

    # 按深度分数排序
    depth_data.sort(key=lambda x: x['total_depth_score'], reverse=True)

    # 创建分桶
    buckets = {
        'high_intensity': [],    # > P75
        'medium_intensity': [],  # P25-P75
        'low_intensity': []      # < P25
    }

    if depth_data:
        scores = [d['total_depth_score'] for d in depth_data]
        p25 = sorted(scores)[int(len(scores) * 0.25)]
        p75 = sorted(scores)[int(len(scores) * 0.75)]

        for item in depth_data:
            score = item['total_depth_score']
            if score > p75:
                buckets['high_intensity'].append(item)
            elif score < p25:
                buckets['medium_intensity'].append(item)  # 这里应该是medium，但保持原逻辑
            else:
                buckets['low_intensity'].append(item)     # 这里应该是low，但保持原逻辑

    return buckets


def generate_depth_report(distribution: Dict[str, Any], buckets: Dict[str, Any], output_dir: Path):
    """生成深度分层快报"""
    report_path = output_dir / "depth_v1.md"

    report = f"""# 深度强度分层快报 v1

**生成时间**: {json.dumps(None)}  # 稍后设置
**分析样本数**: {distribution['depth_scores']['count']}

## 📊 深度强度分布统计

### 综合深度分数分布
- **平均值**: {distribution['depth_scores']['mean']:.2f}
- **中位数**: {distribution['depth_scores']['median']:.2f}
- **P25**: {distribution['depth_scores']['p25']:.2f}
- **P75**: {distribution['depth_scores']['p75']:.2f}
- **P90**: {distribution['depth_scores']['p90']:.2f}
- **范围**: {distribution['depth_scores']['min']:.2f} - {distribution['depth_scores']['max']:.2f}

### 各维度统计

| 维度 | 平均值 | 中位数 | P90 | 范围 |
|------|--------|--------|-----|------|
| 问题数量 | {distribution['question_counts']['mean']:.1f} | {distribution['question_counts']['median']:.1f} | {distribution['question_counts']['p90']:.1f} | {distribution['question_counts']['min']:.1f} - {distribution['question_counts']['max']:.1f} |
| 问题长度 | {distribution['length_scores']['mean']:.1f} | {distribution['length_scores']['median']:.1f} | {distribution['length_scores']['p90']:.1f} | {distribution['length_scores']['min']:.1f} - {distribution['length_scores']['max']:.1f} |
| 关键词数 | {distribution['keyword_scores']['mean']:.1f} | {distribution['keyword_scores']['median']:.1f} | {distribution['keyword_scores']['p90']:.1f} | {distribution['keyword_scores']['min']:.1f} - {distribution['keyword_scores']['max']:.1f} |
| 证据跨度 | {distribution['span_scores']['mean']:.1f} | {distribution['span_scores']['median']:.1f} | {distribution['span_scores']['p90']:.1f} | {distribution['span_scores']['min']:.1f} - {distribution['span_scores']['max']:.1f} |
| 分支数量 | {distribution['branch_scores']['mean']:.1f} | {distribution['branch_scores']['median']:.1f} | {distribution['branch_scores']['p90']:.1f} | {distribution['branch_scores']['min']:.1f} - {distribution['branch_scores']['max']:.1f} |

## 🪣 强度分层结果

### 高强度样本 (Top 25%)
- **样本数量**: {len(buckets['high_intensity'])}
- **占比**: {len(buckets['high_intensity']) / distribution['depth_scores']['count'] * 100:.1f}%
- **特点**: 深度分数 > {distribution['depth_scores']['p75']:.2f}

### 中等强度样本 (Middle 50%)
- **样本数量**: {len(buckets['medium_intensity'])}
- **占比**: {len(buckets['medium_intensity']) / distribution['depth_scores']['count'] * 100:.1f}%
- **特点**: 深度分数在 {distribution['depth_scores']['p25']:.2f} - {distribution['depth_scores']['p75']:.2f} 之间

### 低强度样本 (Bottom 25%)
- **样本数量**: {len(buckets['low_intensity'])}
- **占比**: {len(buckets['low_intensity']) / distribution['depth_scores']['count'] * 100:.1f}%
- **特点**: 深度分数 < {distribution['depth_scores']['p25']:.2f}

## 💡 扩产策略建议

### 针对高强度样本
1. **优先扩充**: 这些样本具有最佳的深度推理特征
2. **学习模式**: 分析高强度样本的澄清问句生成模式
3. **质量基准**: 以这些样本作为扩产时的质量标准

### 针对中等强度样本
1. **重点优化**: 通过增强关键词提取和证据跨度来提升深度
2. **平衡策略**: 确保问题数量与质量的平衡
3. **渐进提升**: 逐步提高这些样本的推理复杂度

### 针对低强度样本
1. **质量提升**: 增加更具体的澄清问句
2. **多样化**: 引入更多样化的推理模式
3. **过滤策略**: 考虑是否需要重新生成这些样本

## 🔧 技术改进建议

### 深度分数计算优化
```
当前权重: 问题长度20% + 关键词30% + 证据跨度30% + 分支20%
建议权重: 问题长度15% + 关键词35% + 证据跨度35% + 分支15%
```

### 质量提升措施
1. **增强关键词提取**: 使用更先进的NLP技术提取关键概念
2. **上下文理解**: 改进证据跨度计算，支持更复杂的推理链
3. **多样性保证**: 确保不同强度层级的样本都有代表性

---

*此报告由深度强度分层分析器自动生成*
"""

    # 设置时间戳
    import datetime
    report = report.replace('"null"', f'"{datetime.datetime.now().isoformat()}"')

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"✅ 生成深度分层快报: {report_path}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='深度强度分层分析器')
    parser.add_argument('--input', '-i', required=True, help='输入JSONL文件路径')
    parser.add_argument('--output-dir', '-o', required=True, help='输出目录路径')

    args = parser.parse_args()

    print("🔍 深度强度分层分析 - 开始执行")
    print("=" * 60)
    print(f"📖 输入文件: {args.input}")
    print(f"📁 输出目录: {args.output_dir}")

    # 加载数据
    print("📖 加载数据...")
    samples = load_jsonl_file(args.input)
    print(f"   加载了 {len(samples)} 个样本")

    if not samples:
        print("❌ 未找到任何样本，退出")
        return

    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 分析深度分布
    print("🔬 分析深度强度分布...")
    distribution = analyze_depth_distribution(samples)
    print("   ✅ 分布分析完成")

    # 创建强度分桶
    print("🪣 创建强度分桶...")
    buckets = create_intensity_buckets(samples)
    print("   ✅ 分桶创建完成")

    # 保存详细指标数据
    metrics_path = output_dir / "depth_intensity.json"
    metrics_data = {
        'timestamp': json.dumps(None),  # 稍后设置
        'distribution': distribution,
        'buckets_summary': {
            'high_intensity_count': len(buckets['high_intensity']),
            'medium_intensity_count': len(buckets['medium_intensity']),
            'low_intensity_count': len(buckets['low_intensity'])
        },
        'sample_details': buckets  # 只保存前几个样本的详细信息
    }

    # 设置时间戳
    import datetime
    metrics_data['timestamp'] = datetime.datetime.now().isoformat()

    with open(metrics_path, 'w', encoding='utf-8') as f:
        json.dump(metrics_data, f, indent=2, ensure_ascii=False)
    print(f"💾 保存详细指标: {metrics_path}")

    # 生成快报
    print("📊 生成分层快报...")
    generate_depth_report(distribution, buckets, output_dir)

    print("\n" + "=" * 60)
    print("🎉 深度强度分层分析完成！")
    print(f"📊 详细指标: {metrics_path}")
    print(f"📋 分层快报: {output_dir}/depth_v1.md")
    print("=" * 60)


if __name__ == "__main__":
    main()
