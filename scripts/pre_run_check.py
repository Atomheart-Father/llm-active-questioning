#!/usr/bin/env python3
"""
预跑检查脚本 - RC1影子评估阈值验证
"""

import argparse
import json
import sys
import os
import numpy as np
from pathlib import Path

# 在文件顶部或合适位置加入：
def assert_distribution_health(scores, std_min=0.08, iqr_min=0.12):
  arr=np.array([float(s) for s in scores], dtype=float)
  std=float(arr.std())
  q75,q25=np.percentile(arr,75),np.percentile(arr,25)
  iqr=float(q75-q25)
  assert std>=std_min and iqr>=iqr_min, f"score distribution too narrow: std={std:.3f}, iqr={iqr:.3f}"

def assert_shadow_audit_present():
  path="reports/rc1/shadow_data_audit.json"
  assert os.path.exists(path), f"missing audit report: {path}"
  rep=json.load(open(path))
  keys=["mask_uniqueness","top_mask_ratio","jaccard_hi_ratio","mean_len","std_len","dup_ratio"]
  assert all(k in rep for k in keys), "incomplete audit report"
  print("[audit] ok:", {k:rep[k] for k in keys})

def check_shadow_results(shadow_file, spearman_min, top10_min):
    """检查影子评估结果是否达到预跑门槛"""
    
    # 查找最新的影子评估结果文件
    shadow_files = list(Path("reports").glob("shadow_run_*.json"))
    if not shadow_files:
        print("❌ 未找到影子评估结果文件")
        return False
    
    latest_shadow = max(shadow_files, key=lambda x: x.stat().st_mtime)
    print(f"📄 读取影子评估结果: {latest_shadow}")
    
    try:
        with open(latest_shadow, 'r', encoding='utf-8') as f:
            shadow_data = json.load(f)
        
        # 获取稳态指标
        correlations = shadow_data.get("correlations", {}).get("stable_dataset", {})
        spearman = correlations.get("spearman", 0)
        
        overlap_metrics = shadow_data.get("overlap_metrics", {})
        top10_overlap = overlap_metrics.get("top10_overlap", 0)
        
        print(f"📊 影子评估指标:")
        print(f"  Spearman相关性: {spearman:.3f} (门槛: {spearman_min})")
        print(f"  Top10重合度: {top10_overlap:.3f} (门槛: {top10_min})")
        
        # 检查是否达标
        spearman_pass = spearman >= spearman_min
        top10_pass = top10_overlap >= top10_min
        
        # 获取评分分布进行健康检查
        score_distribution = shadow_data.get("score_distribution", {})
        new_scores = score_distribution.get("new_scores_normalized", {})
        if new_scores and "values" in new_scores:
            scores = new_scores["values"]
            assert_distribution_health(scores)
        elif "new_scores" in shadow_data:
            scores = shadow_data["new_scores"]
            assert_distribution_health(scores)
        
        if spearman_pass and top10_pass:
            print("✅ 预跑检查通过")
            return True
        else:
            print("❌ 预跑检查失败:")
            if not spearman_pass:
                print(f"  - Spearman不达标: {spearman:.3f} < {spearman_min}")
            if not top10_pass:
                print(f"  - Top10重合不达标: {top10_overlap:.3f} < {top10_min}")
            return False
            
    except Exception as e:
        print(f"❌ 读取影子评估结果失败: {e}")
        return False

def check_score_distribution_health(scores):
    """检查评分分布健康度"""
    
    if len(scores) < 10:
        return False, "样本数量过少"
    
    scores_array = np.array(scores, dtype=float)
    std = scores_array.std()
    iqr = np.percentile(scores_array, 75) - np.percentile(scores_array, 25)
    
    print(f"  📊 评分分布: std={std:.3f}, IQR={iqr:.3f}")
    
    if std < 0.08:
        return False, f"标准差过小: {std:.3f} < 0.08"
    
    if iqr < 0.12:
        return False, f"四分位距过小: {iqr:.3f} < 0.12"
    
    return True, "分布健康"

def check_data_audit():
    """检查数据审计是否通过"""
    audit_file = Path("reports/rc1/shadow_data_audit.json")
    if not audit_file.exists():
        return False, "影子数据审计文件不存在"
    
    try:
        with open(audit_file, 'r', encoding='utf-8') as f:
            audit_data = json.load(f)
        
        if not audit_data.get("passed", False):
            failures = audit_data.get("failures", [])
            return False, f"数据审计失败: {'; '.join(failures)}"
        
        # 打印关键指标
        print("📊 数据审计指标:")
        by_task = audit_data.get("by_task", {})
        detempl = audit_data.get("detemplatization", {})
        
        print(f"  任务分布: {by_task}")
        print(f"  掩码唯一率: {detempl.get('mask_uniqueness', 0):.3f}")
        print(f"  最频繁掩码占比: {detempl.get('most_common_mask_ratio', 0):.3f}")
        print(f"  高相似度对比例: {detempl.get('high_sim_ratio', 0):.3f}")
        print(f"  题干长度均值: {detempl.get('mean_length', 0):.1f}")
        
        return True, "数据审计通过"
        
    except Exception as e:
        return False, f"读取审计文件失败: {e}"

def main():
    parser = argparse.ArgumentParser(description='RC1预跑检查')
    parser.add_argument('--shadow', required=True, help='影子评估数据文件')
    parser.add_argument('--spearman-min', type=float, required=True, help='Spearman最低阈值')
    parser.add_argument('--top10-min', type=float, required=True, help='Top10重合最低阈值')
    
    args = parser.parse_args()
    
    print("🔍 RC1预跑检查开始")
    print("=" * 40)
    
    # 0. 前置检查：数据审计
    assert_shadow_audit_present()
    
    # 检查影子评估文件是否存在
    if not Path(args.shadow).exists():
        print(f"❌ 影子评估文件不存在: {args.shadow}")
        sys.exit(1)
    
    # 执行检查
    if check_shadow_results(args.shadow, args.spearman_min, args.top10_min):
        print("\n🎉 所有预跑检查通过！")
        sys.exit(0)
    else:
        print("\n❌ 预跑检查失败！")
        sys.exit(1)

if __name__ == "__main__":
    main()
