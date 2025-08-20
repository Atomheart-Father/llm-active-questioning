#!/usr/bin/env python3
"""
Shadow Run - 影子运行对比系统
对同一批样本并行计算新旧评分系统，进行排名与相关性分析
"""

import argparse
import json
import time
import random
from pathlib import Path
from typing import Dict, List, Any, Tuple
import numpy as np
from scipy.stats import spearmanr, kendalltau
import yaml
import sys
import logging

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.evaluation.advanced_reward_system import MultiDimensionalRewardSystem
from src.evaluation.diversity_metrics import DiversityMetrics

logger = logging.getLogger(__name__)

class ShadowRunEvaluator:
    """影子运行评估器"""
    
    def __init__(self, config_path: str = "configs/default_config.yaml"):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 初始化评估系统
        self.new_reward_system = MultiDimensionalRewardSystem()
        
        # 创建输出目录
        Path("reports").mkdir(exist_ok=True)
        Path("data").mkdir(exist_ok=True)
        
        logger.info("Shadow Run评估器初始化完成")
    
    def generate_stratified_sample(self, n: int = 245, seed: int = 20250820) -> List[Dict[str, Any]]:
        """生成分层抽样的评估样本"""
        random.seed(seed)
        np.random.seed(seed)
        
        # 每类任务的样本数 (约等分)
        samples_per_task = n // 3
        remainder = n % 3
        
        task_samples = {
            "math": samples_per_task + (1 if remainder > 0 else 0),
            "multihop": samples_per_task + (1 if remainder > 1 else 0), 
            "clarify": samples_per_task
        }
        
        logger.info(f"生成分层样本: {task_samples}")
        
        # 生成样本数据
        all_samples = []
        
        for task_type, count in task_samples.items():
            for i in range(count):
                sample = self._generate_sample_for_task(task_type, i, seed)
                all_samples.append(sample)
        
        # 随机打乱
        random.shuffle(all_samples)
        
        logger.info(f"生成了{len(all_samples)}个样本")
        return all_samples
    
    def _generate_sample_for_task(self, task_type: str, index: int, seed: int) -> Dict[str, Any]:
        """为特定任务类型生成样本"""
        sample_id = f"{task_type}_{seed}_{index:03d}"
        
        if task_type == "math":
            return {
                "id": sample_id,
                "task_type": "math",
                "turns": [
                    {"role": "user", "content": f"一个长方形的长是{5+index}厘米，宽是{3+index//2}厘米，面积是多少？"},
                    {"role": "assistant", "content": f"<think>长方形面积=长×宽，所以面积={5+index}×{3+index//2}={(5+index)*(3+index//2)}平方厘米。</think>\n\n计算步骤：\n1. 确定公式：面积 = 长 × 宽\n2. 代入数值：面积 = {5+index} × {3+index//2}\n3. 计算结果：面积 = {(5+index)*(3+index//2)}平方厘米\n\n答案：{(5+index)*(3+index//2)}平方厘米"}
                ],
                "ground_truth": {
                    "correct_answer": (5+index)*(3+index//2),
                    "task_success": True,
                    "reasoning_steps": 3
                },
                "meta": {"template_id": "math_formal_teacher", "needs_clarification": False}
            }
        
        elif task_type == "multihop":
            countries = ["法国", "德国", "意大利", "西班牙", "英国"]
            capitals = ["巴黎", "柏林", "罗马", "马德里", "伦敦"]
            country = countries[index % len(countries)]
            capital = capitals[index % len(capitals)]
            
            return {
                "id": sample_id,
                "task_type": "multihop", 
                "turns": [
                    {"role": "user", "content": f"{country}的首都是什么？这个城市有什么著名景点？"},
                    {"role": "assistant", "content": f"让我分步回答这个问题：\n\n第一步：{country}的首都\n{country}的首都是{capital}。\n\n第二步：{capital}的著名景点\n{capital}有许多世界闻名的景点，包括历史建筑、博物馆和文化地标。\n\n综合答案：{country}的首都是{capital}，这座城市拥有丰富的历史文化景点。"}
                ],
                "ground_truth": {
                    "correct_answer": {"capital": capital, "has_landmarks": True},
                    "task_success": True,
                    "reasoning_hops": 2
                },
                "meta": {"template_id": "multihop_systematic", "needs_clarification": False}
            }
        
        elif task_type == "clarify":
            ambiguous_queries = [
                "他什么时候来的？",
                "这个怎么用？", 
                "价格是多少？",
                "在哪里可以找到？",
                "需要多长时间？"
            ]
            query = ambiguous_queries[index % len(ambiguous_queries)]
            
            return {
                "id": sample_id,
                "task_type": "clarify",
                "turns": [
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": f"我需要更多信息来准确回答您的问题。\\n\\n关于\"{query}\"，我想了解：\\n1. 您指的具体是什么/谁？\\n2. 您希望了解哪个方面的信息？\\n3. 这是在什么场景下的问题？\\n\\n请提供这些细节，我将为您提供精确的答案。"}
                ],
                "ground_truth": {
                    "correct_behavior": "ask_clarification",
                    "task_success": True,
                    "clarification_points": 3
                },
                "meta": {"template_id": "clarify_polite_assistant", "needs_clarification": True}
            }
        
        else:
            raise ValueError(f"未知任务类型: {task_type}")
    
    def load_or_generate_sample_data(self, n: int, seed: int, data_file: str = "data/shadow_eval_245.jsonl") -> List[Dict[str, Any]]:
        """加载或生成样本数据"""
        data_path = Path(data_file)
        
        if data_path.exists():
            logger.info(f"从文件加载样本: {data_file}")
            samples = []
            with open(data_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        samples.append(json.loads(line))
            
            if len(samples) == n:
                return samples
            else:
                logger.warning(f"文件中样本数({len(samples)})与需求不符({n})，重新生成")
        
        # 生成新样本
        logger.info(f"生成新的样本数据: {n}条")
        samples = self.generate_stratified_sample(n, seed)
        
        # 保存到文件
        data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(data_path, 'w', encoding='utf-8') as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        logger.info(f"样本数据已保存: {data_file}")
        return samples
    
    def evaluate_with_old_system(self, sample: Dict[str, Any]) -> Dict[str, float]:
        """使用旧的7维评分系统"""
        # 这里实现旧的7维评分逻辑
        # 暂时使用启发式规则模拟
        
        task_type = sample.get("task_type", "unknown")
        dialogue_text = self._extract_dialogue_text(sample)
        
        # 基础评分
        scores = {
            "logic_rigor": 0.75,
            "calc_accuracy": 0.70,
            "expression_clarity": 0.72,
            "completeness": 0.68,
            "clarification": 0.65,
            "naturalness": 0.70,
            "educational": 0.67
        }
        
        # 根据任务类型调整
        if task_type == "math":
            if "think" in dialogue_text:
                scores["logic_rigor"] += 0.15
            if "步骤" in dialogue_text:
                scores["completeness"] += 0.15
            if "=" in dialogue_text:
                scores["calc_accuracy"] += 0.20
        
        elif task_type == "clarify":
            if "?" in dialogue_text or "？" in dialogue_text:
                scores["clarification"] += 0.25
            if "请" in dialogue_text or "您" in dialogue_text:
                scores["naturalness"] += 0.15
        
        elif task_type == "multihop":
            if "第一" in dialogue_text and "第二" in dialogue_text:
                scores["completeness"] += 0.20
            if "步骤" in dialogue_text or "分步" in dialogue_text:
                scores["logic_rigor"] += 0.15
        
        # 确保分数在合理范围
        for key in scores:
            scores[key] = max(0.0, min(1.0, scores[key]))
        
        # 计算加权总分 (旧权重)
        old_weights = {
            "logic_rigor": 0.20,
            "calc_accuracy": 0.20, 
            "expression_clarity": 0.15,
            "completeness": 0.15,
            "clarification": 0.10,
            "naturalness": 0.10,
            "educational": 0.10
        }
        
        total_score = sum(scores[key] * old_weights[key] for key in scores)
        scores["total_score"] = total_score
        
        return scores
    
    def evaluate_with_new_system(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """使用新的奖励系统评估"""
        return self.new_reward_system.evaluate_dialogue(sample)
    
    def calculate_task_success_correlation(self, samples: List[Dict], old_scores: List[float], new_scores: List[float]) -> Tuple[float, float]:
        """计算与任务成功率的相关性"""
        # 提取真实的任务成功标签
        success_labels = []
        for sample in samples:
            ground_truth = sample.get("ground_truth", {})
            task_success = ground_truth.get("task_success", False)
            success_labels.append(1.0 if task_success else 0.0)
        
        if len(set(success_labels)) < 2:
            # 所有样本都成功或都失败，无法计算相关性
            return 0.0, 0.0
        
        # 计算相关性
        old_corr, _ = spearmanr(old_scores, success_labels)
        new_corr, _ = spearmanr(new_scores, success_labels)
        
        return old_corr or 0.0, new_corr or 0.0
    
    def _compute_task_success(self, sample: Dict[str, Any]) -> int:
        """统一的任务成功定义"""
        ground_truth = sample.get("ground_truth", {})
        task_type = sample.get("task_type", "unknown")
        
        # 统一成功标准
        if task_type == "math":
            # 数学题：精确匹配
            return 1 if ground_truth.get("task_success", False) else 0
        elif task_type == "multihop":
            # 多跳推理：逻辑完整性
            return 1 if ground_truth.get("task_success", False) else 0
        elif task_type == "clarify":
            # 澄清任务：是否正确识别需要澄清
            return 1 if ground_truth.get("task_success", False) else 0
        else:
            return 0
    
    def run_shadow_evaluation(self, n: int = 245, seed: int = 20250820, stratify: bool = True) -> Dict[str, Any]:
        """执行影子运行评估"""
        logger.info(f"开始影子运行评估: n={n}, seed={seed}, stratify={stratify}")
        
        # 1. 加载或生成样本
        samples = self.load_or_generate_sample_data(n, seed)
        
        # 2. 并行评估 - 使用DataFrame确保对齐
        import pandas as pd
        from scipy.stats import rankdata
        
        eval_data = []
        unstable_samples = []
        
        for i, sample in enumerate(samples):
            logger.info(f"评估样本 {i+1}/{len(samples)}: {sample['id']}")
            
            # 旧系统评分
            old_result = self.evaluate_with_old_system(sample)
            old_score = old_result["total_score"]
            
            # 新系统评分
            new_result = self.evaluate_with_new_system(sample)
            new_score = new_result["primary_reward"]
            
            # 任务成功标签
            task_success = self._compute_task_success(sample)
            
            # 检查不稳定样本
            variance = new_result.get("meta", {}).get("variance", 0.0)
            is_unstable = variance > 0.08
            if is_unstable:
                unstable_samples.append({
                    "id": sample["id"],
                    "variance": variance,
                    "task_type": sample.get("task_type")
                })
            
            eval_data.append({
                "sample_id": sample["id"],
                "task_type": sample.get("task_type", "unknown"),
                "old_score": old_score,
                "new_score": new_score,
                "task_success": task_success,
                "variance": variance,
                "is_unstable": is_unstable,
                "stable_weight": 0.5 if is_unstable else 1.0
            })
        
        # 转换为DataFrame确保对齐
        df = pd.DataFrame(eval_data)
        
        # 断言检查
        assert len(df) == n, f"样本数不匹配: 期望{n}, 实际{len(df)}"
        assert df['old_score'].std() > 0, "旧分数无变化，检查评分逻辑"
        assert df['new_score'].std() > 0, "新分数无变化，检查评分逻辑"
        
        # 归一化确保量纲一致 (min-max到[0,1])
        df['old_score_norm'] = (df['old_score'] - df['old_score'].min()) / (df['old_score'].max() - df['old_score'].min())
        df['new_score_norm'] = (df['new_score'] - df['new_score'].min()) / (df['new_score'].max() - df['new_score'].min())
        
        # 使用归一化分数进行后续分析
        old_scores = df['old_score_norm'].values
        new_scores = df['new_score_norm'].values
        
        # 3. 计算基于秩的相关性 - 处理并列
        old_ranks = rankdata(old_scores, method="average")
        new_ranks = rankdata(new_scores, method="average")
        
        # 计算并列比例
        old_ties_ratio = 1 - len(np.unique(old_ranks)) / len(old_ranks)
        new_ties_ratio = 1 - len(np.unique(new_ranks)) / len(new_ranks)
        
        if old_ties_ratio > 0.2 or new_ties_ratio > 0.2:
            logger.warning(f"检测到高并列比例: old={old_ties_ratio:.3f}, new={new_ties_ratio:.3f}")
        
        # 相关性计算
        spearman_corr, spearman_p = spearmanr(old_ranks, new_ranks)
        kendall_tau, kendall_p = kendalltau(old_ranks, new_ranks)
        
        # 双向sanity check - 检查方向是否颠倒
        spearman_neg, _ = spearmanr(old_ranks, -new_ranks)
        direction_reversed = abs(spearman_neg) > abs(spearman_corr) + 0.1
        
        if direction_reversed:
            logger.error(f"疑似方向颠倒! 正向:{spearman_corr:.4f} vs 反向:{spearman_neg:.4f}")
        
        # 稳定版本计算 (剔除不稳定样本)
        stable_mask = df['stable_weight'] == 1.0
        stable_df = df[stable_mask] if stable_mask.sum() > 5 else df  # 至少保留5个样本
        
        stable_old_ranks = rankdata(stable_df['old_score_norm'], method="average")
        stable_new_ranks = rankdata(stable_df['new_score_norm'], method="average")
        stable_spearman, _ = spearmanr(stable_old_ranks, stable_new_ranks) if len(stable_df) > 1 else (0.0, 1.0)
        
        # 4. 计算Top-K重合度 - 修复版本，按sample_id对齐
        def get_top_k_overlap_fixed(df_input, k_pct, old_col='old_score_norm', new_col='new_score_norm'):
            k = max(1, int(len(df_input) * k_pct / 100))
            
            # 按分数降序排序，取前K个sample_id
            top_k_old = set(df_input.nlargest(k, old_col)['sample_id'].values)
            top_k_new = set(df_input.nlargest(k, new_col)['sample_id'].values)
            
            overlap = len(top_k_old & top_k_new)
            return overlap / k, top_k_old, top_k_new
        
        # 计算多个K值的重合度
        overlap_results = {}
        top_lists = {}
        
        for k_pct in [5, 10, 20, 50]:
            overlap, top_old, top_new = get_top_k_overlap_fixed(df, k_pct)
            overlap_results[f"top{k_pct}_overlap"] = overlap
            if k_pct in [10, 20]:  # 保存详细列表用于调试
                top_lists[f"top{k_pct}"] = {
                    "old_ids": list(top_old),
                    "new_ids": list(top_new), 
                    "intersection": list(top_old & top_new)
                }
        
        # 5. 计算与任务成功率的相关性 - 使用DataFrame数据
        success_labels = df['task_success'].values
        success_rate_by_task = df.groupby('task_type')['task_success'].agg(['mean', 'count']).to_dict('index')
        
        # 检查成功率分布
        overall_success_rate = df['task_success'].mean()
        if overall_success_rate == 0.0 or overall_success_rate == 1.0:
            logger.warning(f"成功率极端: {overall_success_rate:.3f}, 相关性计算可能不准确")
        
        # 计算相关性
        if len(np.unique(success_labels)) > 1:  # 有变化才计算
            old_success_corr, _ = spearmanr(old_ranks, success_labels)
            new_success_corr, _ = spearmanr(new_ranks, success_labels)
        else:
            old_success_corr = new_success_corr = 0.0
        
        # 计算改进百分比
        if abs(old_success_corr) > 0.001:
            corr_improve_pct = ((new_success_corr - old_success_corr) / abs(old_success_corr)) * 100
        else:
            corr_improve_pct = 0.0
        
        # 6. 按任务类型统计
        by_task_stats = {}
        for task_type in df['task_type'].unique():
            task_df = df[df['task_type'] == task_type]
            if len(task_df) > 1:
                task_old_ranks = rankdata(task_df['old_score_norm'], method="average")
                task_new_ranks = rankdata(task_df['new_score_norm'], method="average")
                task_spearman, _ = spearmanr(task_old_ranks, task_new_ranks) if len(task_df) > 1 else (0.0, 1.0)
                
                by_task_stats[task_type] = {
                    "count": len(task_df),
                    "spearman": task_spearman or 0.0,
                    "old_mean": task_df['old_score_norm'].mean(),
                    "new_mean": task_df['new_score_norm'].mean(),
                    "old_std": task_df['old_score_norm'].std(),
                    "new_std": task_df['new_score_norm'].std(),
                    "success_rate": task_df['task_success'].mean(),
                    "unstable_rate": task_df['is_unstable'].mean()
                }
        
        # 生成Top-10诊断列表
        top10_df = df.nlargest(10, 'old_score_norm')[['sample_id', 'old_score_norm', 'new_score_norm', 'task_type']]
        top10_old_list = top10_df.to_dict('records')
        
        top10_new_df = df.nlargest(10, 'new_score_norm')[['sample_id', 'old_score_norm', 'new_score_norm', 'task_type']]
        top10_new_list = top10_new_df.to_dict('records')
        
        # 保存样本清单用于复现
        sample_manifest = {
            "seed": seed,
            "stratified": stratify,
            "task_distribution": df['task_type'].value_counts().to_dict(),
            "samples": df[['sample_id', 'task_type']].to_dict('records')
        }
        
        # 7. 构建完整结果
        result = {
            "metadata": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "n": len(df),
                "seed": seed,
                "stratified": stratify,
                "stable_samples": len(stable_df),
                "unstable_samples": len(df) - len(stable_df)
            },
            "correlations": {
                "full_dataset": {
                    "spearman": round(spearman_corr or 0.0, 4),
                    "spearman_p": round(spearman_p or 1.0, 4),
                    "kendall_tau": round(kendall_tau or 0.0, 4),
                    "kendall_p": round(kendall_p or 1.0, 4)
                },
                "stable_dataset": {
                    "spearman": round(stable_spearman or 0.0, 4),
                    "stable_samples": len(stable_df)
                }
            },
            "overlap_metrics": overlap_results,
            "task_success_correlation": {
                "corr_to_success_old": round(old_success_corr, 4),
                "corr_to_success_new": round(new_success_corr, 4),
                "corr_improve_pct": round(corr_improve_pct, 2),
                "overall_success_rate": round(overall_success_rate, 4),
                "success_rate_by_task": success_rate_by_task
            },
            "score_distribution": {
                "old_scores_normalized": {
                    "mean": round(np.mean(old_scores), 4),
                    "std": round(np.std(old_scores), 4),
                    "min": round(np.min(old_scores), 4),
                    "max": round(np.max(old_scores), 4)
                },
                "new_scores_normalized": {
                    "mean": round(np.mean(new_scores), 4),
                    "std": round(np.std(new_scores), 4),
                    "min": round(np.min(new_scores), 4),
                    "max": round(np.max(new_scores), 4)
                }
            },
            "by_task": by_task_stats,
            "unstable_samples": unstable_samples,
            "quality_metrics": {
                "unstable_rate": round(len(unstable_samples) / len(df), 4),
                "avg_variance": round(np.mean([s["variance"] for s in unstable_samples]) if unstable_samples else 0.0, 4),
                "ties_ratio": {
                    "old": round(old_ties_ratio, 4),
                    "new": round(new_ties_ratio, 4)
                }
            },
            "diagnostics": {
                "direction_check": {
                    "spearman_positive": round(spearman_corr or 0.0, 4),
                    "spearman_negative": round(spearman_neg or 0.0, 4),
                    "direction_reversed": direction_reversed
                },
                "top10_lists": {
                    "by_old_score": top10_old_list,
                    "by_new_score": top10_new_list
                },
                "top_k_details": top_lists,
                "sample_manifest": sample_manifest
            }
        }
        
        return result
    
    def check_thresholds(self, result: Dict[str, Any]) -> Dict[str, bool]:
        """检查验收门槛 - 基于稳定版本"""
        gate_config = self.config.get("shadow_gate", {})
        
        # 优先使用稳定版本的指标
        stable_spearman = result["correlations"]["stable_dataset"]["spearman"]
        top10_overlap = result["overlap_metrics"].get("top10_overlap", 0.0)
        corr_improve_pct = result["task_success_correlation"]["corr_improve_pct"]
        
        # 检查是否有方向颠倒问题
        direction_ok = not result["diagnostics"]["direction_check"]["direction_reversed"]
        
        checks = {
            "spearman_pass": stable_spearman >= gate_config.get("spearman_min", 0.75),
            "top10_overlap_pass": top10_overlap >= gate_config.get("top10_overlap_min", 0.70),
            "corr_improve_pass": corr_improve_pct >= gate_config.get("corr_improve_pct", 10),
            "direction_check_pass": direction_ok
        }
        
        checks["overall_pass"] = all(checks.values())
        
        # 添加阈值信息
        checks["thresholds_used"] = gate_config
        checks["actual_values"] = {
            "stable_spearman": stable_spearman,
            "top10_overlap": top10_overlap,
            "corr_improve_pct": corr_improve_pct,
            "direction_ok": direction_ok
        }
        
        return checks
    
    def _extract_dialogue_text(self, sample: Dict) -> str:
        """提取对话文本"""
        if "turns" in sample:
            parts = []
            for turn in sample["turns"]:
                if isinstance(turn, dict) and "content" in turn:
                    parts.append(turn["content"])
            return " ".join(parts)
        elif "content" in sample:
            return sample["content"]
        else:
            return str(sample)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Shadow Run - 影子运行对比")
    parser.add_argument("--n", type=int, default=245, help="样本数量")
    parser.add_argument("--seed", type=int, default=20250820, help="随机种子")
    parser.add_argument("--stratify", action="store_true", default=True, help="是否分层抽样")
    parser.add_argument("--config", default="configs/default_config.yaml", help="配置文件路径")
    parser.add_argument("--output", help="输出文件路径")
    parser.add_argument("--materialize", help="物化样本到指定文件")
    parser.add_argument("--dump-manifest", dest="dump_manifest", help="输出样本清单到指定文件")
    parser.add_argument("--tag", default="shadow_run", help="运行标签")
    
    args = parser.parse_args()
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    try:
        # 创建评估器
        evaluator = ShadowRunEvaluator(args.config)
        
        # 如果需要物化样本，先生成并保存
        if args.materialize:
            logger.info(f"物化样本到: {args.materialize}")
            if args.stratify:
                samples = evaluator.generate_stratified_sample(args.n, args.seed)
            else:
                samples = evaluator.load_or_generate_sample_data(args.n, args.seed)
            
            # 保存样本
            materialize_path = Path(args.materialize)
            materialize_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(materialize_path, 'w', encoding='utf-8') as f:
                for sample in samples:
                    f.write(json.dumps(sample, ensure_ascii=False) + '\n')
            
            logger.info(f"已物化 {len(samples)} 个样本")
            
            # 如果需要生成manifest
            if args.dump_manifest:
                manifest = {
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'total_samples': len(samples),
                    'seed': args.seed,
                    'stratified': args.stratify,
                    'tasks': {},
                    'samples': []
                }
                
                # 统计任务分布
                from collections import Counter
                task_counts = Counter()
                for sample in samples:
                    task = sample.get('task', 'unknown')
                    task_counts[task] += 1
                    manifest['samples'].append({
                        'id': sample.get('id', ''),
                        'task': task,
                        'question': sample.get('question', '')[:100] + '...' if len(sample.get('question', '')) > 100 else sample.get('question', '')
                    })
                
                manifest['tasks'] = dict(task_counts)
                
                manifest_path = Path(args.dump_manifest)
                manifest_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, ensure_ascii=False, indent=2)
                
                logger.info(f"样本清单保存到: {manifest_path}")
        
        # 执行评估
        result = evaluator.run_shadow_evaluation(args.n, args.seed, args.stratify)
        
        # 检查门槛
        threshold_checks = evaluator.check_thresholds(result)
        result["threshold_checks"] = threshold_checks
        
        # 确定输出文件
        if not args.output:
            timestamp = time.strftime("%Y%m%d")
            args.output = f"reports/shadow_run_{timestamp}.json"
        
        # 保存结果
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 自定义JSON编码器处理numpy类型
        def json_serializer(obj):
            if hasattr(obj, 'item'):  # numpy scalar
                return obj.item()
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=json_serializer)
        
        # 打印结果
        print("🩺 Shadow Run体检报告")
        print("=" * 60)
        print(f"📊 样本数量: {result['metadata']['n']} (稳定: {result['metadata']['stable_samples']}, 不稳定: {result['metadata']['unstable_samples']})")
        print(f"📈 Spearman相关性: 全量={result['correlations']['full_dataset']['spearman']:.4f}, 稳定版={result['correlations']['stable_dataset']['spearman']:.4f}")
        print(f"🎯 Top-K重合度: Top5={result['overlap_metrics'].get('top5_overlap', 0):.4f}, Top10={result['overlap_metrics'].get('top10_overlap', 0):.4f}, Top20={result['overlap_metrics'].get('top20_overlap', 0):.4f}")
        print(f"📊 任务成功相关性: 旧={result['task_success_correlation']['corr_to_success_old']:.4f}, 新={result['task_success_correlation']['corr_to_success_new']:.4f}, 改进={result['task_success_correlation']['corr_improve_pct']:.2f}%")
        print(f"⚠️  质量指标: 不稳定率={result['quality_metrics']['unstable_rate']:.4f}, 并列比例(旧/新)={result['quality_metrics']['ties_ratio']['old']:.3f}/{result['quality_metrics']['ties_ratio']['new']:.3f}")
        
        # 方向检查
        direction_check = result['diagnostics']['direction_check']
        if direction_check['direction_reversed']:
            print(f"🚨 方向颠倒警告: 正向={direction_check['spearman_positive']:.4f} vs 反向={direction_check['spearman_negative']:.4f}")
        
        # 成功率分布
        print(f"\n📋 任务成功率分布:")
        for task_type, stats in result['task_success_correlation']['success_rate_by_task'].items():
            print(f"  {task_type}: {stats['mean']:.3f} ({stats['count']}样本)")
        
        print(f"\n🚦 门槛检查 (基于稳定版本):")
        for check_name, passed in threshold_checks.items():
            if check_name.endswith('_pass'):
                status = "✅ PASS" if passed else "❌ FAIL"
                actual_val = threshold_checks['actual_values'].get(check_name.replace('_pass', ''), 'N/A')
                print(f"  {check_name}: {status} (实际值: {actual_val})")
        
        overall_status = "✅ 全部通过" if threshold_checks["overall_pass"] else "❌ 存在未通过项"
        print(f"\n🏆 总体状态: {overall_status}")
        
        # 显示诊断信息
        print(f"\n🔍 Top-10样本对比:")
        print("旧系统Top-10:", [s['sample_id'] for s in result['diagnostics']['top10_lists']['by_old_score'][:5]])
        print("新系统Top-10:", [s['sample_id'] for s in result['diagnostics']['top10_lists']['by_new_score'][:5]])
        
        print(f"\n📄 详细结果已保存: {output_path}")
        
        # 返回退出码
        sys.exit(0 if threshold_checks["overall_pass"] else 1)
        
    except Exception as e:
        logger.error(f"Shadow Run评估失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
