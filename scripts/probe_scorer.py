#!/usr/bin/env python3
"""
打分器连通性探针 - 验证真实API调用
"""

import argparse
import json
import time
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.advanced_reward_system import MultiDimensionalRewardSystem

def probe_scorer(n_samples=8, provider="deepseek_r1", live=True):
    """探测打分器连通性"""
    print(f"🔍 探测打分器连通性: {provider}")
    print("=" * 40)
    
    # 初始化评分系统
    scorer = MultiDimensionalRewardSystem(
        model_name=provider,
        temperature=0.0,
        top_p=0.0
    )
    
    # 测试样本
    test_samples = [
        {
            "query": "计算 15 + 23 × 4",
            "response": "我来计算这个表达式：\n按照运算顺序：15 + 23 × 4 = 15 + 92 = 107",
            "task_type": "math",
            "needs_clarification": False
        },
        {
            "query": "帮我分析投资方案",
            "response": "我需要更多信息来为您分析：\n1. 投资类型和金额\n2. 风险偏好\n3. 投资期限",
            "task_type": "clarify", 
            "needs_clarification": True
        },
        {
            "query": "谁是美国第一任总统？他的任期是什么时候？",
            "response": "美国第一任总统是乔治·华盛顿，任期从1789年到1797年。",
            "task_type": "multihop",
            "needs_clarification": False
        }
    ] * (n_samples // 3 + 1)
    
    results = []
    total_api_calls = 0
    total_latency = 0
    
    for i, sample in enumerate(test_samples[:n_samples]):
        print(f"📊 测试样本 {i+1}/{n_samples}: {sample['task_type']}")
        
        start_time = time.time()
        try:
            # 执行评分（K=3投票）
            dialogue = {
                "query": sample["query"],
                "response": sample["response"],
                "needs_clarification": sample["needs_clarification"]
            }
            
            result = scorer.evaluate_dialogue(dialogue)
            
            end_time = time.time()
            latency = end_time - start_time
            total_latency += latency
            
            # 检查结果
            if "error" in result:
                print(f"  ❌ 评分失败: {result['error']}")
                continue
            
            # 检查是否有真实API调用
            api_calls = result.get("api_calls", 0)
            total_api_calls += api_calls
            
            final_score = result.get("final_score", 0)
            variance = result.get("variance", 0)
            
            print(f"  ✅ 评分: {final_score:.3f}, 方差: {variance:.3f}")
            print(f"  📞 API调用: {api_calls}次, 延迟: {latency:.2f}s")
            
            results.append({
                "sample_id": i,
                "final_score": final_score,
                "variance": variance,
                "api_calls": api_calls,
                "latency": latency
            })
            
        except Exception as e:
            print(f"  ❌ 评分异常: {e}")
            continue
    
    # 汇总结果
    print("\n" + "=" * 40)
    print("🎯 探测结果汇总:")
    
    if results:
        avg_score = sum(r["final_score"] for r in results) / len(results)
        avg_variance = sum(r["variance"] for r in results) / len(results)
        avg_latency = total_latency / len(results)
        
        print(f"  📊 成功样本: {len(results)}/{n_samples}")
        print(f"  📊 平均评分: {avg_score:.3f}")
        print(f"  📊 平均方差: {avg_variance:.3f}")
        print(f"  📊 平均延迟: {avg_latency:.2f}s")
        print(f"  📞 总API调用: {total_api_calls}次")
        
        # 验证连通性
        assert total_api_calls > 0, "❌ 无真实API调用，连通性失败"
        assert avg_latency > 0.1, "❌ 延迟过低，疑似模拟响应"
        assert avg_variance >= 0, "❌ 方差异常"
        
        print("  ✅ 连通性验证通过")
        
        # 保存探测结果
        probe_result = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "provider": provider,
            "n_samples": n_samples,
            "successful_samples": len(results),
            "total_api_calls": total_api_calls,
            "avg_latency": avg_latency,
            "avg_score": avg_score,
            "avg_variance": avg_variance
        }
        
        with open("reports/rc1/scorer_probe.json", 'w', encoding='utf-8') as f:
            json.dump(probe_result, f, indent=2)
        
        return True
    else:
        print("  ❌ 所有样本评分失败")
        return False

def main():
    parser = argparse.ArgumentParser(description="打分器连通性探针")
    parser.add_argument('--n', type=int, default=8, help='测试样本数量')
    parser.add_argument('--provider', default='deepseek_r1', help='打分器提供商')
    parser.add_argument('--live', action='store_true', help='实时模式')
    
    args = parser.parse_args()
    
    success = probe_scorer(args.n, args.provider, args.live)
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
