#!/usr/bin/env python3
"""
Stage 2 Guard Check Metrics - 守护校验脚本
用于校验metrics.json的统计自洽性
"""

import json
import sys
from pathlib import Path

def load_metrics():
    """加载metrics.json文件"""
    metrics_path = Path("data/processed/active_qa_v1/metrics.json")
    if not metrics_path.exists():
        print(f"❌ 错误: metrics.json文件不存在: {metrics_path}")
        return None

    with open(metrics_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def validate_total_samples(metrics):
    """校验总样本数与分片求和一致"""
    by_shard = metrics.get('by_shard', {})
    total_from_shards = sum(shard_info.get('total_samples', 0) for shard_info in by_shard.values())
    total_in_metrics = metrics.get('total_samples', 0)

    if total_from_shards != total_in_metrics:
        print("❌ 错误: 总样本数不一致")
        print(f"  分片求和: {total_from_shards}")
        print(f"  指标总计: {total_in_metrics}")
        return False
    else:
        print(f"✅ 总样本数校验通过: {total_in_metrics}")
        return True

def validate_alignment_stats(metrics):
    """校验对齐统计的准确性"""
    by_shard = metrics.get('by_shard', {})
    alignment_stats = metrics.get('alignment_stats', {})

    # 计算累计对齐统计
    total_samples = 0
    total_alignment_ok = 0
    total_alignment_errors = 0

    for shard_name, shard_info in by_shard.items():
        shard_total = shard_info.get('total_samples', 0)
        shard_ok = shard_info.get('alignment_ok_count', 0)

        total_samples += shard_total
        total_alignment_ok += shard_ok
        total_alignment_errors += shard_total - shard_ok

    # 校验累计统计
    if total_alignment_errors != alignment_stats.get('alignment_error_count', -1):
        print("❌ 错误: 对齐错误计数不一致")
        print(f"  分片计算错误数: {total_alignment_errors}")
        print(f"  指标错误数: {alignment_stats.get('alignment_error_count', -1)}")
        return False

    if total_alignment_ok != alignment_stats.get('alignment_ok_count', -1):
        print("❌ 错误: 对齐正确计数不一致")
        print(f"  分片计算正确数: {total_alignment_ok}")
        print(f"  指标正确数: {alignment_stats.get('alignment_ok_count', -1)}")
        return False

    # 校验百分比
    expected_percentage = (total_alignment_ok / total_samples * 100) if total_samples > 0 else 0
    actual_percentage = alignment_stats.get('alignment_ok_percentage', -1)

    if abs(expected_percentage - actual_percentage) > 0.01:  # 允许0.01的误差
        print("❌ 错误: 对齐准确率百分比不一致")
        print(f"  分片计算百分比: {expected_percentage:.6f}%")
        print(f"  指标百分比: {actual_percentage:.6f}%")
        return False

    print("✅ 对齐统计校验通过:")
    print(f"  总样本: {total_samples}")
    print(f"  对齐正确: {total_alignment_ok}")
    print(f"  对齐错误: {total_alignment_errors}")
    print(".6f")
    return True

def validate_license_compliance(metrics):
    """校验许可合规性"""
    by_shard = metrics.get('by_shard', {})
    license_whitelist = {'cc-by-sa-3.0', 'cc-by-sa-4.0', 'mit', 'apache-2.0'}
    license_errors = metrics.get('license_whitelist_errors', [])

    found_errors = []
    for shard_name, shard_info in by_shard.items():
        license_type = shard_info.get('licensing', '')
        if license_type not in license_whitelist:
            found_errors.append(f"{shard_name}: {license_type}")

    if found_errors:
        print("❌ 错误: 发现许可不符合白名单的分片:")
        for error in found_errors:
            print(f"  {error}")
        return False

    print("✅ 许可白名单校验通过")
    return True

def validate_shard_completeness(metrics):
    """校验分片信息的完整性"""
    by_shard = metrics.get('by_shard', {})
    required_fields = ['total_samples', 'alignment_ok_count', 'licensing']

    missing_fields = []
    for shard_name, shard_info in by_shard.items():
        for field in required_fields:
            if field not in shard_info:
                missing_fields.append(f"{shard_name}.{field}")

    if missing_fields:
        print("❌ 错误: 分片信息不完整，缺少字段:")
        for field in missing_fields:
            print(f"  {field}")
        return False

    print("✅ 分片信息完整性校验通过")
    return True

def main():
    """主函数"""
    print("🔍 Stage 2 守护校验 - 开始执行")
    print("=" * 50)

    # 加载metrics
    metrics = load_metrics()
    if not metrics:
        return 1

    print(f"📊 校验指标文件: {metrics['timestamp'] if 'timestamp' in metrics else '未知时间'}")
    print()

    # 执行各项校验
    checks = [
        ("总样本数自洽性", validate_total_samples),
        ("对齐统计准确性", validate_alignment_stats),
        ("许可合规性", validate_license_compliance),
        ("分片信息完整性", validate_shard_completeness),
    ]

    all_passed = True
    for check_name, check_func in checks:
        print(f"🔍 检查: {check_name}")
        if not check_func(metrics):
            all_passed = False
        print()

    # 输出最终结果
    print("=" * 50)
    if all_passed:
        print("🎉 所有守护校验通过！")
        print("✅ metrics.json统计自洽，可以安全使用")
        return 0
    else:
        print("❌ 发现统计不一致问题，需要立即修正")
        print("💡 建议：运行指标重算脚本或手动修正metrics.json")
        return 1

if __name__ == "__main__":
    sys.exit(main())
