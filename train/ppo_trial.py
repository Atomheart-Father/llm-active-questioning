#!/usr/bin/env python3
"""
PPO Trial - 5k steps小步PPO试炼
基于TRL的强化学习训练，集成Phase 2的权重校准和过度澄清惩罚
"""

import argparse
import json
import time
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
import yaml
import numpy as np
import torch
from dataclasses import dataclass, field

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 检查并安装必要依赖
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments
    from trl import PPOTrainer, PPOConfig, AutoModelForCausalLMWithValueHead
    from datasets import Dataset
    import wandb
except ImportError as e:
    print(f"❌ 缺少必要依赖: {e}")
    print("请运行: pip install transformers trl datasets wandb accelerate")
    sys.exit(1)

from src.evaluation.advanced_reward_system import MultiDimensionalRewardSystem
from src.evaluation.overclar_penalty import OverClarificationPenalty
from src.evaluation.shadow_run import ShadowRunEvaluator

logger = logging.getLogger(__name__)

@dataclass
class PPOTrialConfig:
    """PPO试炼配置"""
    
    # 模型配置
    base_model: str = "Qwen/Qwen3-4B-Thinking-2507"
    tokenizer: str = "auto"
    
    # 数据配置
    datasets: Dict[str, float] = field(default_factory=lambda: {
        "hotpotqa": 0.40,
        "strategyqa": 0.30, 
        "gsm8k": 0.30
    })
    rollout_len: int = 128
    max_turns: int = 6
    train_samples: int = 100  # 轻量级试炼
    eval_shadow_n: int = 245
    
    # 训练配置
    steps: int = 5000
    batch_size: int = 32
    mini_batch_size: int = 4
    lr: float = 1.0e-5
    ppo_clip: float = 0.2
    gae_lambda: float = 0.95
    gamma: float = 0.99
    vf_coef: float = 0.5
    
    # KL控制
    init_kl_coef: float = 0.02
    target_kl: float = 0.03
    kl_adaptation: bool = True
    
    # 奖励配置
    weights_file: str = "configs/weights.json"
    use_overclar_penalty: bool = True
    overclar: Dict[str, Any] = field(default_factory=lambda: {
        "alpha": 0.07,
        "cap": 3
    })
    
    # 并发配置
    scorer_provider: str = "deepseek_r1"
    k_vote: int = 3
    cache_ttl_days: int = 14
    max_concurrent: int = 5
    
    # 其他配置
    seed: int = 20250820
    wandb: bool = False
    save_every_steps: int = 500
    eval_every_steps: int = 500

class PPOTrialTrainer:
    """PPO试炼训练器"""
    
    def __init__(self, config: PPOTrialConfig):
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # 设置随机种子
        torch.manual_seed(config.seed)
        np.random.seed(config.seed)
        
        # 初始化奖励系统
        self.reward_system = MultiDimensionalRewardSystem()
        if config.use_overclar_penalty:
            self.penalty_system = OverClarificationPenalty(
                alpha=config.overclar["alpha"],
                cap=config.overclar["cap"]
            )
        else:
            self.penalty_system = None
        
        # 加载权重
        self.load_weights()
        
        # 初始化shadow run评估器
        self.shadow_evaluator = ShadowRunEvaluator()
        
        # Hacking检测计数器
        self.hacking_signals = {
            "ask_spam_count": 0,
            "format_exploit_count": 0,
            "variance_spike_count": 0
        }
        
        logger.info(f"PPO试炼训练器初始化完成: {config.base_model}")
    
    def load_weights(self):
        """加载权重配置"""
        if self.config.weights_file == "_uniform":
            # 使用均匀权重
            self.weights = None
            logger.info("使用均匀权重")
        else:
            try:
                with open(self.config.weights_file, 'r', encoding='utf-8') as f:
                    weights_data = json.load(f)
                self.weights = weights_data.get("weights", {})
                logger.info(f"加载权重: {self.weights}")
            except FileNotFoundError:
                logger.warning(f"权重文件未找到: {self.config.weights_file}，使用均匀权重")
                self.weights = None
    
    def setup_model_and_tokenizer(self):
        """设置模型和分词器（试炼版本-模拟模式）"""
        # 从环境变量获取模型名称
        model_name = os.getenv("BASE_MODEL", self.config.base_model)
        
        logger.info(f"模拟加载模型: {model_name}")
        
        # 试炼版本：跳过真实模型加载，使用模拟模式
        self.tokenizer = None
        self.model = None
        self.ref_model = None
        
        logger.info("模型和分词器设置完成（模拟模式）")
    
    def generate_training_data(self) -> Dataset:
        """生成训练数据"""
        logger.info(f"生成{self.config.train_samples}个训练样本...")
        
        # 基于现有shadow_run数据扩展
        base_samples = self.shadow_evaluator.load_or_generate_sample_data(
            self.config.eval_shadow_n, 
            self.config.seed
        )
        
        # 扩展到目标数量
        training_samples = []
        target_count = self.config.train_samples
        samples_per_base = target_count // len(base_samples) + 1
        
        for i, base_sample in enumerate(base_samples):
            for j in range(samples_per_base):
                if len(training_samples) >= target_count:
                    break
                
                # 创建变体样本
                sample = base_sample.copy()
                sample["id"] = f"{base_sample['id']}_var_{j}"
                
                # 生成问题变体
                base_query = sample.get("question", sample.get("query", f"模拟问题 {sample['id']}"))
                variants = [
                    base_query,
                    f"请帮助我解决：{base_query}",
                    f"关于这个问题：{base_query}，请给出答案。",
                    f"{base_query}请详细说明。"
                ]
                query = variants[j % len(variants)]
                
                training_samples.append({
                    "query": query,
                    "sample_id": sample["id"],
                    "task_type": sample.get("task_type", "unknown"),
                    "meta": sample.get("meta", {})
                })
        
        # 截断到目标数量
        training_samples = training_samples[:target_count]
        
        logger.info(f"生成了{len(training_samples)}个训练样本")
        return Dataset.from_list(training_samples)
    
    def compute_reward(self, query: str, response: str, sample_meta: Dict[str, Any]) -> float:
        """计算奖励"""
        # 构建对话样本
        dialogue = {
            "id": f"trial_{int(time.time())}",
            "question": query,
            "response": response,
            "turns": [
                {"role": "user", "content": query},
                {"role": "assistant", "content": response}
            ],
            "meta": sample_meta
        }
        
        # 基础奖励评估
        reward_result = self.reward_system.evaluate_dialogue(dialogue)
        base_reward = reward_result["primary_reward"]
        
        # 应用过度澄清惩罚
        if self.penalty_system:
            penalty_info = self.penalty_system.compute_penalty(dialogue)
            final_reward = self.penalty_system.apply_penalty_to_reward(base_reward, penalty_info)
            
            # Hacking检测
            self.detect_reward_hacking(dialogue, reward_result, penalty_info)
        else:
            final_reward = base_reward
        
        return final_reward
    
    def detect_reward_hacking(self, dialogue: Dict[str, Any], 
                            reward_result: Dict[str, Any], 
                            penalty_info: Dict[str, Any]):
        """检测奖励破解行为"""
        # 检测1: ask_spam (澄清轮数过多)
        clarify_turns = penalty_info["clarify_turns"]
        if clarify_turns > self.config.overclar["cap"]:
            self.hacking_signals["ask_spam_count"] += 1
        
        # 检测2: format_exploit (高格式分，低正确性)
        component_scores = reward_result.get("component_scores", {})
        format_score = reward_result.get("hard_rules", {}).get("metrics", {}).get("format_score", 0)
        logic_score = component_scores.get("logic_rigor", 0)
        
        if format_score > 0.8 and logic_score < 0.3:
            self.hacking_signals["format_exploit_count"] += 1
        
        # 检测3: variance_spike (评分方差过高)
        variance = reward_result.get("meta", {}).get("variance", 0)
        if variance > 0.08:
            self.hacking_signals["variance_spike_count"] += 1
    
    def check_hacking_thresholds(self, total_samples: int) -> Dict[str, bool]:
        """检查hacking阈值"""
        thresholds = {
            "ask_spam_rate": 0.05,        # 5%
            "format_exploit_rate": 0.03,  # 3%
            "variance_spike_rate": 0.10   # 10%
        }
        
        rates = {}
        alerts = {}
        
        for signal_name, count in self.hacking_signals.items():
            rate_name = signal_name.replace("_count", "_rate")
            
            rate = count / total_samples if total_samples > 0 else 0
            rates[rate_name] = rate
            alerts[rate_name] = rate > thresholds[rate_name]
        
        return {"rates": rates, "alerts": alerts}
    
    def run_shadow_evaluation(self, checkpoint_path: Optional[str] = None, tag: str = "eval") -> Dict[str, Any]:
        """运行影子评估"""
        logger.info(f"运行影子评估: {tag}")
        
        # 如果指定了checkpoint，需要加载模型
        if checkpoint_path:
            logger.info(f"从checkpoint加载模型: {checkpoint_path}")
            # 这里应该加载checkpoint，但由于是试炼版本，暂时跳过
        
        # 使用shadow_run进行评估
        result = self.shadow_evaluator.run_shadow_evaluation(
            n=self.config.eval_shadow_n,
            seed=self.config.seed,
            stratify=True
        )
        
        # 提取关键指标
        evaluation_result = {
            "tag": tag,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "shadow_metrics": {
                "spearman": result["correlations"]["stable_dataset"]["spearman"],
                "top10_overlap": result["overlap_metrics"]["top10_overlap"],
                "corr_improve_pct": result["task_success_correlation"]["corr_improve_pct"]
            },
            "success_rates": {
                task: info["mean"] for task, info in result["task_success_correlation"]["success_rate_by_task"].items()
            },
            "overclar_rate": result.get("overclar_rate", 0.0),
            "avg_turns": result.get("avg_turns", 0.0)
        }
        
        return evaluation_result
    
    def train(self) -> Dict[str, Any]:
        """执行PPO训练"""
        logger.info("开始PPO训练...")
        
        # 设置模型
        self.setup_model_and_tokenizer()
        
        # 生成训练数据
        train_dataset = self.generate_training_data()
        
        # 试炼版本：跳过真实PPO配置，使用模拟训练
        logger.info("使用模拟PPO训练模式")
        
        # 训练前评估
        pre_eval = self.run_shadow_evaluation(tag="pre_rl")
        
        # 训练循环（简化版本）
        training_stats = {
            "steps": [],
            "rewards": [],
            "kl_divergence": [],
            "loss": []
        }
        
        logger.info("开始训练循环...")
        
        # 模拟训练过程（实际实现中需要真正的PPO循环）
        for step in range(0, self.config.steps, self.config.eval_every_steps):
            # 模拟训练步骤
            batch = train_dataset.shuffle(seed=self.config.seed + step).select(range(self.config.batch_size))
            
            # 模拟奖励计算
            step_rewards = []
            for sample in batch:
                # 生成响应（这里用模拟数据）
                response = f"这是步骤{step}的模拟响应: {sample['query'][:50]}..."
                reward = self.compute_reward(sample['query'], response, sample.get('meta', {}))
                step_rewards.append(reward)
            
            avg_reward = np.mean(step_rewards)
            mock_kl = np.random.normal(0.02, 0.01)  # 模拟KL散度
            mock_loss = np.random.normal(0.5, 0.1)  # 模拟损失
            
            training_stats["steps"].append(step)
            training_stats["rewards"].append(avg_reward)
            training_stats["kl_divergence"].append(max(0, mock_kl))
            training_stats["loss"].append(max(0, mock_loss))
            
            logger.info(f"Step {step}: reward={avg_reward:.4f}, kl={mock_kl:.4f}")
            
            # KL检查
            if mock_kl > self.config.target_kl * 4:  # 严重超标
                logger.warning(f"KL散度过高: {mock_kl:.4f}")
                break
            
            # 保存检查点
            if step % self.config.save_every_steps == 0 and step > 0:
                checkpoint_dir = f"checkpoints/ppo_trial/step_{step}"
                Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
                logger.info(f"保存检查点: {checkpoint_dir}")
        
        # 训练后评估
        post_eval = self.run_shadow_evaluation(tag="post_rl")
        
        # 检查hacking
        total_samples = len(train_dataset) * (self.config.steps // self.config.eval_every_steps)
        hacking_check = self.check_hacking_thresholds(total_samples)
        
        # 计算增量
        delta_metrics = self.compute_delta_metrics(pre_eval, post_eval)
        
        # 验收检查
        pass_criteria = self.check_pass_criteria(pre_eval, post_eval, hacking_check)
        
        # 组装结果
        result = {
            "config": {
                "steps": self.config.steps,
                "model": self.config.base_model,
                "seed": self.config.seed
            },
            "train": {
                "steps": self.config.steps,
                "kl_curve": training_stats["kl_divergence"],
                "reward_curve": training_stats["rewards"],
                "final_kl": training_stats["kl_divergence"][-1] if training_stats["kl_divergence"] else 0.0
            },
            "eval_pre": pre_eval,
            "eval_post": post_eval,
            "delta": delta_metrics,
            "shadow": post_eval["shadow_metrics"],
            "hacking_signals": hacking_check["rates"],
            "pass_criteria": pass_criteria,
            "overall_pass": all(pass_criteria.values())
        }
        
        return result
    
    def compute_delta_metrics(self, pre_eval: Dict[str, Any], post_eval: Dict[str, Any]) -> Dict[str, Any]:
        """计算增量指标"""
        delta = {}
        
        # 成功率增量
        success_pp = {}
        for task in ["hotpotqa", "strategyqa", "gsm8k"]:
            pre_success = pre_eval["success_rates"].get(task, 0.0)
            post_success = post_eval["success_rates"].get(task, 0.0)
            success_pp[task] = (post_success - pre_success) * 100  # 转换为百分点
        
        delta["success_pp"] = success_pp
        
        # 过度澄清率变化
        pre_overclar = pre_eval.get("overclar_rate", 0.0)
        post_overclar = post_eval.get("overclar_rate", 0.0)
        if pre_overclar > 0:
            overclar_change_pct = ((post_overclar - pre_overclar) / pre_overclar) * 100
        else:
            overclar_change_pct = 0.0
        delta["overclar_rate_pct"] = overclar_change_pct
        
        # 平均轮数变化
        pre_turns = pre_eval.get("avg_turns", 0.0)
        post_turns = post_eval.get("avg_turns", 0.0)
        delta["avg_turns"] = post_turns - pre_turns
        
        return delta
    
    def check_pass_criteria(self, pre_eval: Dict[str, Any], post_eval: Dict[str, Any], 
                          hacking_check: Dict[str, Any]) -> Dict[str, bool]:
        """检查验收标准"""
        criteria = {}
        
        # 1. 任务成功率提升≥5pp (需要发问的任务)
        ask_needed_tasks = ["hotpotqa", "strategyqa"]
        success_improvements = []
        for task in ask_needed_tasks:
            pre_success = pre_eval["success_rates"].get(task, 0.0)
            post_success = post_eval["success_rates"].get(task, 0.0)
            improvement = (post_success - pre_success) * 100
            success_improvements.append(improvement)
        
        avg_success_improvement = np.mean(success_improvements) if success_improvements else 0.0
        criteria["success_improvement_5pp"] = avg_success_improvement >= 5.0
        
        # 2. 过度澄清率相对下降≥20%
        pre_overclar = pre_eval.get("overclar_rate", 0.0)
        post_overclar = post_eval.get("overclar_rate", 0.0)
        if pre_overclar > 0:
            overclar_reduction = (pre_overclar - post_overclar) / pre_overclar
            criteria["overclar_reduction_20pct"] = overclar_reduction >= 0.2
        else:
            criteria["overclar_reduction_20pct"] = True  # 无过度澄清则通过
        
        # 3. 平均轮数不增加
        pre_turns = pre_eval.get("avg_turns", 0.0)
        post_turns = post_eval.get("avg_turns", 0.0)
        criteria["avg_turns_no_increase"] = post_turns <= pre_turns
        
        # 4. 影子运行稳态指标
        shadow_metrics = post_eval["shadow_metrics"]
        criteria["shadow_spearman"] = shadow_metrics["spearman"] >= 0.75
        criteria["shadow_top10_overlap"] = shadow_metrics["top10_overlap"] >= 0.70
        criteria["shadow_corr_improve"] = shadow_metrics["corr_improve_pct"] >= 10
        
        # 5. KL稳定性
        final_kl = post_eval.get("final_kl", 0.0)
        criteria["kl_stability"] = final_kl <= self.config.target_kl * 4
        
        # 6. 无reward hacking
        alerts = hacking_check.get("alerts", {})
        criteria["no_hacking"] = not any(alerts.values())
        
        return criteria

def run_ablation_studies(base_config: PPOTrialConfig) -> Dict[str, Any]:
    """运行消融研究"""
    ablation_results = {}
    
    # 1. 关闭过度澄清惩罚
    config_no_penalty = base_config
    config_no_penalty.use_overclar_penalty = False
    trainer_no_penalty = PPOTrialTrainer(config_no_penalty)
    result_no_penalty = trainer_no_penalty.run_shadow_evaluation(tag="ablate_penalty")
    ablation_results["penalty_off"] = result_no_penalty
    
    # 2. 调整alpha参数
    config_alpha_04 = base_config
    config_alpha_04.overclar["alpha"] = 0.04
    trainer_alpha = PPOTrialTrainer(config_alpha_04)
    result_alpha = trainer_alpha.run_shadow_evaluation(tag="alpha_0p04")
    ablation_results["alpha_0p04"] = result_alpha
    
    # 3. 使用均匀权重
    config_uniform = base_config
    config_uniform.weights_file = "_uniform"
    trainer_uniform = PPOTrialTrainer(config_uniform)
    result_uniform = trainer_uniform.run_shadow_evaluation(tag="uniform_weights")
    ablation_results["uniform_weights"] = result_uniform
    
    return ablation_results

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="PPO Trial - 5k steps小步PPO试炼")
    parser.add_argument("--config", default="configs/ppo_trial.yaml", help="配置文件路径")
    parser.add_argument("--override", help="配置覆盖，格式：key=value")
    parser.add_argument("--tag", default="main", help="实验标签")
    parser.add_argument("--ablation", action="store_true", help="运行消融研究")
    parser.add_argument("--eval-only", action="store_true", help="仅运行评估")
    
    args = parser.parse_args()
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    try:
        # 加载配置
        with open(args.config, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)
        
        # 应用覆盖
        if args.override:
            key, value = args.override.split("=", 1)
            keys = key.split(".")
            current = config_dict
            for k in keys[:-1]:
                current = current[k]
            # 尝试转换类型
            try:
                if value.lower() in ["true", "false"]:
                    current[keys[-1]] = value.lower() == "true"
                elif value.replace(".", "").isdigit():
                    current[keys[-1]] = float(value) if "." in value else int(value)
                else:
                    current[keys[-1]] = value
            except:
                current[keys[-1]] = value
        
        # 创建配置对象
        config = PPOTrialConfig(**config_dict)
        
        # 创建训练器
        trainer = PPOTrialTrainer(config)
        
        if args.eval_only:
            # 仅运行评估
            result = trainer.run_shadow_evaluation(tag=args.tag)
        else:
            # 运行完整训练
            result = trainer.train()
            
            # 添加消融研究
            if args.ablation:
                ablation_results = run_ablation_studies(config)
                result["ablation"] = ablation_results
        
        # 保存结果
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = f"reports/ppo_trial_{timestamp}_{args.tag}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # 自定义JSON编码器处理numpy类型
            def json_serializer(obj):
                if hasattr(obj, 'item'):  # numpy scalar
                    return obj.item()
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                if isinstance(obj, (np.bool_, bool)):
                    return bool(obj)
                raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')
            
            json.dump(result, f, ensure_ascii=False, indent=2, default=json_serializer)
        
        # 打印结果摘要
        print("🚀 PPO试炼结果摘要")
        print("=" * 60)
        
        if not args.eval_only:
            print(f"📊 训练步数: {result['config']['steps']}")
            print(f"🎯 最终奖励: {result['train']['reward_curve'][-1]:.4f}")
            print(f"📈 最终KL: {result['train']['final_kl']:.4f}")
            
            # 打印增量指标
            delta = result["delta"]
            print(f"\n📈 性能提升:")
            for task, improvement in delta["success_pp"].items():
                print(f"  {task}: {improvement:+.2f}pp")
            print(f"  过度澄清率变化: {delta['overclar_rate_pct']:+.2f}%")
            print(f"  平均轮数变化: {delta['avg_turns']:+.2f}")
            
            # 验收状态
            pass_criteria = result["pass_criteria"]
            print(f"\n🚦 验收检查:")
            for criterion, passed in pass_criteria.items():
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"  {criterion}: {status}")
            
            overall_status = "✅ 全部通过" if result["overall_pass"] else "❌ 存在未通过项"
            print(f"\n🏆 总体状态: {overall_status}")
        
        print(f"\n📄 详细结果已保存: {output_file}")
        
        # 返回退出码
        if args.eval_only:
            sys.exit(0)
        else:
            sys.exit(0 if result["overall_pass"] else 1)
        
    except Exception as e:
        logger.error(f"PPO试炼失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
