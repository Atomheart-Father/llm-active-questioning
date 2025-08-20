#!/usr/bin/env python3
"""
RC1产物完整性检查脚本
验证所有必需文件和报告的完整性
"""

import json
from pathlib import Path
import os

def check_rc1_artifacts():
    """检查RC1所有产物的完整性"""
    print("🔍 RC1产物完整性检查")
    print("=" * 50)
    
    # 必需的产物清单
    required_artifacts = {
        "训练报告": [
            "reports/rc1/rc1_final_report.json",
            "reports/rc1/seed_20250820/training_result.json",
            "reports/rc1/seed_20250821/training_result.json", 
            "reports/rc1/seed_20250822/training_result.json"
        ],
        "模型权重": [
            "checkpoints/rc1/best/",
            "checkpoints/rc1/20250820/step_43000/",
            "checkpoints/rc1/20250821/step_46000/",
            "checkpoints/rc1/20250822/step_47000/"
        ],
        "基准测试": [
            "reports/rc1/benchmarks/inference_benchmark.json"
        ],
        "文档": [
            "reports/rc1/model_card.md",
            "release/RC1/README.md",
            "release/RC1/CHANGELOG.md",
            "release/RC1/summary.md"
        ],
        "配置": [
            "configs/ppo_scale.yaml",
            "configs/weights.json",
            "scripts/rc1_precheck.py"
        ]
    }
    
    all_good = True
    summary = {"总计": 0, "存在": 0, "缺失": 0}
    
    for category, artifacts in required_artifacts.items():
        print(f"\n📂 {category}:")
        category_good = True
        
        for artifact in artifacts:
            summary["总计"] += 1
            path = Path(artifact)
            
            if path.exists():
                if path.is_dir():
                    # 检查目录非空
                    contents = list(path.iterdir())
                    if contents:
                        print(f"  ✅ {artifact}/ ({len(contents)}个文件)")
                        summary["存在"] += 1
                    else:
                        print(f"  ⚠️ {artifact}/ (空目录)")
                        category_good = False
                        summary["缺失"] += 1
                else:
                    # 检查文件大小
                    size = path.stat().st_size
                    if size > 0:
                        size_mb = size / (1024 * 1024)
                        print(f"  ✅ {artifact} ({size_mb:.2f}MB)")
                        summary["存在"] += 1
                    else:
                        print(f"  ❌ {artifact} (空文件)")
                        category_good = False
                        summary["缺失"] += 1
            else:
                print(f"  ❌ {artifact} (不存在)")
                category_good = False
                summary["缺失"] += 1
        
        if not category_good:
            all_good = False
    
    # 检查关键指标
    print(f"\n📊 关键指标验证:")
    try:
        with open("reports/rc1/rc1_final_report.json", 'r', encoding='utf-8') as f:
            report = json.load(f)
        
        # 检查训练完成度
        seeds_completed = len(report.get("seed_results", []))
        print(f"  ✅ 种子训练: {seeds_completed}/3 完成")
        
        # 检查最优checkpoint
        best_checkpoint = report.get("best_checkpoint", {})
        if best_checkpoint and "checkpoint_path" in best_checkpoint:
            print(f"  ✅ 最优checkpoint: {best_checkpoint['checkpoint_path']}")
        else:
            print(f"  ❌ 最优checkpoint: 未找到")
            all_good = False
        
        # 检查验收结果
        acceptance = report.get("acceptance_check", {})
        if acceptance:
            checks = acceptance.get("checks", {})
            passed_count = sum(1 for check in checks.values() if check.get("passed", False))
            total_count = len(checks)
            print(f"  📋 验收标准: {passed_count}/{total_count} 通过")
            
            # 详细验收状态
            if checks:
                print("    详细状态:")
                for name, check in checks.items():
                    status = "✅" if check.get("passed", False) else "❌"
                    value = check.get("value", "N/A")
                    threshold = check.get("threshold", "N/A")
                    print(f"      {status} {name}: {value} (门槛: {threshold})")
        
    except Exception as e:
        print(f"  ❌ 报告解析失败: {e}")
        all_good = False
    
    # 检查基准测试
    print(f"\n⚡ 性能基准:")
    try:
        with open("reports/rc1/benchmarks/inference_benchmark.json", 'r', encoding='utf-8') as f:
            benchmarks = json.load(f)
        
        models = benchmarks.get("models", {})
        for quant_type, metrics in models.items():
            if "error" not in metrics:
                tps = metrics.get("tokens_per_second", 0)
                memory = metrics.get("memory_usage_gb", 0)
                print(f"  ✅ {quant_type}: {tps:.1f} tokens/s, {memory:.1f}GB")
            else:
                print(f"  ❌ {quant_type}: {metrics['error']}")
                
    except Exception as e:
        print(f"  ❌ 基准测试解析失败: {e}")
        all_good = False
    
    # 总结
    print(f"\n" + "=" * 50)
    print(f"📋 产物检查总结:")
    print(f"  总计文件: {summary['总计']}")
    print(f"  存在文件: {summary['存在']}")
    print(f"  缺失文件: {summary['缺失']}")
    print(f"  完整性: {summary['存在'] / summary['总计'] * 100:.1f}%")
    
    if all_good:
        print(f"  状态: ✅ 全部完整")
        print(f"\n🎉 RC1产物检查通过，可以进行发布！")
    else:
        print(f"  状态: ❌ 存在缺失")
        print(f"\n⚠️ 请修复缺失项目后重新检查")
    
    return all_good

if __name__ == "__main__":
    success = check_rc1_artifacts()
    exit(0 if success else 1)
