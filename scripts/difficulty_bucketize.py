#!/usr/bin/env python3
"""
难度分桶与分布重采样
将样本按难度分为Easy/Medium/Hard，并重采样到目标分布
"""

import json
import argparse
import logging
import random
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict, Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DifficultyBucketizer:
    def __init__(self):
        # 难度分桶阈值
        self.thresholds = {
            'len_tokens': {'easy': 200, 'hard': 600},
            'turns': {'easy': 2, 'hard': 5},
            'tool_hops': {'easy': 1, 'hard': 4},
            'ops_numeric': {'easy': 1, 'hard': 4},
            'entities': {'easy': 3, 'hard': 7},
            'connector_density': {'easy': 3, 'hard': 6},
            'clue_overlap': {'easy': 0.40, 'hard': 0.20}  # 注意：overlap越低越难
        }

    def classify_difficulty(self, metrics: Dict[str, Any]) -> str:
        """将样本分类为Easy/Medium/Hard"""
        scores = {'easy': 0, 'medium': 0, 'hard': 0}
        
        # 检查各项指标
        for metric, thresholds in self.thresholds.items():
            value = metrics.get(metric, 0)
            
            if metric == 'clue_overlap':
                # overlap越低越难
                if value > thresholds['easy']:
                    scores['easy'] += 1
                elif value < thresholds['hard']:
                    scores['hard'] += 1
                else:
                    scores['medium'] += 1
            else:
                # 其他指标越高越难
                if value <= thresholds['easy']:
                    scores['easy'] += 1
                elif value >= thresholds['hard']:
                    scores['hard'] += 1
                else:
                    scores['medium'] += 1
        
        # 需要澄清且轮次多的倾向于hard
        if metrics.get('needs_clarification', False) and metrics.get('turns', 0) >= 4:
            scores['hard'] += 2
        
        # 有模糊性标记的倾向于medium/hard
        if metrics.get('ambiguity_flags', []):
            scores['medium'] += len(metrics['ambiguity_flags'])
        
        # 返回得分最高的类别
        return max(scores, key=scores.get)

    def load_metrics(self, metrics_file: Path) -> List[Dict[str, Any]]:
        """加载指标文件"""
        metrics = []
        with open(metrics_file, 'r', encoding='utf-8') as f:
            for line in f:
                metrics.append(json.loads(line.strip()))
        return metrics

    def analyze_distribution(self, samples_by_difficulty: Dict[str, List]) -> Dict[str, Any]:
        """分析当前分布"""
        total = sum(len(samples) for samples in samples_by_difficulty.values())
        
        distribution = {}
        for difficulty, samples in samples_by_difficulty.items():
            count = len(samples)
            percentage = count / total if total > 0 else 0
            distribution[difficulty] = {
                'count': count,
                'percentage': percentage
            }
        
        return {
            'total': total,
            'distribution': distribution
        }

    def parse_target_distribution(self, target_str: str) -> Dict[str, float]:
        """解析目标分布字符串"""
        target = {}
        for pair in target_str.split(','):
            difficulty, ratio = pair.split(':')
            target[difficulty.strip()] = float(ratio.strip())
        
        # 确保总和为1
        total = sum(target.values())
        if abs(total - 1.0) > 1e-6:
            logger.warning(f"目标分布总和不为1: {total}, 进行归一化")
            target = {k: v/total for k, v in target.items()}
        
        return target

    def resample_to_target(self, samples_by_difficulty: Dict[str, List], 
                          target_dist: Dict[str, float], 
                          total_target: int = None) -> List[Dict[str, Any]]:
        """重采样到目标分布"""
        current_total = sum(len(samples) for samples in samples_by_difficulty.values())
        
        if total_target is None:
            total_target = current_total
        
        resampled = []
        
        for difficulty, target_ratio in target_dist.items():
            target_count = int(total_target * target_ratio)
            available_samples = samples_by_difficulty.get(difficulty, [])
            
            if len(available_samples) == 0:
                logger.warning(f"没有{difficulty}难度的样本可供采样")
                continue
            
            if len(available_samples) >= target_count:
                # 随机选择
                selected = random.sample(available_samples, target_count)
            else:
                # 重复采样（bootstrap）
                selected = random.choices(available_samples, k=target_count)
                logger.info(f"{difficulty}难度样本不足，使用重复采样: {len(available_samples)} -> {target_count}")
            
            # 添加难度标签
            for sample in selected:
                sample['difficulty'] = difficulty
            
            resampled.extend(selected)
        
        # 打乱顺序
        random.shuffle(resampled)
        
        return resampled

    def resample_by_task(self, metrics: List[Dict[str, Any]], 
                        target_dist: Dict[str, float],
                        tasks: List[str]) -> List[Dict[str, Any]]:
        """按任务分别重采样"""
        final_samples = []
        
        for task in tasks:
            task_metrics = [m for m in metrics if m.get('task') == task]
            
            if not task_metrics:
                logger.warning(f"任务 {task} 没有样本")
                continue
            
            # 按难度分组
            task_by_difficulty = defaultdict(list)
            for sample in task_metrics:
                difficulty = self.classify_difficulty(sample)
                task_by_difficulty[difficulty].append(sample)
            
            logger.info(f"任务 {task} 难度分布:")
            for diff, samples in task_by_difficulty.items():
                logger.info(f"  {diff}: {len(samples)} 样本")
            
            # 重采样
            task_resampled = self.resample_to_target(
                task_by_difficulty, 
                target_dist, 
                len(task_metrics)
            )
            
            final_samples.extend(task_resampled)
        
        return final_samples

def main():
    parser = argparse.ArgumentParser(description='难度分桶与重采样')
    parser.add_argument('--metrics', required=True, help='指标文件路径')
    parser.add_argument('--target', required=True, help='目标分布，如easy:0.25,medium:0.45,hard:0.30')
    parser.add_argument('--by_task', help='按任务分别处理，用逗号分隔')
    parser.add_argument('--out', required=True, help='输出文件路径')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    
    args = parser.parse_args()
    
    # 设置随机种子
    random.seed(args.seed)
    
    metrics_path = Path(args.metrics)
    output_path = Path(args.out)
    
    if not metrics_path.exists():
        logger.error(f"指标文件不存在: {metrics_path}")
        return 1
    
    # 创建输出目录
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    bucketizer = DifficultyBucketizer()
    
    # 加载指标
    logger.info(f"加载指标文件: {metrics_path}")
    metrics = bucketizer.load_metrics(metrics_path)
    logger.info(f"加载了 {len(metrics)} 个样本的指标")
    
    # 解析目标分布
    target_dist = bucketizer.parse_target_distribution(args.target)
    logger.info(f"目标分布: {target_dist}")
    
    # 分类并重采样
    if args.by_task:
        tasks = [task.strip() for task in args.by_task.split(',')]
        logger.info(f"按任务分别处理: {tasks}")
        resampled_samples = bucketizer.resample_by_task(metrics, target_dist, tasks)
    else:
        # 整体处理
        by_difficulty = defaultdict(list)
        for sample in metrics:
            difficulty = bucketizer.classify_difficulty(sample)
            by_difficulty[difficulty].append(sample)
        
        # 分析当前分布
        current_dist = bucketizer.analyze_distribution(by_difficulty)
        logger.info("当前分布:")
        for diff, info in current_dist['distribution'].items():
            logger.info(f"  {diff}: {info['count']} ({info['percentage']:.1%})")
        
        resampled_samples = bucketizer.resample_to_target(by_difficulty, target_dist)
    
    # 分析重采样后分布
    resampled_by_difficulty = defaultdict(list)
    for sample in resampled_samples:
        resampled_by_difficulty[sample.get('difficulty', 'unknown')].append(sample)
    
    final_dist = bucketizer.analyze_distribution(resampled_by_difficulty)
    logger.info("重采样后分布:")
    for diff, info in final_dist['distribution'].items():
        logger.info(f"  {diff}: {info['count']} ({info['percentage']:.1%})")
    
    # 保存结果
    with open(output_path, 'w', encoding='utf-8') as f:
        for sample in resampled_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    
    logger.info(f"重采样完成！输出 {len(resampled_samples)} 个样本到: {output_path}")
    
    # 生成统计报告
    stats = {
        'original_count': len(metrics),
        'resampled_count': len(resampled_samples),
        'target_distribution': target_dist,
        'original_distribution': {k: v['percentage'] for k, v in 
                                bucketizer.analyze_distribution(
                                    {diff: [m for m in metrics if bucketizer.classify_difficulty(m) == diff] 
                                     for diff in ['easy', 'medium', 'hard']}
                                )['distribution'].items()},
        'final_distribution': {k: v['percentage'] for k, v in final_dist['distribution'].items()},
        'seed': args.seed
    }
    
    stats_path = output_path.with_suffix('.stats.json')
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    logger.info(f"统计报告保存到: {stats_path}")
    
    return 0

if __name__ == "__main__":
    exit(main())
