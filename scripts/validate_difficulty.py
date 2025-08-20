#!/usr/bin/env python3
"""
难度分布验证器
检查难度分布是否达标，生成直方图和分位数统计
"""

import json
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict, Counter
import statistics

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DifficultyValidator:
    def __init__(self):
        self.metric_limits = {
            'len_tokens': {'max': 3500},
            'turns': {'max': 8},
            'tool_hops': {'max': 8},
            'clue_overlap': {'easy_max': 0.65, 'hard_min': 0.10}
        }

    def load_samples(self, file_path: Path) -> List[Dict[str, Any]]:
        """加载样本文件"""
        samples = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                samples.append(json.loads(line.strip()))
        return samples

    def analyze_difficulty_distribution(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析难度分布"""
        difficulty_counts = Counter()
        by_task_difficulty = defaultdict(lambda: defaultdict(int))
        
        for sample in samples:
            difficulty = sample.get('difficulty', 'unknown')
            task = sample.get('task', 'unknown')
            
            difficulty_counts[difficulty] += 1
            by_task_difficulty[task][difficulty] += 1
        
        total = len(samples)
        
        # 计算分布百分比
        distribution = {}
        for difficulty, count in difficulty_counts.items():
            distribution[difficulty] = {
                'count': count,
                'percentage': count / total if total > 0 else 0
            }
        
        # 按任务分布
        task_distributions = {}
        for task, task_counts in by_task_difficulty.items():
            task_total = sum(task_counts.values())
            task_distributions[task] = {}
            for difficulty, count in task_counts.items():
                task_distributions[task][difficulty] = {
                    'count': count,
                    'percentage': count / task_total if task_total > 0 else 0
                }
        
        return {
            'total_samples': total,
            'overall_distribution': distribution,
            'by_task_distribution': task_distributions
        }

    def calculate_metric_statistics(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算指标统计信息"""
        metrics_data = defaultdict(list)
        
        # 收集所有指标数据
        for sample in samples:
            for metric in ['len_tokens', 'turns', 'tool_hops', 'entities', 
                          'ops_numeric', 'connector_density', 'clue_overlap', 'coref_pronouns']:
                value = sample.get(metric, 0)
                if isinstance(value, (int, float)):
                    metrics_data[metric].append(value)
        
        # 计算统计量
        statistics_report = {}
        for metric, values in metrics_data.items():
            if values:
                statistics_report[metric] = {
                    'count': len(values),
                    'mean': statistics.mean(values),
                    'median': statistics.median(values),
                    'min': min(values),
                    'max': max(values),
                    'p10': self.percentile(values, 10),
                    'p90': self.percentile(values, 90),
                    'std': statistics.stdev(values) if len(values) > 1 else 0
                }
        
        return statistics_report

    def percentile(self, values: List[float], p: int) -> float:
        """计算百分位数"""
        sorted_values = sorted(values)
        k = (len(sorted_values) - 1) * p / 100
        f = int(k)
        c = k - f
        if f == len(sorted_values) - 1:
            return sorted_values[f]
        return sorted_values[f] * (1 - c) + sorted_values[f + 1] * c

    def analyze_by_difficulty(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """按难度分析指标"""
        by_difficulty = defaultdict(list)
        
        for sample in samples:
            difficulty = sample.get('difficulty', 'unknown')
            by_difficulty[difficulty].append(sample)
        
        difficulty_analysis = {}
        for difficulty, difficulty_samples in by_difficulty.items():
            if difficulty_samples:
                # 计算clue_overlap的统计
                clue_overlaps = [s.get('clue_overlap', 0) for s in difficulty_samples 
                               if isinstance(s.get('clue_overlap'), (int, float))]
                
                analysis = {
                    'sample_count': len(difficulty_samples),
                    'clue_overlap_median': statistics.median(clue_overlaps) if clue_overlaps else 0,
                    'avg_len_tokens': statistics.mean([s.get('len_tokens', 0) for s in difficulty_samples]),
                    'avg_turns': statistics.mean([s.get('turns', 0) for s in difficulty_samples]),
                    'avg_tool_hops': statistics.mean([s.get('tool_hops', 0) for s in difficulty_samples])
                }
                
                difficulty_analysis[difficulty] = analysis
        
        return difficulty_analysis

    def check_violations(self, samples: List[Dict[str, Any]], 
                        min_hard_pct: float, max_easy_pct: float,
                        len_max: int, turns_max: int, tool_hops_max: int,
                        clue_overlap_max_easy: float, clue_overlap_min_hard: float) -> List[str]:
        """检查违规情况"""
        violations = []
        
        # 分析分布
        dist_analysis = self.analyze_difficulty_distribution(samples)
        overall_dist = dist_analysis['overall_distribution']
        
        # 检查hard比例
        hard_pct = overall_dist.get('hard', {}).get('percentage', 0)
        if hard_pct < min_hard_pct:
            violations.append(f"Hard样本比例不足: {hard_pct:.1%} < {min_hard_pct:.1%}")
        
        # 检查easy比例
        easy_pct = overall_dist.get('easy', {}).get('percentage', 0)
        if easy_pct > max_easy_pct:
            violations.append(f"Easy样本比例过高: {easy_pct:.1%} > {max_easy_pct:.1%}")
        
        # 检查超限样本
        overlimit_counts = defaultdict(int)
        for sample in samples:
            if sample.get('len_tokens', 0) > len_max:
                overlimit_counts['len_tokens'] += 1
            if sample.get('turns', 0) > turns_max:
                overlimit_counts['turns'] += 1
            if sample.get('tool_hops', 0) > tool_hops_max:
                overlimit_counts['tool_hops'] += 1
        
        for metric, count in overlimit_counts.items():
            pct = count / len(samples) * 100
            violations.append(f"{metric}超限样本: {count} ({pct:.1f}%)")
        
        # 检查难度一致性
        difficulty_analysis = self.analyze_by_difficulty(samples)
        
        easy_clue_median = difficulty_analysis.get('easy', {}).get('clue_overlap_median', 0)
        if easy_clue_median < clue_overlap_max_easy:
            violations.append(f"Easy样本clue_overlap中位数过低: {easy_clue_median:.3f} < {clue_overlap_max_easy}")
        
        hard_clue_median = difficulty_analysis.get('hard', {}).get('clue_overlap_median', 1)
        if hard_clue_median > clue_overlap_min_hard:
            violations.append(f"Hard样本clue_overlap中位数过高: {hard_clue_median:.3f} > {clue_overlap_min_hard}")
        
        return violations

    def generate_report(self, samples: List[Dict[str, Any]], 
                       balanced_samples: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """生成完整报告"""
        report = {
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'total_samples': len(samples),
            'distribution_analysis': self.analyze_difficulty_distribution(samples),
            'metric_statistics': self.calculate_metric_statistics(samples),
            'difficulty_breakdown': self.analyze_by_difficulty(samples)
        }
        
        if balanced_samples:
            report['balanced_analysis'] = {
                'total_samples': len(balanced_samples),
                'distribution_analysis': self.analyze_difficulty_distribution(balanced_samples),
                'difficulty_breakdown': self.analyze_by_difficulty(balanced_samples)
            }
        
        return report

def main():
    parser = argparse.ArgumentParser(description='验证难度分布')
    parser.add_argument('--metrics', required=True, help='原始指标文件')
    parser.add_argument('--balanced', help='平衡后样本文件')
    parser.add_argument('--min_hard_pct', type=float, default=0.30, help='Hard样本最低比例')
    parser.add_argument('--max_easy_pct', type=float, default=0.30, help='Easy样本最高比例')
    parser.add_argument('--len_max', type=int, default=3500, help='最大token数')
    parser.add_argument('--turns_max', type=int, default=8, help='最大轮次数')
    parser.add_argument('--tool_hops_max', type=int, default=8, help='最大工具调用数')
    parser.add_argument('--clue_overlap_max_easy', type=float, default=0.65, help='Easy样本clue_overlap上限')
    parser.add_argument('--clue_overlap_min_hard', type=float, default=0.10, help='Hard样本clue_overlap下限')
    parser.add_argument('--out', required=True, help='输出报告文件')
    
    args = parser.parse_args()
    
    metrics_path = Path(args.metrics)
    output_path = Path(args.out)
    
    if not metrics_path.exists():
        logger.error(f"指标文件不存在: {metrics_path}")
        return 1
    
    # 创建输出目录
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    validator = DifficultyValidator()
    
    # 加载样本
    logger.info(f"加载指标文件: {metrics_path}")
    samples = validator.load_samples(metrics_path)
    logger.info(f"加载了 {len(samples)} 个样本")
    
    balanced_samples = None
    if args.balanced:
        balanced_path = Path(args.balanced)
        if balanced_path.exists():
            logger.info(f"加载平衡样本文件: {balanced_path}")
            balanced_samples = validator.load_samples(balanced_path)
            logger.info(f"加载了 {len(balanced_samples)} 个平衡样本")
        else:
            logger.warning(f"平衡样本文件不存在: {balanced_path}")
    
    # 生成报告
    report = validator.generate_report(samples, balanced_samples)
    
    # 检查违规（使用平衡样本或原始样本）
    check_samples = balanced_samples if balanced_samples else samples
    violations = validator.check_violations(
        check_samples,
        args.min_hard_pct, args.max_easy_pct,
        args.len_max, args.turns_max, args.tool_hops_max,
        args.clue_overlap_max_easy, args.clue_overlap_min_hard
    )
    
    report['validation'] = {
        'violations': violations,
        'passed': len(violations) == 0,
        'thresholds': {
            'min_hard_pct': args.min_hard_pct,
            'max_easy_pct': args.max_easy_pct,
            'len_max': args.len_max,
            'turns_max': args.turns_max,
            'tool_hops_max': args.tool_hops_max,
            'clue_overlap_max_easy': args.clue_overlap_max_easy,
            'clue_overlap_min_hard': args.clue_overlap_min_hard
        }
    }
    
    # 保存报告
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # 输出结果
    logger.info(f"验证报告保存到: {output_path}")
    
    if violations:
        logger.error("发现以下违规:")
        for violation in violations:
            logger.error(f"  ❌ {violation}")
        logger.error("难度验证失败!")
        return 1
    else:
        logger.info("✅ 所有难度指标验证通过!")
        return 0

if __name__ == "__main__":
    exit(main())
