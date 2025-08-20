#!/usr/bin/env python3
"""
防伪闸门检查 - 确保RC1为真实训练，拒绝任何dry-run产物
"""

import os
import json
import hashlib
import sqlite3
from pathlib import Path
import sys
import time

def check_scorer_connectivity():
    """检查打分器真实连通性"""
    print("🔍 检查打分器连通性...")
    
    # 检查API Key配置
    scorer_provider = os.getenv("SCORER_PROVIDER")
    api_key = os.getenv("SCORER_API_KEY")
    
    assert scorer_provider in {"deepseek_r1", "gemini", "gpt35"}, f"❌ 打分器未配置: {scorer_provider}"
    assert api_key, "❌ SCORER_API_KEY未设置：拒绝dry-run"
    
    # 检查缓存数据库的真实使用情况
    cache_db = Path("gemini_cache.sqlite")
    if cache_db.exists():
        conn = sqlite3.connect(cache_db)
        cursor = conn.cursor()
        
        # 检查最近的真实API调用
        cursor.execute("""
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN tries > 0 THEN 1 ELSE 0 END) as real_calls,
                   AVG(latency_ms) as avg_latency
            FROM cache 
            WHERE timestamp > datetime('now', '-1 hour')
        """)
        result = cursor.fetchone()
        conn.close()
        
        total, real_calls, avg_latency = result
        if total > 0:
            hit_rate = (total - real_calls) / total
            print(f"  📊 最近1小时: {total}次评分, {real_calls}次真实API调用")
            print(f"  📊 缓存命中率: {hit_rate:.1%}, 平均延迟: {avg_latency:.1f}ms")
            
            # 防伪检查：缓存命中率不能过高（首轮严格）
            assert hit_rate < 0.90, f"❌ 缓存命中率过高({hit_rate:.1%})，疑似dry-run"
            assert real_calls >= 1, "❌ 无真实API调用，疑似dry-run"
        
    print("  ✅ 打分器连通性检查通过")

def check_training_data():
    """检查训练数据真实性"""
    print("🔍 检查训练数据...")
    
    # 检查shadow评估数据
    shadow_file = Path("data/shadow_eval_245.jsonl")
    assert shadow_file.exists(), "❌ shadow评估数据缺失"
    
    with open(shadow_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    assert len(lines) >= 245, f"❌ 评估样本不足: {len(lines)} < 245"
    
    # 计算数据哈希并记录
    data_content = ''.join(lines)
    data_hash = hashlib.sha256(data_content.encode()).hexdigest()
    
    # 检查成功率分布（防止全0/全1）
    success_counts = {"math": 0, "multihop": 0, "clarify": 0}
    total_counts = {"math": 0, "multihop": 0, "clarify": 0}
    
    for line in lines:
        try:
            sample = json.loads(line.strip())
            task_type = sample.get("task_type", "unknown")
            if task_type in success_counts:
                total_counts[task_type] += 1
                # 模拟成功判断（实际应有具体逻辑）
                if sample.get("success", False):
                    success_counts[task_type] += 1
        except:
            continue
    
    # 防伪检查：成功率不能极端
    for task_type in success_counts:
        if total_counts[task_type] > 0:
            success_rate = success_counts[task_type] / total_counts[task_type]
            assert 0.1 <= success_rate <= 0.9, f"❌ {task_type}成功率极端: {success_rate:.1%}"
    
    # 保存数据清单
    manifest = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "total_samples": len(lines),
        "data_hash": data_hash,
        "success_rates": {k: success_counts[k]/total_counts[k] if total_counts[k] > 0 else 0 
                         for k in success_counts}
    }
    
    with open("reports/rc1/data_hash.json", 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"  ✅ 数据样本: {len(lines)}条")
    print(f"  ✅ 数据哈希: {data_hash[:16]}...")
    print(f"  ✅ 成功率分布: {manifest['success_rates']}")

def check_model_checkpoints():
    """检查模型权重真实性"""
    print("🔍 检查模型权重...")
    
    checkpoints_dir = Path("checkpoints/rc1")
    real_checkpoints = []
    
    # 遍历所有checkpoint目录
    for seed_dir in checkpoints_dir.iterdir():
        if seed_dir.is_dir() and seed_dir.name.isdigit():
            for step_dir in seed_dir.iterdir():
                if step_dir.is_dir() and step_dir.name.startswith("step_"):
                    # 检查权重文件
                    has_real_weights = False
                    
                    # 检查LoRA权重
                    adapter_model = step_dir / "adapter_model.safetensors"
                    if adapter_model.exists() and adapter_model.stat().st_size > 5 * 1024 * 1024:  # >5MB
                        has_real_weights = True
                        print(f"  ✅ LoRA权重: {step_dir} ({adapter_model.stat().st_size // 1024 // 1024}MB)")
                    
                    # 检查全参权重
                    for weight_file in step_dir.glob("pytorch_model*.bin"):
                        if weight_file.stat().st_size > 50 * 1024 * 1024:  # >50MB
                            has_real_weights = True
                            print(f"  ✅ 全参权重: {step_dir} ({weight_file.stat().st_size // 1024 // 1024}MB)")
                            break
                    
                    for weight_file in step_dir.glob("*.safetensors"):
                        if weight_file.name != "adapter_model.safetensors" and weight_file.stat().st_size > 50 * 1024 * 1024:
                            has_real_weights = True
                            print(f"  ✅ SafeTensors权重: {step_dir} ({weight_file.stat().st_size // 1024 // 1024}MB)")
                            break
                    
                    if has_real_weights:
                        real_checkpoints.append(str(step_dir))
                    else:
                        # 检查是否为占位符
                        readme_file = step_dir / "README.md"
                        if readme_file.exists():
                            with open(readme_file, 'r', encoding='utf-8') as f:
                                content = f.read()
                            if "占位符" in content or "placeholder" in content.lower():
                                print(f"  ❌ 检测到占位符checkpoint: {step_dir}")
                                assert False, f"❌ 发现占位符权重，拒绝dry-run: {step_dir}"
    
    assert len(real_checkpoints) > 0, "❌ 未找到任何真实模型权重，疑似dry-run"
    print(f"  ✅ 真实checkpoint: {len(real_checkpoints)}个")

def check_training_curves():
    """检查训练曲线真实性"""
    print("🔍 检查训练曲线...")
    
    # 检查最终报告
    report_file = Path("reports/rc1/rc1_final_report.json")
    if report_file.exists():
        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
        
        # 检查每个种子的训练曲线
        for seed_result in report.get("seed_results", []):
            if "training" in seed_result and "training_curves" in seed_result["training"]:
                curves = seed_result["training"]["training_curves"]
                
                # 检查奖励曲线方差
                rewards = curves.get("rewards", [])
                kl_divs = curves.get("kl_divs", [])
                
                if len(rewards) > 1:
                    reward_std = __import__('statistics').stdev(rewards)
                    assert reward_std > 0, f"❌ 奖励曲线无变化，疑似常数/模拟"
                    print(f"  ✅ 种子{seed_result['seed']} 奖励曲线方差: {reward_std:.4f}")
                
                if len(kl_divs) > 1:
                    kl_std = __import__('statistics').stdev(kl_divs)
                    assert kl_std > 0, f"❌ KL曲线无变化，疑似常数/模拟"
                    print(f"  ✅ 种子{seed_result['seed']} KL曲线方差: {kl_std:.4f}")

def check_shadow_evaluation():
    """检查影子评估真实性"""
    print("🔍 检查影子评估...")
    
    report_file = Path("reports/rc1/rc1_final_report.json")
    if report_file.exists():
        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
        
        # 检查影子指标
        if "best_checkpoint" in report and "metrics" in report["best_checkpoint"]:
            shadow_metrics = report["best_checkpoint"]["metrics"].get("shadow_metrics", {})
            
            spearman = shadow_metrics.get("spearman")
            top10_overlap = shadow_metrics.get("top10_overlap")
            corr_improve = shadow_metrics.get("corr_improve_pct")
            
            # 防伪检查：不能为None或明显的构造值
            assert spearman is not None, "❌ Spearman相关性为空"
            assert top10_overlap is not None, "❌ Top10重合为空"
            assert corr_improve is not None, "❌ 相关性改善为空"
            
            # 检查是否为明显的模拟值
            assert not (spearman == 0.0 and top10_overlap == 0.0 and corr_improve == 0.0), \
                "❌ 影子指标全为0，疑似构造"
            
            print(f"  ✅ Spearman: {spearman:.3f}")
            print(f"  ✅ Top10重合: {top10_overlap:.3f}")
            print(f"  ✅ 相关性改善: {corr_improve:.1f}%")

def main():
    """主检查流程"""
    print("🚨 RC1防伪闸门检查")
    print("=" * 50)
    
    # 检查环境变量
    run_mode = os.getenv("RUN_MODE")
    assert run_mode == "prod", f"❌ RUN_MODE={run_mode}，必须为'prod'"
    print(f"✅ 运行模式: {run_mode}")
    
    try:
        check_scorer_connectivity()
        print()
        
        check_training_data()
        print()
        
        check_model_checkpoints()
        print()
        
        check_training_curves()
        print()
        
        check_shadow_evaluation()
        print()
        
        print("=" * 50)
        print("✅ 防伪检查全部通过 - 确认为真实训练")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ 防伪检查失败: {e}")
        print("❌ 拒绝进入RC1发布流程")
        return 1
    except Exception as e:
        print(f"\n❌ 检查过程出错: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
