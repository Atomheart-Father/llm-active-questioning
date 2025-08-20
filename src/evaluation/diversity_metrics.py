#!/usr/bin/env python3
"""
多样性指标系统
基于GPT-5指导实现的文本多样性度量工具
"""

import json
import math
import re
from collections import Counter, defaultdict
from typing import Dict, List, Any, Tuple
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DiversityMetrics:
    """多样性指标计算器
    
    实现GPT5要求的核心指标：
    - TTR (Type-Token Ratio)
    - Distinct-1/2 (词汇多样性)
    - n-gram KL散度
    - Zipf斜率
    - 角色/语体覆盖度
    """
    
    def __init__(self):
        # 中文分词简化处理
        self.word_pattern = re.compile(r'[\u4e00-\u9fff]+|[a-zA-Z]+|\d+')
        
    def tokenize_text(self, text: str) -> List[str]:
        """简化的中文分词"""
        # 清理文本
        text = re.sub(r'<[^>]+>', '', text)  # 移除标签
        text = re.sub(r'[^\u4e00-\u9fff\w\s]', ' ', text)  # 保留中文、英文、数字
        
        # 提取词汇
        tokens = self.word_pattern.findall(text.lower())
        return [token for token in tokens if len(token) > 1]  # 过滤单字符
    
    def calculate_ttr(self, texts: List[str]) -> float:
        """计算Type-Token Ratio (词汇丰富度)"""
        all_tokens = []
        for text in texts:
            all_tokens.extend(self.tokenize_text(text))
        
        if not all_tokens:
            return 0.0
        
        types = len(set(all_tokens))
        tokens = len(all_tokens)
        
        return types / tokens if tokens > 0 else 0.0
    
    def calculate_distinct_n(self, texts: List[str], n: int = 1) -> float:
        """计算Distinct-n指标"""
        all_ngrams = []
        
        for text in texts:
            tokens = self.tokenize_text(text)
            if len(tokens) >= n:
                ngrams = [tuple(tokens[i:i+n]) for i in range(len(tokens)-n+1)]
                all_ngrams.extend(ngrams)
        
        if not all_ngrams:
            return 0.0
        
        unique_ngrams = len(set(all_ngrams))
        total_ngrams = len(all_ngrams)
        
        return unique_ngrams / total_ngrams if total_ngrams > 0 else 0.0
    
    def get_ngram_distribution(self, texts: List[str], n: int = 3) -> Dict[tuple, float]:
        """获取n-gram分布"""
        ngram_counts = Counter()
        
        for text in texts:
            tokens = self.tokenize_text(text)
            if len(tokens) >= n:
                ngrams = [tuple(tokens[i:i+n]) for i in range(len(tokens)-n+1)]
                ngram_counts.update(ngrams)
        
        # 转换为概率分布
        total = sum(ngram_counts.values())
        if total == 0:
            return {}
        
        return {ngram: count/total for ngram, count in ngram_counts.items()}
    
    def calculate_kl_divergence(self, dist1: Dict[tuple, float], dist2: Dict[tuple, float]) -> float:
        """计算KL散度"""
        if not dist1 or not dist2:
            return 0.0
        
        # 获取所有n-gram的并集
        all_ngrams = set(dist1.keys()) | set(dist2.keys())
        
        kl_div = 0.0
        for ngram in all_ngrams:
            p = dist1.get(ngram, 1e-10)  # 平滑处理
            q = dist2.get(ngram, 1e-10)
            
            if p > 0:
                kl_div += p * math.log(p / q)
        
        return kl_div
    
    def calculate_zipf_slope(self, texts: List[str]) -> float:
        """计算Zipf分布斜率"""
        # 统计词频
        word_counts = Counter()
        for text in texts:
            tokens = self.tokenize_text(text)
            word_counts.update(tokens)
        
        if len(word_counts) < 10:  # 需要足够的词汇
            return 0.0
        
        # 按频率排序
        frequencies = sorted(word_counts.values(), reverse=True)
        
        # 计算Zipf斜率 (log-log线性拟合)
        ranks = list(range(1, len(frequencies) + 1))
        
        # 使用对数变换
        log_ranks = [math.log(r) for r in ranks]
        log_freqs = [math.log(f) for f in frequencies if f > 0]
        
        if len(log_ranks) != len(log_freqs) or len(log_ranks) < 2:
            return 0.0
        
        # 计算线性回归斜率
        n = len(log_ranks)
        sum_x = sum(log_ranks)
        sum_y = sum(log_freqs)
        sum_xy = sum(x * y for x, y in zip(log_ranks, log_freqs))
        sum_x2 = sum(x * x for x in log_ranks)
        
        if n * sum_x2 - sum_x * sum_x == 0:
            return 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        return abs(slope)  # 返回绝对值
    
    def extract_style_attributes(self, dialogue_data: List[Dict]) -> Dict[str, int]:
        """提取语体和角色属性统计"""
        roles = set()
        styles = set()
        
        for dialogue in dialogue_data:
            # 从对话元数据中提取
            meta = dialogue.get('meta', {})
            template_info = dialogue.get('template_info', {})
            
            if 'role' in meta:
                roles.add(meta['role'])
            if 'role' in template_info:
                roles.add(template_info['role'])
                
            if 'style' in meta:
                styles.add(meta['style'])
            if 'style_tag' in template_info:
                styles.add(template_info['style_tag'])
                
            # 从对话内容中推断
            content = self._extract_dialogue_content(dialogue)
            inferred_attrs = self._infer_style_attributes(content)
            roles.update(inferred_attrs['roles'])
            styles.update(inferred_attrs['styles'])
        
        return {
            'unique_roles': len(roles),
            'unique_styles': len(styles),
            'role_list': list(roles),
            'style_list': list(styles)
        }
    
    def _extract_dialogue_content(self, dialogue: Dict) -> str:
        """提取对话内容"""
        if 'turns' in dialogue:
            contents = []
            for turn in dialogue['turns']:
                if isinstance(turn, dict) and 'content' in turn:
                    contents.append(turn['content'])
            return ' '.join(contents)
        elif 'content' in dialogue:
            return dialogue['content']
        else:
            return str(dialogue)
    
    def _infer_style_attributes(self, content: str) -> Dict[str, List[str]]:
        """从内容推断语体和角色特征"""
        roles = []
        styles = []
        
        # 角色特征识别
        if any(word in content for word in ['作为数学教师', '解题步骤', '验证答案']):
            roles.append('teacher')
        if any(word in content for word in ['我来帮你', '我的思路', '😊']):
            roles.append('student')
        if any(word in content for word in ['研究问题', '分析框架', '置信度']):
            roles.append('researcher') 
        if any(word in content for word in ['调查主题', '线索', '发现']):
            roles.append('journalist')
        if any(word in content for word in ['需求', '解决方案', '业务场景']):
            roles.append('product_manager')
        
        # 语体特征识别
        if any(word in content for word in ['📐', '#数学', '✨']):
            styles.append('social_media')
        if '```' in content or 'Query' in content:
            styles.append('technical')
        if any(word in content for word in ['亲爱的', '感谢', '祝好']):
            styles.append('formal_polite')
        if any(word in content for word in ['嗨', '哇', '超有趣']):
            styles.append('casual')
        
        return {'roles': roles, 'styles': styles}
    
    def generate_diversity_report(self, current_data: List[Dict], 
                                baseline_data: List[Dict] = None,
                                output_file: str = None) -> Dict[str, Any]:
        """生成完整的多样性报告"""
        logger.info(f"生成多样性报告，数据量: {len(current_data)}")
        
        # 提取文本内容
        current_texts = [self._extract_dialogue_content(d) for d in current_data]
        
        # 计算基础指标
        ttr = self.calculate_ttr(current_texts)
        distinct_1 = self.calculate_distinct_n(current_texts, 1)
        distinct_2 = self.calculate_distinct_n(current_texts, 2)
        zipf_slope = self.calculate_zipf_slope(current_texts)
        
        # 计算语体多样性
        style_stats = self.extract_style_attributes(current_data)
        
        # 构建报告
        report = {
            "dataset_info": {
                "total_samples": len(current_data),
                "total_texts": len(current_texts),
                "avg_text_length": np.mean([len(self.tokenize_text(t)) for t in current_texts])
            },
            "lexical_diversity": {
                "ttr": round(ttr, 4),
                "distinct_1": round(distinct_1, 4),
                "distinct_2": round(distinct_2, 4),
                "zipf_slope": round(zipf_slope, 4)
            },
            "style_diversity": {
                "unique_roles": style_stats['unique_roles'],
                "unique_styles": style_stats['unique_styles'],
                "role_coverage": style_stats['role_list'],
                "style_coverage": style_stats['style_list']
            }
        }
        
        # 与基线对比（如果提供）
        if baseline_data:
            baseline_texts = [self._extract_dialogue_content(d) for d in baseline_data]
            
            # 计算KL散度
            current_dist = self.get_ngram_distribution(current_texts, 3)
            baseline_dist = self.get_ngram_distribution(baseline_texts, 3)
            kl_divergence = self.calculate_kl_divergence(current_dist, baseline_dist)
            
            baseline_style_stats = self.extract_style_attributes(baseline_data)
            
            report["baseline_comparison"] = {
                "kl_divergence_3gram": round(kl_divergence, 4),
                "ttr_change": round(ttr - self.calculate_ttr(baseline_texts), 4),
                "distinct_2_change": round(distinct_2 - self.calculate_distinct_n(baseline_texts, 2), 4),
                "role_coverage_increase": style_stats['unique_roles'] - baseline_style_stats['unique_roles'],
                "style_coverage_increase": style_stats['unique_styles'] - baseline_style_stats['unique_styles']
            }
        
        # 验收门槛检查
        report["threshold_check"] = self._check_diversity_thresholds(report)
        
        # 保存报告
        if output_file:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"多样性报告已保存: {output_file}")
        
        return report
    
    def _check_diversity_thresholds(self, report: Dict) -> Dict[str, Any]:
        """检查GPT5设定的多样性门槛"""
        thresholds = {
            "distinct_2_threshold": 0.60,
            "kl_divergence_threshold": 0.15,
            "min_role_coverage": 4,
            "min_style_coverage": 3
        }
        
        results = {}
        metrics = report["lexical_diversity"]
        style_metrics = report["style_diversity"]
        
        # 检查distinct-2
        results["distinct_2_pass"] = metrics["distinct_2"] >= thresholds["distinct_2_threshold"]
        
        # 检查KL散度（如果有基线对比）
        if "baseline_comparison" in report:
            kl_div = report["baseline_comparison"]["kl_divergence_3gram"]
            results["kl_divergence_pass"] = kl_div >= thresholds["kl_divergence_threshold"]
        else:
            results["kl_divergence_pass"] = None  # 无基线数据
        
        # 检查覆盖度
        results["role_coverage_pass"] = style_metrics["unique_roles"] >= thresholds["min_role_coverage"]
        results["style_coverage_pass"] = style_metrics["unique_styles"] >= thresholds["min_style_coverage"]
        
        # 总体通过状态
        required_checks = [
            results["distinct_2_pass"],
            results["role_coverage_pass"], 
            results["style_coverage_pass"]
        ]
        
        if results["kl_divergence_pass"] is not None:
            required_checks.append(results["kl_divergence_pass"])
        
        results["overall_pass"] = all(required_checks)
        results["thresholds_used"] = thresholds
        
        return results

def analyze_template_diversity(template_dir: str) -> Dict[str, Any]:
    """分析模板包的多样性"""
    template_files = list(Path(template_dir).glob("*.json"))
    
    all_templates = []
    for file_path in template_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'templates' in data:
                all_templates.extend(data['templates'])
    
    # 统计模板属性
    roles = set()
    styles = set()
    task_types = set()
    
    for template in all_templates:
        roles.add(template.get('role', 'unknown'))
        styles.add(template.get('style_tag', 'unknown'))
        # 从文件名推断任务类型
        if 'math' in str(template.get('id', '')):
            task_types.add('math')
        elif 'multihop' in str(template.get('id', '')):
            task_types.add('multihop')
        elif 'clarify' in str(template.get('id', '')):
            task_types.add('clarification')
    
    return {
        "total_templates": len(all_templates),
        "unique_roles": len(roles),
        "unique_styles": len(styles),
        "unique_task_types": len(task_types),
        "role_list": list(roles),
        "style_list": list(styles),
        "task_type_list": list(task_types),
        "templates_per_task": len(all_templates) // max(1, len(task_types))
    }

def main():
    """测试函数"""
    # 测试数据
    test_dialogues = [
        {
            "id": "test_1",
            "meta": {"role": "teacher", "style": "formal"},
            "turns": [
                {"role": "user", "content": "一个正方形的周长是20厘米，面积是多少？"},
                {"role": "assistant", "content": "作为数学教师，我将为您提供严谨的解答。解题步骤：1. 求边长：20÷4=5厘米 2. 求面积：5²=25平方厘米"}
            ]
        },
        {
            "id": "test_2", 
            "meta": {"role": "student", "style": "casual"},
            "turns": [
                {"role": "user", "content": "帮我算个题"},
                {"role": "assistant", "content": "好的，我来帮你算这道题！😊 我的思路是这样：首先看看条件，然后用公式计算。"}
            ]
        }
    ]
    
    # 创建多样性分析器
    diversity = DiversityMetrics()
    
    # 生成报告
    report = diversity.generate_diversity_report(
        test_dialogues, 
        output_file="logs/diversity_test_report.json"
    )
    
    print("🎯 多样性分析结果:")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    # 分析模板多样性
    template_analysis = analyze_template_diversity("templates/pack_v2/")
    print(f"\n📋 模板多样性分析:")
    print(json.dumps(template_analysis, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
