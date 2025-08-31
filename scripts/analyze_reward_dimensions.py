#!/usr/bin/env python3
"""
奖励维度诊断面板 - 快速识别相关性问题
"""

import json
import os
import sys
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import spearmanr, pearsonr

def load_manifest(manifest_path):
    """加载manifest文件"""
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    samples = []
    with open(manifest_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples

def analyze_dimensions(samples):
    """分析奖励维度的统计特性"""
    analysis = {
        "overview": {
            "total_samples": len(samples),
            "dimensions": ["rules_score", "logic_rigor", "question_quality", "reasoning_completeness", "natural_interaction"]
        },
        "statistics": {},
        "correlations": {},
        "diagnostics": {}
    }

    # 收集所有评分数据
    data = []
    for sample in samples:
        if "evaluation" in sample:
            eval_data = sample["evaluation"]
            if "primary_reward" in eval_data and "hard_rules" in eval_data:
                row = {
                    "primary_reward": eval_data["primary_reward"],
                    "rules_score": eval_data["hard_rules"]["rules_score"],
                    "logic_rigor": eval_data["component_scores"].get("logic_rigor", 0),
                    "question_quality": eval_data["component_scores"].get("question_quality", 0),
                    "reasoning_completeness": eval_data["component_scores"].get("reasoning_completeness", 0),
                    "natural_interaction": eval_data["component_scores"].get("natural_interaction", 0),
                    "task_type": sample.get("task_type", "unknown"),
                    "rules_gate_triggered": eval_data.get("meta", {}).get("rules_gate_triggered", False)
                }
                data.append(row)

    if not data:
        analysis["diagnostics"]["error"] = "No evaluation data found in samples"
        return analysis

    df = pd.DataFrame(data)

    # 基础统计
    for dim in analysis["overview"]["dimensions"]:
        if dim in df.columns:
            stats = {
                "count": int(df[dim].count()),
                "mean": float(df[dim].mean()),
                "std": float(df[dim].std()),
                "min": float(df[dim].min()),
                "max": float(df[dim].max()),
                "variance": float(df[dim].var()),
                "constant_check": df[dim].std() < 1e-6
            }
            analysis["statistics"][dim] = stats

            # 诊断常量维度
            if stats["constant_check"]:
                analysis["diagnostics"][f"{dim}_constant"] = f"Variance < 1e-6, likely constant in training set"

    # 相关性分析
    target = "primary_reward"
    if target in df.columns:
        correlations = {}
        for dim in analysis["overview"]["dimensions"]:
            if dim in df.columns and df[dim].std() > 1e-6:
                spearman_corr, spearman_p = spearmanr(df[target], df[dim])
                pearson_corr, pearson_p = pearsonr(df[target], df[dim])

                correlations[dim] = {
                    "spearman": float(spearman_corr),
                    "spearman_p": float(spearman_p),
                    "pearson": float(pearson_corr),
                    "pearson_p": float(pearson_p)
                }

        analysis["correlations"] = correlations

        # 维度间相关性矩阵
        dim_corr_matrix = {}
        dims = [d for d in analysis["overview"]["dimensions"] if d in df.columns]
        for i, dim1 in enumerate(dims):
            dim_corr_matrix[dim1] = {}
            for dim2 in dims:
                if df[dim1].std() > 1e-6 and df[dim2].std() > 1e-6:
                    corr, _ = spearmanr(df[dim1], df[dim2])
                    dim_corr_matrix[dim1][dim2] = float(corr)
                else:
                    dim_corr_matrix[dim1][dim2] = 0.0

        analysis["dimension_correlations"] = dim_corr_matrix

        # 按任务类型分组分析
        if "task_type" in df.columns:
            task_analysis = {}
            for task_type in df["task_type"].unique():
                task_df = df[df["task_type"] == task_type]
                if len(task_df) > 5:  # 至少5个样本才分析
                    task_corr = {}
                    for dim in dims:
                        if dim in task_df.columns and task_df[dim].std() > 1e-6:
                            corr, _ = spearmanr(task_df[target], task_df[dim])
                            task_corr[dim] = float(corr)

                    task_analysis[task_type] = {
                        "count": len(task_df),
                        "correlations": task_corr,
                        "mean_reward": float(task_df[target].mean())
                    }

            analysis["task_analysis"] = task_analysis

    # 门控统计
    if "rules_gate_triggered" in df.columns:
        gate_stats = {
            "total_samples": len(df),
            "gate_triggered_count": int(df["rules_gate_triggered"].sum()),
            "gate_triggered_rate": float(df["rules_gate_triggered"].mean())
        }
        analysis["gate_statistics"] = gate_stats

    return analysis

def main():
    parser = argparse.ArgumentParser(description="奖励维度诊断面板")
    parser.add_argument("--manifest", required=True, help="包含评估结果的manifest文件")
    parser.add_argument("--out-json", default="artifacts/reward_diag.json", help="JSON输出文件")
    parser.add_argument("--out-csv", default="artifacts/reward_diag.csv", help="CSV输出文件")

    args = parser.parse_args()

    # 加载数据
    print(f"加载manifest: {args.manifest}")
    samples = load_manifest(args.manifest)
    print(f"找到 {len(samples)} 个样本")

    # 分析维度
    print("分析奖励维度...")
    analysis = analyze_dimensions(samples)

    # 输出JSON
    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    # 输出CSV (简化版)
    if analysis.get("statistics"):
        csv_data = []
        for dim, stats in analysis["statistics"].items():
            row = {"dimension": dim, **stats}
            if "correlations" in analysis and dim in analysis["correlations"]:
                row.update(analysis["correlations"][dim])
            csv_data.append(row)

        if csv_data:
            csv_df = pd.DataFrame(csv_data)
            os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
            csv_df.to_csv(args.out_csv, index=False)

    print(f"分析完成!")
    print(f"JSON报告: {args.out_json}")
    print(f"CSV报告: {args.out_csv}")

    # 关键诊断输出
    if "diagnostics" in analysis and analysis["diagnostics"]:
        print("\n🚨 关键诊断:")
        for diag, msg in analysis["diagnostics"].items():
            print(f"  - {diag}: {msg}")

if __name__ == "__main__":
    main()
