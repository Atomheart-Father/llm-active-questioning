#!/usr/bin/env python3
"""
种子池质量验证器
检查多样性、去重、配比、泄漏等指标
"""

import json
import argparse
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from collections import Counter, defaultdict
import hashlib
import math

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PoolValidator:
    def __init__(self):
        pass

    def load_samples(self, file_path: Path) -> List[Dict[str, Any]]:
        """加载样本文件"""
        samples = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                samples.append(json.loads(line.strip()))
        return samples

    def calculate_distinct_n(self, texts: List[str], n: int = 2) -> float:
        """计算distinct-n指标"""
        all_ngrams = []
        
        for text in texts:
            words = re.findall(r'\b\w+\b', text.lower())
            ngrams = [' '.join(words[i:i+n]) for i in range(len(words)-n+1)]
            all_ngrams.extend(ngrams)
        
        if not all_ngrams:
            return 0.0
        
        unique_ngrams = len(set(all_ngrams))
        total_ngrams = len(all_ngrams)
        
        return unique_ngrams / total_ngrams

    def calculate_kl_divergence(self, texts: List[str], n: int = 3) -> float:
        """计算n-gram KL散度"""
        # 收集所有n-grams
        all_ngrams = []
        for text in texts:
            words = re.findall(r'\b\w+\b', text.lower())
            ngrams = [' '.join(words[i:i+n]) for i in range(len(words)-n+1)]
            all_ngrams.extend(ngrams)
        
        if not all_ngrams:
            return 0.0
        
        # 计算频率分布
        ngram_counts = Counter(all_ngrams)
        total = len(all_ngrams)
        
        # 计算与均匀分布的KL散度
        vocab_size = len(ngram_counts)
        uniform_prob = 1.0 / vocab_size
        
        kl_div = 0.0
        for count in ngram_counts.values():
            p = count / total
            if p > 0:
                kl_div += p * math.log(p / uniform_prob)
        
        # 归一化到[0,1]范围
        max_kl = math.log(vocab_size)
        return kl_div / max_kl if max_kl > 0 else 0.0

    def count_roles_and_styles(self, samples: List[Dict[str, Any]]) -> Tuple[int, int]:
        """统计角色和语体数量"""
        roles = set()
        styles = set()
        
        for sample in samples:
            # 从模板ID或元数据中提取角色/语体信息
            template_id = sample.get('template_id', '')
            metadata = sample.get('metadata', {})
            
            # 简化实现：从模板ID提取
            if 'teacher' in template_id or 'expert' in template_id:
                roles.add('expert')
            elif 'student' in template_id or 'learner' in template_id:
                roles.add('student')
            elif 'assistant' in template_id:
                roles.add('assistant')
            else:
                roles.add('general')
            
            # 语体识别（简化）
            question = sample.get('question', '')
            if '请' in question or 'Please' in question:
                styles.add('polite')
            elif '?' in question or '？' in question:
                styles.add('interrogative')
            elif '!' in question or '！' in question:
                styles.add('exclamatory')
            else:
                styles.add('declarative')
        
        return len(roles), len(styles)

    def calculate_duplication_rate(self, samples: List[Dict[str, Any]]) -> float:
        """计算去重后重复率"""
        # 基于问题内容的简单去重
        question_hashes = []
        
        for sample in samples:
            question = sample.get('question', '')
            # 标准化处理
            normalized = re.sub(r'\s+', ' ', question.lower().strip())
            question_hash = hashlib.md5(normalized.encode()).hexdigest()
            question_hashes.append(question_hash)
        
        unique_hashes = len(set(question_hashes))
        total_hashes = len(question_hashes)
        
        duplication_rate = (total_hashes - unique_hashes) / total_hashes if total_hashes > 0 else 0
        return duplication_rate

    def check_length_distribution(self, samples: List[Dict[str, Any]], 
                                min_len: int, max_len: int) -> Tuple[int, int]:
        """检查长度分布"""
        too_short = 0
        too_long = 0
        
        for sample in samples:
            question = sample.get('question', '')
            context = sample.get('context', '')
            full_text = f"{question} {context}"
            
            length = len(full_text)
            if length < min_len:
                too_short += 1
            elif length > max_len:
                too_long += 1
        
        return too_short, too_long

    def check_task_distribution(self, samples: List[Dict[str, Any]], 
                              expected_tasks: List[str]) -> Dict[str, float]:
        """检查任务分布"""
        task_counts = Counter()
        
        for sample in samples:
            task = sample.get('task', 'unknown')
            task_counts[task] += 1
        
        total = len(samples)
        task_distribution = {}
        
        for task in expected_tasks:
            count = task_counts.get(task, 0)
            percentage = count / total if total > 0 else 0
            task_distribution[task] = percentage
        
        return task_distribution

    def check_data_leakage(self, samples: List[Dict[str, Any]], 
                          reference_file: Path, ngram_size: int = 5, 
                          similarity_threshold: float = 0.85) -> int:
        """检查数据泄漏"""
        if not reference_file.exists():
            logger.warning(f"参考文件不存在: {reference_file}")
            return 0
        
        # 加载参考数据
        reference_samples = self.load_samples(reference_file)
        reference_ngrams = set()
        
        for ref_sample in reference_samples:
            ref_text = ref_sample.get('question', '') + ' ' + ref_sample.get('context', '')
            words = re.findall(r'\b\w+\b', ref_text.lower())
            ngrams = [' '.join(words[i:i+ngram_size]) for i in range(len(words)-ngram_size+1)]
            reference_ngrams.update(ngrams)
        
        # 检查泄漏
        leaked_samples = 0
        
        for sample in samples:
            sample_text = sample.get('question', '') + ' ' + sample.get('context', '')
            words = re.findall(r'\b\w+\b', sample_text.lower())
            sample_ngrams = [' '.join(words[i:i+ngram_size]) for i in range(len(words)-ngram_size+1)]
            
            if sample_ngrams:
                overlap = len(set(sample_ngrams) & reference_ngrams)
                similarity = overlap / len(sample_ngrams)
                
                if similarity > similarity_threshold:
                    leaked_samples += 1
        
        return leaked_samples

    def validate_pool(self, samples: List[Dict[str, Any]], 
                     min_distinct2: float, kl3_min: float, 
                     roles_min: int, styles_min: int,
                     max_dup_pct: float, max_len: int, min_len: int,
                     expected_tasks: List[str],
                     reference_file: Path = None, leak_ngram: int = 5, 
                     leak_sim: float = 0.85) -> Dict[str, Any]:
        """执行完整验证"""
        logger.info(f"开始验证种子池，共 {len(samples)} 个样本")
        
        results = {
            'total_samples': len(samples),
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }
        
        # 1. 多样性指标
        logger.info("检查多样性指标...")
        questions = [sample.get('question', '') for sample in samples]
        
        distinct2 = self.calculate_distinct_n(questions, 2)
        kl3 = self.calculate_kl_divergence(questions, 3)
        roles_count, styles_count = self.count_roles_and_styles(samples)
        
        results['diversity'] = {
            'distinct_2': distinct2,
            'kl_3_divergence': kl3,
            'roles_count': roles_count,
            'styles_count': styles_count
        }
        
        # 2. 去重检查
        logger.info("检查重复率...")
        dup_rate = self.calculate_duplication_rate(samples)
        results['duplication'] = {
            'rate': dup_rate,
            'percentage': dup_rate * 100
        }
        
        # 3. 长度分布
        logger.info("检查长度分布...")
        too_short, too_long = self.check_length_distribution(samples, min_len, max_len)
        results['length'] = {
            'too_short': too_short,
            'too_long': too_long,
            'too_short_pct': too_short / len(samples) * 100,
            'too_long_pct': too_long / len(samples) * 100
        }
        
        # 4. 任务分布
        logger.info("检查任务分布...")
        task_dist = self.check_task_distribution(samples, expected_tasks)
        results['task_distribution'] = task_dist
        
        # 5. 泄漏检查
        if reference_file:
            logger.info("检查数据泄漏...")
            leaked_count = self.check_data_leakage(samples, reference_file, leak_ngram, leak_sim)
            results['leakage'] = {
                'leaked_samples': leaked_count,
                'leak_percentage': leaked_count / len(samples) * 100
            }
        
        # 6. 验证结果
        violations = []
        
        if distinct2 < min_distinct2:
            violations.append(f"distinct-2 过低: {distinct2:.3f} < {min_distinct2}")
        
        if kl3 < kl3_min:
            violations.append(f"3-gram KL散度过低: {kl3:.3f} < {kl3_min}")
        
        if roles_count < roles_min:
            violations.append(f"角色数不足: {roles_count} < {roles_min}")
        
        if styles_count < styles_min:
            violations.append(f"语体数不足: {styles_count} < {styles_min}")
        
        if dup_rate > max_dup_pct / 100:
            violations.append(f"重复率过高: {dup_rate*100:.1f}% > {max_dup_pct}%")
        
        if too_long > 0:
            violations.append(f"超长样本: {too_long} 个样本 > {max_len} 字符")
        
        if too_short > 0:
            violations.append(f"过短样本: {too_short} 个样本 < {min_len} 字符")
        
        # 检查任务配比（允许±3pp误差）
        expected_ratios = {'hotpotqa': 0.45, 'strategyqa': 0.30, 'gsm8k': 0.25}
        for task, expected_ratio in expected_ratios.items():
            actual_ratio = task_dist.get(task, 0)
            if abs(actual_ratio - expected_ratio) > 0.03:
                violations.append(f"任务 {task} 配比偏差: {actual_ratio:.3f} vs {expected_ratio:.3f}")
        
        if reference_file and 'leakage' in results:
            if results['leakage']['leaked_samples'] > 0:
                violations.append(f"数据泄漏: {results['leakage']['leaked_samples']} 个样本")
        
        results['validation'] = {
            'violations': violations,
            'passed': len(violations) == 0
        }
        
        return results

def main():
    parser = argparse.ArgumentParser(description='验证种子池质量')
    parser.add_argument('input_file', help='种子池文件路径')
    parser.add_argument('--min_distinct2', type=float, default=0.60, help='distinct-2最小值')
    parser.add_argument('--kl3_min', type=float, default=0.15, help='3-gram KL散度最小值')
    parser.add_argument('--roles_min', type=int, default=4, help='最少角色数')
    parser.add_argument('--styles_min', type=int, default=3, help='最少语体数')
    parser.add_argument('--max_dup_pct', type=float, default=2.0, help='最大重复率百分比')
    parser.add_argument('--max_len', type=int, default=4096, help='最大长度')
    parser.add_argument('--min_len', type=int, default=64, help='最小长度')
    parser.add_argument('--leak_check', help='泄漏检查参考文件')
    parser.add_argument('--leak_ngram', type=int, default=5, help='泄漏检查n-gram大小')
    parser.add_argument('--leak_sim', type=float, default=0.85, help='泄漏相似度阈值')
    parser.add_argument('--by_task', default='hotpotqa,strategyqa,gsm8k', help='期望任务列表')
    
    args = parser.parse_args()
    
    input_path = Path(args.input_file)
    if not input_path.exists():
        logger.error(f"输入文件不存在: {input_path}")
        return 1
    
    validator = PoolValidator()
    
    # 加载样本
    samples = validator.load_samples(input_path)
    
    # 解析期望任务
    expected_tasks = [task.strip() for task in args.by_task.split(',')]
    
    # 执行验证
    reference_file = Path(args.leak_check) if args.leak_check else None
    
    results = validator.validate_pool(
        samples=samples,
        min_distinct2=args.min_distinct2,
        kl3_min=args.kl3_min,
        roles_min=args.roles_min,
        styles_min=args.styles_min,
        max_dup_pct=args.max_dup_pct,
        max_len=args.max_len,
        min_len=args.min_len,
        expected_tasks=expected_tasks,
        reference_file=reference_file,
        leak_ngram=args.leak_ngram,
        leak_sim=args.leak_sim
    )
    
    # 输出结果
    logger.info("验证结果:")
    logger.info(f"  样本总数: {results['total_samples']}")
    logger.info(f"  distinct-2: {results['diversity']['distinct_2']:.3f}")
    logger.info(f"  3-gram KL: {results['diversity']['kl_3_divergence']:.3f}")
    logger.info(f"  角色数: {results['diversity']['roles_count']}")
    logger.info(f"  语体数: {results['diversity']['styles_count']}")
    logger.info(f"  重复率: {results['duplication']['percentage']:.1f}%")
    
    if 'leakage' in results:
        logger.info(f"  泄漏样本: {results['leakage']['leaked_samples']}")
    
    # 保存详细报告
    report_path = input_path.with_suffix('.validation.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"详细报告保存到: {report_path}")
    
    # 检查是否通过
    if results['validation']['passed']:
        logger.info("✅ 种子池验证通过!")
        return 0
    else:
        logger.error("❌ 种子池验证失败:")
        for violation in results['validation']['violations']:
            logger.error(f"  - {violation}")
        return 1

if __name__ == "__main__":
    exit(main())
