#!/usr/bin/env python3
"""
Over-Clarification Penalty - 过度澄清惩罚系统
在needs_clarification=false的样本上惩罚无必要的澄清
"""

import argparse
import json
import re
from typing import Dict, List, Any, Tuple
from pathlib import Path
import logging
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

class OverClarificationPenalty:
    """过度澄清惩罚计算器"""
    
    def __init__(self, alpha: float = 0.07, cap: int = 3, 
                 enforce_when_needs_clarification_false: bool = True):
        self.alpha = alpha
        self.cap = cap
        self.enforce = enforce_when_needs_clarification_false
        
        # 澄清行为模式
        self.clarification_patterns = [
            r'[？?]',  # 问号
            r'请问|能否|可以.*吗|是否',  # 礼貌询问
            r'哪.*?[？?]|什么.*?[？?]|如何.*?[？?]|为什么.*?[？?]',  # 疑问词
            r'需要.*?确认|需要.*?澄清|不太确定',  # 澄清表述
            r'<QUESTION>.*?</QUESTION>',  # 结构化澄清标签
            r'我想了解|我需要知道|能告诉我',  # 信息请求
        ]
        
        logger.info(f"过度澄清惩罚初始化: α={alpha}, cap={cap}, enforce={self.enforce}")
    
    def detect_clarification_turns(self, dialogue: Dict[str, Any]) -> int:
        """检测澄清轮数"""
        clarify_count = 0
        
        if "turns" in dialogue:
            for turn in dialogue["turns"]:
                if isinstance(turn, dict) and turn.get("role") == "assistant":
                    content = turn.get("content", "")
                    if self._is_clarification_turn(content):
                        clarify_count += 1
        
        return clarify_count
    
    def _is_clarification_turn(self, content: str) -> bool:
        """判断是否为澄清轮次"""
        for pattern in self.clarification_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
    def should_apply_penalty(self, dialogue: Dict[str, Any]) -> bool:
        """判断是否应该应用惩罚"""
        if not self.enforce:
            return False
        
        # 检查模板标注
        meta = dialogue.get("meta", {})
        needs_clarification = meta.get("needs_clarification", True)
        
        # 只对不需要澄清的样本应用惩罚
        return not needs_clarification
    
    def compute_penalty(self, dialogue: Dict[str, Any]) -> Dict[str, Any]:
        """计算过度澄清惩罚"""
        # 检测澄清轮数
        clarify_turns = self.detect_clarification_turns(dialogue)
        
        # 判断是否应用惩罚
        should_penalty = self.should_apply_penalty(dialogue)
        
        if should_penalty and clarify_turns > 0:
            # penalty = alpha * min(c, cap)
            penalty = self.alpha * min(clarify_turns, self.cap)
        else:
            penalty = 0.0
        
        result = {
            "penalty": penalty,
            "clarify_turns": clarify_turns,
            "should_apply": should_penalty,
            "meta": {
                "alpha": self.alpha,
                "cap": self.cap,
                "needs_clarification": dialogue.get("meta", {}).get("needs_clarification", True)
            }
        }
        
        return result
    
    def apply_penalty_to_reward(self, base_reward: float, penalty_info: Dict[str, Any]) -> float:
        """将惩罚应用到基础奖励"""
        penalty = penalty_info["penalty"]
        penalized_reward = max(0.0, base_reward - penalty)
        return penalized_reward

def test_penalty_system():
    """单元测试"""
    penalty_system = OverClarificationPenalty(alpha=0.07, cap=3)
    
    test_cases = [
        {
            "name": "不触发样本",
            "dialogue": {
                "meta": {"needs_clarification": True},
                "turns": [
                    {"role": "user", "content": "计算1+1"},
                    {"role": "assistant", "content": "1+1=2"}
                ]
            },
            "expected_penalty": 0.0
        },
        {
            "name": "触发样本c=1",
            "dialogue": {
                "meta": {"needs_clarification": False},
                "turns": [
                    {"role": "user", "content": "计算1+1"},
                    {"role": "assistant", "content": "请问您需要详细步骤吗？"}
                ]
            },
            "expected_penalty": 0.07
        },
        {
            "name": "触发样本c=2",
            "dialogue": {
                "meta": {"needs_clarification": False},
                "turns": [
                    {"role": "user", "content": "计算1+1"},
                    {"role": "assistant", "content": "您指的是什么类型的加法？"},
                    {"role": "user", "content": "普通加法"},
                    {"role": "assistant", "content": "还需要我说明计算过程吗？"}
                ]
            },
            "expected_penalty": 0.14
        },
        {
            "name": "触发样本c=5超过cap",
            "dialogue": {
                "meta": {"needs_clarification": False},
                "turns": [
                    {"role": "user", "content": "计算1+1"},
                    {"role": "assistant", "content": "请问？"},
                    {"role": "assistant", "content": "能否？"},
                    {"role": "assistant", "content": "是否？"},
                    {"role": "assistant", "content": "什么？"},
                    {"role": "assistant", "content": "如何？"}
                ]
            },
            "expected_penalty": 0.21  # alpha * cap = 0.07 * 3
        }
    ]
    
    print("🧪 过度澄清惩罚单元测试")
    print("=" * 50)
    
    all_passed = True
    for test_case in test_cases:
        result = penalty_system.compute_penalty(test_case["dialogue"])
        actual_penalty = result["penalty"]
        expected_penalty = test_case["expected_penalty"]
        
        passed = abs(actual_penalty - expected_penalty) < 0.001
        status = "✅ PASS" if passed else "❌ FAIL"
        
        print(f"{status} {test_case['name']}")
        print(f"  期望惩罚: {expected_penalty}")
        print(f"  实际惩罚: {actual_penalty}")
        print(f"  澄清轮数: {result['clarify_turns']}")
        print(f"  应用惩罚: {result['should_apply']}")
        print()
        
        if not passed:
            all_passed = False
    
    if all_passed:
        print("🎉 所有测试通过!")
    else:
        print("❌ 部分测试失败!")
    
    return all_passed

def run_ablation_study(penalty_system: OverClarificationPenalty, 
                      samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """运行消融研究"""
    # 加载奖励系统
    from src.evaluation.advanced_reward_system import MultiDimensionalRewardSystem
    
    reward_system = MultiDimensionalRewardSystem()
    
    # 不含惩罚的结果
    no_penalty_results = []
    # 含惩罚的结果
    with_penalty_results = []
    
    over_clarification_count = 0
    total_clarify_turns = 0
    
    for sample in samples:
        # 基础奖励评估
        base_result = reward_system.evaluate_dialogue(sample)
        base_reward = base_result["primary_reward"]
        
        # 计算惩罚
        penalty_info = penalty_system.compute_penalty(sample)
        penalty = penalty_info["penalty"]
        penalized_reward = penalty_system.apply_penalty_to_reward(base_reward, penalty_info)
        
        # 统计
        if penalty > 0:
            over_clarification_count += 1
        total_clarify_turns += penalty_info["clarify_turns"]
        
        no_penalty_results.append({
            "sample_id": sample.get("id", "unknown"),
            "task_type": sample.get("task_type", "unknown"),
            "reward": base_reward,
            "clarify_turns": penalty_info["clarify_turns"]
        })
        
        with_penalty_results.append({
            "sample_id": sample.get("id", "unknown"),
            "task_type": sample.get("task_type", "unknown"), 
            "reward": penalized_reward,
            "penalty": penalty,
            "clarify_turns": penalty_info["clarify_turns"]
        })
    
    # 计算指标
    def compute_metrics(results):
        rewards = [r["reward"] for r in results]
        clarify_turns = [r["clarify_turns"] for r in results]
        
        return {
            "avg_reward": sum(rewards) / len(rewards) if rewards else 0,
            "avg_turns": sum(clarify_turns) / len(clarify_turns) if clarify_turns else 0,
            "over_clarification_rate": over_clarification_count / len(results) if results else 0
        }
    
    no_penalty_metrics = compute_metrics(no_penalty_results)
    with_penalty_metrics = compute_metrics(with_penalty_results)
    
    # 消融分析
    ablation_result = {
        "metadata": {
            "n_samples": len(samples),
            "alpha": penalty_system.alpha,
            "cap": penalty_system.cap,
            "over_clarification_samples": over_clarification_count,
            "total_clarify_turns": total_clarify_turns
        },
        "no_penalty": no_penalty_metrics,
        "with_penalty": with_penalty_metrics,
        "improvements": {
            "avg_reward_change": with_penalty_metrics["avg_reward"] - no_penalty_metrics["avg_reward"],
            "avg_turns_change": with_penalty_metrics["avg_turns"] - no_penalty_metrics["avg_turns"],
            "over_clarification_rate_change": 0.0  # 惩罚不会改变检测到的过度澄清率
        }
    }
    
    return ablation_result

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Over-Clarification Penalty - 过度澄清惩罚")
    parser.add_argument("--alpha", type=float, default=0.07, help="惩罚系数")
    parser.add_argument("--cap", type=int, default=3, help="惩罚上限")
    parser.add_argument("--ablation", action="store_true", help="运行消融研究")
    parser.add_argument("--test", action="store_true", help="运行单元测试")
    parser.add_argument("--output", help="输出文件路径")
    
    args = parser.parse_args()
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    if args.test:
        # 运行单元测试
        success = test_penalty_system()
        sys.exit(0 if success else 1)
    
    if args.ablation:
        try:
            # 加载样本数据进行消融研究
            from src.evaluation.shadow_run import ShadowRunEvaluator
            
            evaluator = ShadowRunEvaluator()
            samples = evaluator.load_or_generate_sample_data(50, 20250820)  # 使用较小样本测试
            
            penalty_system = OverClarificationPenalty(args.alpha, args.cap)
            
            print("🔬 过度澄清惩罚消融研究")
            print("=" * 50)
            
            # 运行消融研究
            ablation_result = run_ablation_study(penalty_system, samples)
            
            # 确定输出文件
            if not args.output:
                timestamp = time.strftime("%Y%m%d")
                args.output = f"reports/overclar_ablation_{timestamp}.json"
            
            # 保存结果
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(ablation_result, f, ensure_ascii=False, indent=2)
            
            # 打印结果
            print(f"📊 样本数量: {ablation_result['metadata']['n_samples']}")
            print(f"🚨 过度澄清样本: {ablation_result['metadata']['over_clarification_samples']}")
            print(f"📈 总澄清轮数: {ablation_result['metadata']['total_clarify_turns']}")
            
            print(f"\n📊 无惩罚指标:")
            no_penalty = ablation_result["no_penalty"]
            print(f"  平均奖励: {no_penalty['avg_reward']:.4f}")
            print(f"  平均轮数: {no_penalty['avg_turns']:.2f}")
            print(f"  过度澄清率: {no_penalty['over_clarification_rate']:.4f}")
            
            print(f"\n📊 有惩罚指标:")
            with_penalty = ablation_result["with_penalty"]
            print(f"  平均奖励: {with_penalty['avg_reward']:.4f}")
            print(f"  平均轮数: {with_penalty['avg_turns']:.2f}")
            print(f"  过度澄清率: {with_penalty['over_clarification_rate']:.4f}")
            
            improvements = ablation_result["improvements"]
            print(f"\n📈 改进情况:")
            print(f"  奖励变化: {improvements['avg_reward_change']:+.4f}")
            print(f"  轮数变化: {improvements['avg_turns_change']:+.2f}")
            
            print(f"\n📄 详细结果已保存: {output_path}")
            
        except Exception as e:
            logger.error(f"消融研究失败: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        # 仅运行单元测试
        success = test_penalty_system()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    import time
    main()
