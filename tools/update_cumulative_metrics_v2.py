#!/usr/bin/env python3
"""
临时脚本：更新累积metrics，正式纳入shard-005
"""

import json
from pathlib import Path

def update_cumulative_metrics_v2():
    """更新累积metrics文件，加入shard-005"""

    # 读取当前累积metrics
    cumulative_file = "data/processed/active_qa_v1/metrics.json"
    with open(cumulative_file, 'r', encoding='utf-8') as f:
        cumulative = json.load(f)

    # 读取shard-005的metrics
    shard_file = "data/processed/active_qa_v1/metrics_shard_005.json"
    with open(shard_file, 'r', encoding='utf-8') as f:
        shard_metrics = json.load(f)

    print("=== 更新累积Metrics v2 (加入shard-005) ===")
    print(f"当前累积样本: {cumulative['total_samples']}")
    print(f"shard-005样本: {shard_metrics['total_samples']}")
    print(f"shard-005对齐错误: {shard_metrics['clarification_questions']['alignment_errors']}")
    print(f"shard-005证据关联度: {shard_metrics['evidence_overlap']['mean']:.3f}")

    # 更新总样本数
    old_total = cumulative['total_samples']
    new_total = old_total + shard_metrics['total_samples']

    # 更新对齐统计
    old_errors = cumulative['alignment_stats']['alignment_error_count']
    new_errors = old_errors + shard_metrics['clarification_questions']['alignment_errors']

    # 更新准确率
    new_ok_count = new_total - new_errors
    new_accuracy = (new_ok_count / new_total) * 100

    print(f"\\n更新详情:")
    print(f"  总样本: {old_total} -> {new_total}")
    print(f"  对齐错误: {old_errors} -> {new_errors}")
    print(f"  对齐准确率: {cumulative['alignment_stats']['alignment_ok_percentage']:.2f}% -> {new_accuracy:.2f}%")

    # 更新cumulative数据
    cumulative['timestamp'] = "2025-09-02T22:00:00.000000"  # 更新时间戳
    cumulative['total_samples'] = new_total
    cumulative['alignment_stats']['alignment_ok_count'] = new_ok_count
    cumulative['alignment_stats']['alignment_error_count'] = new_errors
    cumulative['alignment_stats']['alignment_ok_percentage'] = new_accuracy
    cumulative['shards']['shard-005'] = shard_metrics['total_samples']

    # 更新证据关联度统计
    if 'evidence_overlap' not in cumulative:
        cumulative['evidence_overlap'] = {
            'mean': shard_metrics['evidence_overlap']['mean'],
            'count': shard_metrics['evidence_overlap']['count']
        }
        new_mean = shard_metrics['evidence_overlap']['mean']
        new_count = shard_metrics['evidence_overlap']['count']
    else:
        # 计算新的平均值
        old_count = cumulative['evidence_overlap']['count']
        old_mean = cumulative['evidence_overlap']['mean']
        new_count = old_count + shard_metrics['evidence_overlap']['count']
        new_mean = (old_mean * old_count + shard_metrics['evidence_overlap']['mean'] * shard_metrics['evidence_overlap']['count']) / new_count

        cumulative['evidence_overlap']['mean'] = new_mean
        cumulative['evidence_overlap']['count'] = new_count

    print(f"  证据关联度均值: {new_mean:.3f} (基于{new_count}个样本)")

    # 保存更新后的文件
    with open(cumulative_file, 'w', encoding='utf-8') as f:
        json.dump(cumulative, f, indent=2, ensure_ascii=False)

    print(f"\\n✅ 累积metrics已更新并保存到 {cumulative_file}")
    print("🎯 #S2-04f 任务完成：shard-005已正式纳入有效集")

if __name__ == "__main__":
    update_cumulative_metrics_v2()
