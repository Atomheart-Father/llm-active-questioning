#!/usr/bin/env python3
"""
预跑检查脚本 - RC1影子评估阈值验证
"""

import argparse
import json
import sys
import os
from pathlib import Path

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

def main():
    parser = argparse.ArgumentParser(description='RC1预跑检查')
    parser.add_argument('--shadow', required=True, help='影子评估数据文件')
    parser.add_argument('--spearman-min', type=float, required=True, help='Spearman最低阈值')
    parser.add_argument('--top10-min', type=float, required=True, help='Top10重合最低阈值')
    
    args = parser.parse_args()
    
    print("🔍 RC1预跑检查开始")
    print("=" * 40)
    
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
