#!/usr/bin/env python3
"""
数据切分校验脚本
验证train/dev/test数据集的无交叉泄漏

功能：
1. 检查三个数据集之间是否有UID重复
2. 验证切分比例是否符合预期 (80/10/10)
3. 检查每个数据集的样本完整性
4. 输出冲突报告和统计摘要

输出：
- 控制台报告：校验结果
- conflicts.json：发现的重复UID详情
- split_stats.json：切分统计信息
"""

import json
import os
from collections import defaultdict
from pathlib import Path


def load_uids_from_jsonl(filepath):
    """从JSONL文件中提取所有UID"""
    uids = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        sample = json.loads(line)
                        uid = sample.get('uid')
                        if uid:
                            uids.append(uid)
                        else:
                            print(f"警告: {filepath}:{line_num} 缺少UID")
                    except json.JSONDecodeError as e:
                        print(f"错误: {filepath}:{line_num} JSON解析失败: {e}")
    except FileNotFoundError:
        print(f"错误: 文件不存在 {filepath}")
        return []
    except Exception as e:
        print(f"错误: 读取文件 {filepath} 时发生异常: {e}")
        return []

    return uids


def find_uid_conflicts(train_uids, dev_uids, test_uids):
    """查找三个数据集之间的UID冲突"""
    conflicts = {
        'train_dev': [],
        'train_test': [],
        'dev_test': [],
        'all_sets': []
    }

    # 创建UID到数据集的映射
    uid_to_datasets = defaultdict(list)

    for uid in train_uids:
        uid_to_datasets[uid].append('train')
    for uid in dev_uids:
        uid_to_datasets[uid].append('dev')
    for uid in test_uids:
        uid_to_datasets[uid].append('test')

    # 查找冲突
    for uid, datasets in uid_to_datasets.items():
        if len(datasets) > 1:
            # 记录具体冲突
            if 'train' in datasets and 'dev' in datasets:
                conflicts['train_dev'].append(uid)
            if 'train' in datasets and 'test' in datasets:
                conflicts['train_test'].append(uid)
            if 'dev' in datasets and 'test' in datasets:
                conflicts['dev_test'].append(uid)
            if len(datasets) == 3:
                conflicts['all_sets'].append(uid)

    return conflicts, uid_to_datasets


def calculate_split_stats(train_uids, dev_uids, test_uids):
    """计算切分统计信息"""
    total_samples = len(train_uids) + len(dev_uids) + len(test_uids)

    stats = {
        'total_samples': total_samples,
        'train': {
            'count': len(train_uids),
            'percentage': len(train_uids) / total_samples * 100 if total_samples > 0 else 0
        },
        'dev': {
            'count': len(dev_uids),
            'percentage': len(dev_uids) / total_samples * 100 if total_samples > 0 else 0
        },
        'test': {
            'count': len(test_uids),
            'percentage': len(test_uids) / total_samples * 100 if total_samples > 0 else 0
        },
        'expected_distribution': {
            'train': 80.0,
            'dev': 10.0,
            'test': 10.0
        }
    }

    # 计算偏差
    stats['deviations'] = {
        'train': stats['train']['percentage'] - stats['expected_distribution']['train'],
        'dev': stats['dev']['percentage'] - stats['expected_distribution']['dev'],
        'test': stats['test']['percentage'] - stats['expected_distribution']['test']
    }

    return stats


def validate_split_quality(stats):
    """验证切分质量"""
    issues = []

    # 检查比例偏差 (允许1%的误差)
    tolerance = 1.0
    for split_name in ['train', 'dev', 'test']:
        deviation = abs(stats['deviations'][split_name])
        if deviation > tolerance:
            issues.append({
                'type': 'ratio_deviation',
                'split': split_name,
                'expected': stats['expected_distribution'][split_name],
                'actual': stats[split_name]['percentage'],
                'deviation': deviation,
                'status': 'warning' if deviation <= 5.0 else 'error'
            })

    # 检查样本数量合理性
    if stats['total_samples'] == 0:
        issues.append({
            'type': 'no_samples',
            'message': '没有找到任何样本',
            'status': 'error'
        })

    for split_name in ['train', 'dev', 'test']:
        if stats[split_name]['count'] == 0:
            issues.append({
                'type': 'empty_split',
                'split': split_name,
                'message': f'{split_name}数据集为空',
                'status': 'error'
            })

    return issues


def main():
    """主函数"""
    print("🔍 Stage 2 数据切分校验 - 开始执行")
    print("=" * 60)

    # 数据文件路径
    data_dir = Path("data/processed/active_qa_v1")
    train_file = data_dir / "train.jsonl"
    dev_file = data_dir / "dev.jsonl"
    test_file = data_dir / "test.jsonl"

    # 加载UID
    print("📖 加载训练集UID...")
    train_uids = load_uids_from_jsonl(train_file)

    print("📖 加载验证集UID...")
    dev_uids = load_uids_from_jsonl(dev_file)

    print("📖 加载测试集UID...")
    test_uids = load_uids_from_jsonl(test_file)

    # 查找冲突
    print("🔍 查找UID冲突...")
    conflicts, uid_to_datasets = find_uid_conflicts(train_uids, dev_uids, test_uids)

    # 计算统计
    print("📊 计算切分统计...")
    stats = calculate_split_stats(train_uids, dev_uids, test_uids)

    # 验证质量
    print("✅ 验证切分质量...")
    quality_issues = validate_split_quality(stats)

    # 输出结果
    print("\n" + "=" * 60)
    print("📋 校验结果报告:")

    print("\n🔢 数据集规模:")
    print(f"  训练集: {stats['train']['count']} 样本 ({stats['train']['percentage']:.1f}%)")
    print(f"  验证集: {stats['dev']['count']} 样本 ({stats['dev']['percentage']:.1f}%)")
    print(f"  测试集: {stats['test']['count']} 样本 ({stats['test']['percentage']:.1f}%)")
    print(f"  总计: {stats['total_samples']} 样本")

    print("\n📊 期望分布:")
    print("  训练集: 80.0%")
    print("  验证集: 10.0%")
    print("  测试集: 10.0%")

    print("\n⚖️ 分布偏差:")
    for split_name in ['train', 'dev', 'test']:
        deviation = stats['deviations'][split_name]
        status = "✅" if abs(deviation) <= 1.0 else "⚠️" if abs(deviation) <= 5.0 else "❌"
        print(f"  {split_name}: {deviation:+.1f}% {status}")
    # 冲突检查
    total_conflicts = sum(len(conflicts[key]) for key in conflicts if key != 'all_sets')

    print("\n🔍 UID冲突检查:")
    print(f"  训练集-验证集重叠: {len(conflicts['train_dev'])}")
    print(f"  训练集-测试集重叠: {len(conflicts['train_test'])}")
    print(f"  验证集-测试集重叠: {len(conflicts['dev_test'])}")
    print(f"  三集都重叠: {len(conflicts['all_sets'])}")
    print(f"  总冲突数: {total_conflicts}")

    # 质量问题
    if quality_issues:
        print("\n⚠️ 质量问题:")
        for issue in quality_issues:
            status_icon = "❌" if issue['status'] == 'error' else "⚠️"
            print(f"  {status_icon} {issue.get('message', issue['type'])}")
    else:
        print("\n✅ 无质量问题")

    # 保存冲突详情
    conflicts_output = {
        'summary': {
            'total_conflicts': total_conflicts,
            'train_dev_conflicts': len(conflicts['train_dev']),
            'train_test_conflicts': len(conflicts['train_test']),
            'dev_test_conflicts': len(conflicts['dev_test']),
            'all_sets_conflicts': len(conflicts['all_sets'])
        },
        'details': conflicts,
        'stats': stats,
        'quality_issues': quality_issues
    }

    conflicts_file = data_dir / "split_conflicts.json"
    with open(conflicts_file, 'w', encoding='utf-8') as f:
        json.dump(conflicts_output, f, indent=2, ensure_ascii=False)
    print(f"\n💾 保存冲突报告到: {conflicts_file}")

    # 保存统计信息
    stats_file = data_dir / "split_stats.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"💾 保存统计信息到: {stats_file}")

    # 退出状态
    has_errors = any(issue['status'] == 'error' for issue in quality_issues) or total_conflicts > 0

    print("\n" + "=" * 60)
    if has_errors:
        print("❌ 校验失败！发现数据泄漏或质量问题。")
        print("请检查上述问题并修复后重新运行。")
        exit(1)
    else:
        print("✅ 校验通过！数据集切分质量良好，无泄漏风险。")
        exit(0)


if __name__ == "__main__":
    main()
