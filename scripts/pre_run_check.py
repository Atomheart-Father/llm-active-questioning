#!/usr/bin/env python3
"""
ShadowRun预运行检查 - 解耦开发和CI环境
"""

import json
import os
import sys
import argparse
from pathlib import Path

def load_config():
    """加载项目配置"""
    config_path = Path("configs/default_config.yaml")
    if not config_path.exists():
        return {}

    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"⚠️ 无法加载配置: {e}")
        return {}

def check_structure_quality(data_root="shadow_data"):
    """检查数据结构质量"""
    issues = []

    # 检查基础目录
    required_dirs = ["configs", "reports", "data"]
    for dir_name in required_dirs:
        if not Path(dir_name).exists():
            issues.append(f"缺少必需目录: {dir_name}")

    # 检查配置文件
    config_files = ["configs/default_config.yaml", "configs/weights.json"]
    for config_file in config_files:
        if not Path(config_file).exists():
            issues.append(f"缺少配置文件: {config_file}")

    # 检查数据文件
    shadow_files = list(Path("data").glob("shadow_eval_*.jsonl"))
    if not shadow_files:
        issues.append("未找到shadow评估数据文件")
    else:
        # 检查最新文件
        latest_shadow = max(shadow_files, key=lambda p: p.stat().st_mtime)
        with open(latest_shadow, 'r', encoding='utf-8') as f:
            line_count = sum(1 for _ in f)
        if line_count < 50:
            issues.append(f"Shadow数据样本不足: {line_count} < 50")

    return issues

def check_performance_metrics(strict_mode=False):
    """检查性能指标"""
    issues = []
    warnings = []

    # 检查最新的shadow报告
    shadow_reports = list(Path("reports").glob("shadow_run_*.json"))
    if not shadow_reports:
        issues.append("未找到shadow运行报告")
        return issues, warnings

    latest_report = max(shadow_reports, key=lambda p: p.stat().st_mtime)

    try:
        with open(latest_report, 'r', encoding='utf-8') as f:
            report = json.load(f)

        thresholds = report.get("threshold_checks", {})
        actual = thresholds.get("actual_values", {})

        # 基准阈值
        spearman_min = 0.55
        top10_min = 0.60

        # 严格模式使用更高阈值
        if strict_mode:
            spearman_min = 0.75
            top10_min = 0.70

        spearman = actual.get("stable_spearman", 0)
        top10 = actual.get("top10_overlap", 0)

        if spearman < spearman_min:
            if strict_mode:
                issues.append(f"Spearman相关性不足: {spearman:.3f} < {spearman_min:.3f}")
            else:
                warnings.append(f"Spearman相关性偏低: {spearman:.3f} < {spearman_min:.3f}")
        if top10 < top10_min:
            if strict_mode:
                issues.append(f"Top-10重叠率不足: {top10:.3f} < {top10_min:.3f}")
            else:
                warnings.append(f"Top-10重叠率偏低: {top10:.3f} < {top10_min:.3f}")
        # 检查相关性改进
        corr_improve = actual.get("corr_improve_pct", 0)
        if corr_improve < 10 and strict_mode:
            issues.append(f"相关性改进不足: {corr_improve:.1f}% < 10%")

        print("📊 性能指标检查:")
        print(f"  Spearman相关性: {spearman:.3f}")
        print(f"  Top-10重叠率: {top10:.3f}")
        print(f"  相关性改进: {corr_improve:.1f}%")
    except Exception as e:
        issues.append(f"无法读取报告: {e}")

    return issues, warnings

def main():
    parser = argparse.ArgumentParser(description="ShadowRun预运行检查")
    parser.add_argument("--data-root", default="shadow_data", help="数据根目录")
    parser.add_argument("--strict-metrics", action="store_true", help="启用严格性能门槛 (CI模式)")
    parser.add_argument("--out", help="输出检查结果到JSON文件")

    args = parser.parse_args()

    print("🔍 ShadowRun 预运行检查")
    print("=" * 50)

    results = {
        "mode": "strict" if args.strict_metrics else "development",
        "structure_issues": [],
        "performance_issues": [],
        "performance_warnings": [],
        "overall_status": "unknown"
    }

    # 1. 结构质量检查
    print("1. 检查数据结构质量...")
    structure_issues = check_structure_quality(args.data_root)
    results["structure_issues"] = structure_issues

    if structure_issues:
        for issue in structure_issues:
            print(f"   ❌ {issue}")
    else:
        print("   ✅ 结构检查通过")

    # 2. 性能指标检查
    print("\n2. 检查性能指标...")
    perf_issues, perf_warnings = check_performance_metrics(args.strict_metrics)
    results["performance_issues"] = perf_issues
    results["performance_warnings"] = perf_warnings

    if perf_issues:
        for issue in perf_issues:
            print(f"   ❌ {issue}")
    else:
        print("   ✅ 性能检查通过")

    if perf_warnings:
        for warning in perf_warnings:
            print(f"   ⚠️  {warning}")

    # 3. 确定整体状态
    if structure_issues:
        results["overall_status"] = "fail"
        exit_code = 1
    elif perf_issues:
        results["overall_status"] = "fail"
        exit_code = 1
    elif perf_warnings and args.strict_metrics:
        results["overall_status"] = "fail"
        exit_code = 1
    else:
        results["overall_status"] = "pass"
        exit_code = 0

    print(f"\n📋 整体状态: {results['overall_status'].upper()}")

    # 保存结果
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"💾 结果已保存到: {args.out}")

    sys.exit(exit_code)

if __name__ == "__main__":
    main()