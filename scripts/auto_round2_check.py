#!/usr/bin/env python3
"""
自动计算Round 2预检状态
根据各项检查结果自动判定是否通过，禁止手工设置pass=true
"""

import json
import os
import sys
import time
import datetime
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """运行命令并返回结果"""
    print(f"🔍 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        print(f"❌ 命令执行失败: {e}")
        return False, "", str(e)

def check_round2_requirements():
    """检查Round 2所有要求"""
    checks = {}
    
    # 1. 防伪检查（缓存阈值95%）
    success, stdout, stderr = run_command(
        "python scripts/assert_not_simulated.py --cache_hit_lt 0.95",
        "防伪检查（缓存<95%）"
    )
    checks["anti_simulation"] = {
        "passed": success,
        "description": "防伪检查",
        "details": stdout if success else stderr
    }
    
    # 2. 影子运行检查
    success, stdout, stderr = run_command(
        "python -m src.evaluation.shadow_run --n 245 --seed 20250820 --stratify --tag pre_run_check",
        "影子运行预检"
    )
    checks["shadow_run"] = {
        "passed": success,
        "description": "影子运行预检",
        "details": stdout if success else stderr
    }
    
    # 3. 检查影子运行结果文件
    shadow_files = list(Path("reports").glob("shadow_run_*.json"))
    if shadow_files:
        latest_shadow = max(shadow_files, key=lambda x: x.stat().st_mtime)
        try:
            with open(latest_shadow, 'r', encoding='utf-8') as f:
                shadow_data = json.load(f)
            
            # 检查稳态指标
            correlations = shadow_data.get("correlations", {}).get("stable_dataset", {})
            spearman = correlations.get("spearman", 0)
            
            overlap_metrics = shadow_data.get("overlap_metrics", {})
            top10_overlap = overlap_metrics.get("top10_overlap", 0)
            
            # 预跑门槛检查（比正式RC1验收门槛低）
            shadow_passed = spearman >= 0.55 and top10_overlap >= 0.60
            
            if not shadow_passed:
                print(f"❌ 影子指标未达预跑门槛:")
                print(f"   Spearman: {spearman:.3f} (需要≥0.55)")
                print(f"   Top10重合: {top10_overlap:.3f} (需要≥0.60)")
                print(f"   建议检查奖励聚合或成功标签口径")
            
            checks["shadow_metrics"] = {
                "passed": shadow_passed,
                "description": "影子指标检查",
                "details": f"Spearman: {spearman:.3f}, Top10重合: {top10_overlap:.3f}",
                "spearman": spearman,
                "top10_overlap": top10_overlap
            }
        except Exception as e:
            checks["shadow_metrics"] = {
                "passed": False,
                "description": "影子指标检查",
                "details": f"无法读取影子运行结果: {e}"
            }
    else:
        checks["shadow_metrics"] = {
            "passed": False,
            "description": "影子指标检查", 
            "details": "未找到影子运行结果文件"
        }
    
    # 4. 数据质量检查
    seed_pool_exists = Path("data/rollouts/rc1_seed.jsonl").exists()
    balanced_exists = Path("data/rollouts/rc1_seed.balanced.jsonl").exists()
    
    checks["data_quality"] = {
        "passed": seed_pool_exists and balanced_exists,
        "description": "数据质量检查",
        "details": f"种子池: {'✅' if seed_pool_exists else '❌'}, 平衡版: {'✅' if balanced_exists else '❌'}"
    }
    
    return checks

def generate_round2_report():
    """生成Round 2报告"""
    print("🔄 执行Round 2自动预检...")
    
    checks = check_round2_requirements()
    
    # 计算总体通过状态
    all_passed = all(check["passed"] for check in checks.values())
    
    # 生成报告
    report = {
        "round": "round2",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "pass": all_passed,
        "auto_generated": True,
        "checks": checks,
        "summary": {
            "total_checks": len(checks),
            "passed_checks": sum(1 for check in checks.values() if check["passed"]),
            "failed_checks": sum(1 for check in checks.values() if not check["passed"])
        }
    }
    
    # 保存报告
    report_file = Path("reports/preflight/round2_pass.json")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # 输出结果
    print("\n📋 Round 2预检结果:")
    print("=" * 40)
    
    for check_name, check_data in checks.items():
        status = "✅ PASS" if check_data["passed"] else "❌ FAIL"
        print(f"{status} {check_data['description']}")
        if not check_data["passed"]:
            print(f"    详情: {check_data['details']}")
    
    print(f"\n🎯 总体状态: {'✅ PASS' if all_passed else '❌ FAIL'}")
    print(f"📄 报告保存: {report_file}")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit(generate_round2_report())
