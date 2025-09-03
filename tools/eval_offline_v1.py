#!/usr/bin/env python3
"""
离线评测v1：结构完整性评估
对数据集进行无外部LLM的结构质量评估

评估指标：
1. 结构完整率：字段完备性
2. clarification覆盖率：澄清问句的有效性
3. branch一致性：问句与答案的对应关系
4. 冗余率：重复问句比例
5. 长度/回合控制：文本长度分布

输出：metrics_eval_v1.json
"""

import json
import argparse
from collections import defaultdict, Counter
from pathlib import Path
import re
from typing import Dict, List, Any


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


def evaluate_structural_completeness(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """评估结构完整率"""
    required_fields = ['uid', 'user_query', 'clarification_questions',
                      'assistant_response', 'task_type', 'source', 'licensing']

    completeness_stats = defaultdict(int)
    total_samples = len(samples)

    for sample in samples:
        for field in required_fields:
            if field in sample and sample[field]:
                completeness_stats[field] += 1

    # 计算完整率
    completeness_rates = {}
    for field, count in completeness_stats.items():
        completeness_rates[field] = {
            'count': count,
            'rate': count / total_samples if total_samples > 0 else 0
        }

    # 总体完整率（所有字段都完整的样本比例）
    fully_complete = sum(1 for sample in samples
                        if all(field in sample and sample[field] for field in required_fields))
    completeness_rates['overall'] = {
        'count': fully_complete,
        'rate': fully_complete / total_samples if total_samples > 0 else 0
    }

    return completeness_rates


def evaluate_clarification_coverage(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """评估clarification覆盖率"""
    coverage_stats = {
        'total_samples': len(samples),
        'with_clarifications': 0,
        'empty_clarifications': 0,
        'clarification_lengths': [],
        'clarification_word_counts': []
    }

    for sample in samples:
        questions = sample.get('clarification_questions', [])

        if questions:
            coverage_stats['with_clarifications'] += 1
            coverage_stats['clarification_lengths'].append(len(questions))

            # 计算总词数
            total_words = 0
            for q in questions:
                if isinstance(q, str):
                    words = re.findall(r'\b\w+\b', q)
                    total_words += len(words)
            coverage_stats['clarification_word_counts'].append(total_words)
        else:
            coverage_stats['empty_clarifications'] += 1

    # 计算统计
    lengths = coverage_stats['clarification_lengths']
    word_counts = coverage_stats['clarification_word_counts']

    coverage_stats['avg_clarification_count'] = sum(lengths) / len(lengths) if lengths else 0
    coverage_stats['avg_word_count'] = sum(word_counts) / len(word_counts) if word_counts else 0
    coverage_stats['coverage_rate'] = coverage_stats['with_clarifications'] / coverage_stats['total_samples']

    return coverage_stats


def evaluate_branch_consistency(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """评估branch一致性（问句与答案的对应关系）"""
    consistency_stats = {
        'total_samples': len(samples),
        'consistent_samples': 0,
        'inconsistent_samples': 0,
        'consistency_errors': []
    }

    for i, sample in enumerate(samples):
        questions = sample.get('clarification_questions', [])
        response = sample.get('assistant_response', '')

        if not questions or not response:
            continue

        # 提取response中的枚举答案数量
        answer_pattern = r'若问题\d+则答案：'
        enumerated_answers = re.findall(answer_pattern, response)

        is_consistent = len(questions) == len(enumerated_answers)

        if is_consistent:
            consistency_stats['consistent_samples'] += 1
        else:
            consistency_stats['inconsistent_samples'] += 1
            consistency_stats['consistency_errors'].append({
                'index': i,
                'uid': sample.get('uid', 'unknown'),
                'question_count': len(questions),
                'answer_count': len(enumerated_answers)
            })

    total_valid = consistency_stats['consistent_samples'] + consistency_stats['inconsistent_samples']
    consistency_stats['consistency_rate'] = (consistency_stats['consistent_samples'] / total_valid
                                           if total_valid > 0 else 0)

    return consistency_stats


def evaluate_redundancy(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """评估冗余率"""
    redundancy_stats = {
        'total_questions': 0,
        'unique_questions': set(),
        'duplicate_questions': defaultdict(int)
    }

    for sample in samples:
        questions = sample.get('clarification_questions', [])
        for q in questions:
            if isinstance(q, str):
                redundancy_stats['total_questions'] += 1
                redundancy_stats['unique_questions'].add(q.lower().strip())

    unique_count = len(redundancy_stats['unique_questions'])
    total_count = redundancy_stats['total_questions']

    redundancy_stats['redundancy_rate'] = 1 - (unique_count / total_count) if total_count > 0 else 0
    redundancy_stats['unique_count'] = unique_count

    return redundancy_stats


def evaluate_length_control(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """评估长度/回合控制"""
    length_stats = {
        'query_lengths': [],
        'response_lengths': [],
        'question_lengths': []
    }

    for sample in samples:
        # 查询长度
        query = sample.get('user_query', '')
        if query:
            length_stats['query_lengths'].append(len(query))

        # 响应长度
        response = sample.get('assistant_response', '')
        if response:
            length_stats['response_lengths'].append(len(response))

        # 问题长度
        questions = sample.get('clarification_questions', [])
        for q in questions:
            if isinstance(q, str):
                length_stats['question_lengths'].append(len(q))

    # 计算统计量
    stats_keys = list(length_stats.keys())  # 创建副本避免修改时迭代
    for key in stats_keys:
        values = length_stats[key]
        if values:
            sorted_values = sorted(values)
            length_stats[f'{key}_stats'] = {
                'count': len(values),
                'mean': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'p50': sorted_values[len(values) // 2],
                'p90': sorted_values[int(len(values) * 0.9)]
            }
        else:
            length_stats[f'{key}_stats'] = {'count': 0}

    return length_stats


def generate_evaluation_report(results: Dict[str, Any]) -> Dict[str, Any]:
    """生成综合评估报告"""
    report = {
        'timestamp': json.dumps(None),  # 稍后设置
        'dataset_info': {
            'total_samples': results['structural_completeness']['overall']['count'],
            'evaluation_scope': 'offline_structural'
        },
        'metrics': {},  # 将在下面填充
        'recommendations': []
    }

    # 结构完整率
    completeness = results['structural_completeness']
    report['metrics']['structural_completeness'] = {
        'overall_rate': completeness['overall']['rate'],
        'field_rates': {k: v['rate'] for k, v in completeness.items() if k != 'overall'}
    }

    # clarification覆盖率
    coverage = results['clarification_coverage']
    report['metrics']['clarification_coverage'] = {
        'coverage_rate': coverage['coverage_rate'],
        'avg_clarification_count': coverage['avg_clarification_count'],
        'avg_word_count': coverage['avg_word_count']
    }

    # branch一致性
    consistency = results['branch_consistency']
    report['metrics']['branch_consistency'] = {
        'consistency_rate': consistency['consistency_rate'],
        'consistent_samples': consistency['consistent_samples'],
        'inconsistent_samples': consistency['inconsistent_samples']
    }

    # 冗余率
    redundancy = results['redundancy']
    report['metrics']['redundancy'] = {
        'redundancy_rate': redundancy['redundancy_rate'],
        'unique_questions': redundancy['unique_count'],
        'total_questions': redundancy['total_questions']
    }

    # 长度控制
    length = results['length_control']
    report['metrics']['length_control'] = {
        'query_stats': length.get('query_lengths_stats', {}),
        'response_stats': length.get('response_lengths_stats', {}),
        'question_stats': length.get('question_lengths_stats', {})
    }

    # 生成建议
    if completeness['overall']['rate'] < 0.95:
        report['recommendations'].append("结构完整率较低，建议检查数据生成流程")

    if coverage['coverage_rate'] < 0.8:
        report['recommendations'].append("clarification覆盖率不足，建议增强澄清问句生成")

    if consistency['consistency_rate'] < 0.9:
        report['recommendations'].append("branch一致性问题严重，建议修复问答对应关系")

    if redundancy['redundancy_rate'] > 0.3:
        report['recommendations'].append("冗余率较高，建议去重优化")

    return report


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='离线评测v1：结构完整性评估')
    parser.add_argument('--input', '-i', required=True, help='输入JSONL文件路径')
    parser.add_argument('--output', '-o', required=True, help='输出JSON文件路径')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')

    args = parser.parse_args()

    print("🔍 Stage 2 离线评测 v1 - 开始执行")
    print("=" * 60)
    print(f"📖 输入文件: {args.input}")
    print(f"💾 输出文件: {args.output}")

    # 加载数据
    print("📖 加载数据...")
    samples = load_jsonl_file(args.input)
    print(f"   加载了 {len(samples)} 个样本")

    if not samples:
        print("❌ 未找到任何样本，退出")
        return

    # 执行各项评估
    print("🔬 执行结构评估...")

    results = {}
    results['structural_completeness'] = evaluate_structural_completeness(samples)
    print("   ✅ 结构完整率评估完成")

    results['clarification_coverage'] = evaluate_clarification_coverage(samples)
    print("   ✅ clarification覆盖率评估完成")

    results['branch_consistency'] = evaluate_branch_consistency(samples)
    print("   ✅ branch一致性评估完成")

    results['redundancy'] = evaluate_redundancy(samples)
    print("   ✅ 冗余率评估完成")

    results['length_control'] = evaluate_length_control(samples)
    print("   ✅ 长度控制评估完成")

    # 生成综合报告
    print("📊 生成综合报告...")
    report = generate_evaluation_report(results)

    # 添加时间戳
    import datetime
    report['timestamp'] = datetime.datetime.now().isoformat()

    # 保存报告
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"💾 报告已保存到: {output_path}")

    # 输出关键指标
    print("\n" + "=" * 60)
    print("📊 关键指标汇总:")

    metrics = report['metrics']
    print(".1%")
    print(".1%")
    print(".1%")
    print(".1%")

    if report['recommendations']:
        print("\n💡 改进建议:")
        for rec in report['recommendations']:
            print(f"   • {rec}")

    print("=" * 60)


if __name__ == "__main__":
    main()
