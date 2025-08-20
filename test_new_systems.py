#!/usr/bin/env python3
"""
新系统集成测试
测试异步执行器和多维度奖励系统
"""

import asyncio
import json
import time
from pathlib import Path
import sys

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.async_executor import AsyncCommandExecutor
from src.evaluation.advanced_reward_system import MultiDimensionalRewardSystem
from src.utils.logging import get_logger

logger = get_logger("test_new_systems")

async def test_async_executor():
    """测试异步执行器"""
    print("🚀 测试异步命令执行器")
    print("=" * 50)
    
    # 测试命令集合
    test_commands = [
        "echo 'Hello AsyncExecutor!'",
        "python -c 'import time; time.sleep(1); print(\"Python延迟测试\")'",
        "ls -la | head -5",
        "date",
        "python -c 'print(\"计算测试:\", 2+3*4)'",
        # "sleep 5",  # 长时间命令
        # "false",    # 失败命令  
    ]
    
    # 创建执行器
    executor = AsyncCommandExecutor(
        max_concurrent=3,
        timeout_s=10,
        retries=1,
        log_dir="logs/test_executor"
    )
    
    print(f"执行 {len(test_commands)} 个测试命令...")
    start_time = time.time()
    
    # 执行命令批次
    results = await executor.execute_batch(test_commands)
    
    execution_time = time.time() - start_time
    
    # 分析结果
    success_count = sum(1 for r in results if r.ok)
    failed_count = len(results) - success_count
    
    print(f"\n📊 执行结果:")
    print(f"总命令数: {len(results)}")
    print(f"成功: {success_count}")
    print(f"失败: {failed_count}")
    print(f"总耗时: {execution_time:.2f}秒")
    print(f"平均耗时: {execution_time/len(results):.2f}秒/命令")
    
    print(f"\n📝 详细结果:")
    for i, result in enumerate(results):
        status = "✅" if result.ok else "❌"
        cmd_short = result.cmd[:40] + "..." if len(result.cmd) > 40 else result.cmd
        print(f"{status} {i+1}. {cmd_short}")
        print(f"    耗时: {result.latency_ms}ms, 重试: {result.tries}次")
        
        if result.stdout:
            stdout_short = result.stdout.strip()[:100]
            print(f"    输出: {stdout_short}")
        
        if not result.ok and result.stderr:
            stderr_short = result.stderr.strip()[:100]
            print(f"    错误: {stderr_short}")
    
    # 获取执行摘要
    summary = executor.get_execution_summary()
    print(f"\n📈 执行摘要:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    return results

def test_reward_system():
    """测试多维度奖励系统"""
    print("\n🎯 测试多维度奖励系统")
    print("=" * 50)
    
    # 测试对话样本
    test_dialogues = [
        {
            "id": "math_test",
            "type": "math_reasoning",
            "turns": [
                {"role": "user", "content": "一个正方形的周长是20厘米，面积是多少？"},
                {"role": "assistant", "content": "<think>正方形周长=4×边长，所以边长=20÷4=5厘米。面积=边长²=5²=25平方厘米。</think>\n\n计算步骤：\n1. 求边长：周长÷4 = 20÷4 = 5厘米\n2. 求面积：边长² = 5² = 25平方厘米\n\n答案：25平方厘米"}
            ]
        },
        {
            "id": "clarification_test", 
            "type": "ambiguity_clarification",
            "turns": [
                {"role": "user", "content": "他什么时候来的？"},
                {"role": "assistant", "content": "抱歉，我需要更具体的信息。请问您指的是哪位人士呢？"},
                {"role": "user", "content": "我说的是张教授"},
                {"role": "assistant", "content": "明白了！关于张教授的到达时间，我需要查看具体的日程安排才能给您准确答复。"}
            ]
        },
        {
            "id": "multi_hop_test",
            "type": "multi_hop",
            "turns": [
                {"role": "user", "content": "世界最高峰在哪个国家？这个国家的首都是什么？"},
                {"role": "assistant", "content": "让我分步回答：\n\n第一步：世界最高峰是珠穆朗玛峰，位于中国和尼泊尔边境。\n\n第二步：涉及两个国家的首都：\n- 中国的首都是北京\n- 尼泊尔的首都是加德满都\n\n所以答案是：珠穆朗玛峰位于中国和尼泊尔边境，两国首都分别是北京和加德满都。"}
            ]
        }
    ]
    
    # 创建奖励系统
    reward_system = MultiDimensionalRewardSystem(
        model_name="gemini-2.5-pro",
        prompt_version="test_v1",
        cache_db="logs/test_cache.sqlite"
    )
    
    print(f"评估 {len(test_dialogues)} 个测试对话...")
    
    all_results = []
    for dialogue in test_dialogues:
        print(f"\n📋 评估对话: {dialogue['id']} ({dialogue['type']})")
        
        start_time = time.time()
        result = reward_system.evaluate_dialogue(dialogue)
        eval_time = time.time() - start_time
        
        result["evaluation_time_ms"] = int(eval_time * 1000)
        all_results.append(result)
        
        # 显示结果
        print(f"主奖励: {result['primary_reward']:.3f}")
        print(f"评估耗时: {eval_time*1000:.1f}ms")
        
        print("组件分数:")
        for key, score in result["component_scores"].items():
            print(f"  {key}: {score:.3f}")
        
        print("二元指标:")
        for key, value in result["binary_indicators"].items():
            indicator = "✅" if value else "❌"
            print(f"  {indicator} {key}")
        
        print(f"硬规则分数: {result['hard_rules']['rules_score']:.3f}")
        print(f"评分方差: {result['meta']['variance']:.4f}")
    
    # 系统级统计
    print(f"\n📊 系统评估统计:")
    primary_rewards = [r["primary_reward"] for r in all_results]
    eval_times = [r["evaluation_time_ms"] for r in all_results]
    
    print(f"平均主奖励: {sum(primary_rewards)/len(primary_rewards):.3f}")
    print(f"奖励范围: {min(primary_rewards):.3f} - {max(primary_rewards):.3f}")
    print(f"平均评估时间: {sum(eval_times)/len(eval_times):.1f}ms")
    
    # 缓存统计
    cache_stats = reward_system.get_cache_stats()
    print(f"\n💾 缓存统计:")
    print(json.dumps(cache_stats, indent=2, ensure_ascii=False))
    
    return all_results

async def test_integration():
    """集成测试：结合异步执行器和奖励系统"""
    print("\n🔗 集成测试")
    print("=" * 50)
    
    # 创建一些需要异步执行的数据处理命令
    data_commands = [
        "python -c 'import json; print(json.dumps({\"test\": \"data1\", \"score\": 0.85}))'",
        "python -c 'import json; print(json.dumps({\"test\": \"data2\", \"score\": 0.72}))'",
        "python -c 'import json; print(json.dumps({\"test\": \"data3\", \"score\": 0.91}))'",
    ]
    
    executor = AsyncCommandExecutor(max_concurrent=2, log_dir="logs/integration_test")
    
    print("执行数据生成命令...")
    results = await executor.execute_batch(data_commands)
    
    # 处理命令结果并用奖励系统评估
    reward_system = MultiDimensionalRewardSystem(cache_db="logs/integration_cache.sqlite")
    
    processed_data = []
    for i, result in enumerate(results):
        if result.ok:
            try:
                # 解析命令输出的JSON数据
                data = json.loads(result.stdout.strip())
                
                # 构建模拟对话
                dialogue = {
                    "id": f"integration_test_{i}",
                    "turns": [
                        {"role": "user", "content": f"处理数据: {data['test']}"},
                        {"role": "assistant", "content": f"数据处理完成，预测分数: {data['score']}"}
                    ],
                    "command_result": result.__dict__
                }
                
                # 使用奖励系统评估
                reward_result = reward_system.evaluate_dialogue(dialogue)
                
                processed_data.append({
                    "dialogue_id": dialogue["id"],
                    "command_success": True,
                    "command_time_ms": result.latency_ms,
                    "reward_score": reward_result["primary_reward"],
                    "evaluation": reward_result
                })
                
                print(f"✅ 处理 {dialogue['id']}: 命令{result.latency_ms}ms, 奖励{reward_result['primary_reward']:.3f}")
                
            except json.JSONDecodeError as e:
                print(f"❌ 解析命令输出失败: {e}")
        else:
            print(f"❌ 命令执行失败: {result.cmd}")
    
    print(f"\n🎯 集成测试完成，成功处理 {len(processed_data)} 个样本")
    
    if processed_data:
        avg_reward = sum(d["reward_score"] for d in processed_data) / len(processed_data)
        avg_cmd_time = sum(d["command_time_ms"] for d in processed_data) / len(processed_data)
        
        print(f"平均奖励分数: {avg_reward:.3f}")
        print(f"平均命令执行时间: {avg_cmd_time:.1f}ms")
    
    return processed_data

async def main():
    """主测试函数"""
    print("🧪 新系统集成测试")
    print("=" * 60)
    
    try:
        # 测试1: 异步执行器
        executor_results = await test_async_executor()
        
        # 测试2: 奖励系统
        reward_results = test_reward_system()
        
        # 测试3: 集成测试
        integration_results = await test_integration()
        
        # 保存测试结果
        test_summary = {
            "test_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "async_executor": {
                "total_commands": len(executor_results),
                "success_count": sum(1 for r in executor_results if r.ok),
                "avg_latency_ms": sum(r.latency_ms for r in executor_results) / len(executor_results)
            },
            "reward_system": {
                "total_dialogues": len(reward_results),
                "avg_primary_reward": sum(r["primary_reward"] for r in reward_results) / len(reward_results),
                "avg_eval_time_ms": sum(r["evaluation_time_ms"] for r in reward_results) / len(reward_results)
            },
            "integration": {
                "processed_samples": len(integration_results),
                "avg_reward": sum(d["reward_score"] for d in integration_results) / len(integration_results) if integration_results else 0
            }
        }
        
        # 保存详细结果
        results_file = "logs/test_new_systems_results.json"
        Path("logs").mkdir(exist_ok=True)
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                "summary": test_summary,
                "executor_results": [r.__dict__ for r in executor_results],
                "reward_results": reward_results,
                "integration_results": integration_results
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n🎉 所有测试完成！")
        print(f"📄 详细结果已保存到: {results_file}")
        print(f"\n📊 测试摘要:")
        print(json.dumps(test_summary, indent=2, ensure_ascii=False))
        
        # 验证与旧系统的兼容性提示
        print(f"\n🔄 下一步建议:")
        print(f"1. 将异步执行器集成到数据生成管道")
        print(f"2. 在现有45个对话上比较新旧奖励系统")
        print(f"3. 进行小规模PPO试验验证新奖励系统")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
