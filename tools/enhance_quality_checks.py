#!/usr/bin/env python3
"""
临时脚本：增强质检脚本v1.1
添加证据关联度计算、许可白名单、失败原因统计
"""

import json
import re
from collections import Counter
from pathlib import Path

def calculate_evidence_overlap(questions, context):
    """计算澄清问句与上下文的词面重叠度"""
    if not questions or not context:
        return 0.0

    # 简单分词（去除标点和停用词）
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'as', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'what', 'when', 'where', 'who', 'why', 'how', 'which', 'that', 'this', 'these', 'those'}

    def tokenize(text):
        # 简单分词：去除标点，转换为小写
        words = re.findall(r'\b\w+\b', text.lower())
        return [w for w in words if w not in stop_words and len(w) > 2]

    # 对所有问题进行分词并合并
    all_question_tokens = set()
    for q in questions:
        all_question_tokens.update(tokenize(q))

    # 对上下文进行分词
    context_tokens = set(tokenize(context))

    if not all_question_tokens:
        return 0.0

    # 计算重叠度
    overlap = len(all_question_tokens.intersection(context_tokens))
    return overlap / len(all_question_tokens)

def validate_license_whitelist(license_str):
    """验证许可是否在白名单中"""
    whitelist = {'cc-by-sa-3.0', 'cc-by-sa-4.0', 'mit', 'apache-2.0'}
    return license_str in whitelist

def enhance_quality_checks():
    """增强质检脚本的主要逻辑"""

    print("=== 增强质检脚本 v1.1 ===")

    # 读取现有的质检脚本
    original_script = Path("tools/stage2_quality_checks_v1.py")
    if not original_script.exists():
        print("❌ 找不到原始质检脚本")
        return

    with open(original_script, 'r', encoding='utf-8') as f:
        content = f.read()

    print("📖 读取原始质检脚本成功")

    # 增强内容
    enhancements = []

    # 1. 添加证据关联度计算函数
    evidence_overlap_func = '''
def calculate_evidence_overlap(questions, context):
    """计算澄清问句与上下文的词面重叠度"""
    if not questions or not context:
        return 0.0

    # 简单分词（去除标点和停用词）
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'as', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'what', 'when', 'where', 'who', 'why', 'how', 'which', 'that', 'this', 'these', 'those'}

    def tokenize(text):
        # 简单分词：去除标点，转换为小写
        words = re.findall(r'\\b\\w+\\b', text.lower())
        return [w for w in words if w not in stop_words and len(w) > 2]

    # 对所有问题进行分词并合并
    all_question_tokens = set()
    for q in questions:
        all_question_tokens.update(tokenize(q))

    # 对上下文进行分词
    context_tokens = set(tokenize(context))

    if not all_question_tokens:
        return 0.0

    # 计算重叠度
    overlap = len(all_question_tokens.intersection(context_tokens))
    return overlap / len(all_question_tokens)
'''

    # 2. 添加许可白名单验证函数
    license_func = '''
def validate_license_whitelist(license_str):
    """验证许可是否在白名单中"""
    whitelist = {'cc-by-sa-3.0', 'cc-by-sa-4.0', 'mit', 'apache-2.0'}
    return license_str in whitelist
'''

    # 3. 增强QualityChecker类
    class_enhancement = '''
    def __init__(self):
        self.required_fields = [
            "uid", "user_query", "needs_clarification",
            "clarification_questions", "provided_context",
            "assistant_response", "task_type", "source",
            "licensing", "gen_meta"
        ]
        self.license_whitelist = {'cc-by-sa-3.0', 'cc-by-sa-4.0', 'mit', 'apache-2.0'}
        self.drop_reasons = Counter()
        self.evidence_overlaps = []
'''

    # 4. 添加证据关联度检查
    evidence_check = '''
    def check_evidence_overlap(self, samples):
        """检查证据关联度（HotpotQA/ASQA适用）"""
        overlaps = []
        for sample in samples:
            if sample.get('source') in ['hotpotqa', 'asqa']:
                overlap = calculate_evidence_overlap(
                    sample.get('clarification_questions', []),
                    sample.get('provided_context', '')
                )
                overlaps.append(overlap)
                sample['_evidence_overlap'] = overlap
            else:
                sample['_evidence_overlap'] = None

        return overlaps
'''

    # 5. 增强许可检查
    license_check = '''
    def check_license_whitelist(self, samples):
        """检查许可白名单"""
        errors = []
        for i, sample in enumerate(samples):
            license_str = sample.get('licensing', '')
            if not validate_license_whitelist(license_str):
                errors.append({
                    'sample_index': i,
                    'license': license_str,
                    'reason': 'invalid_license'
                })

        return errors
'''

    # 6. 增强失败原因统计
    failure_stats = '''
    def update_drop_reasons(self, reason):
        """更新失败原因统计"""
        self.drop_reasons[reason] += 1
'''

    # 7. 增强run_quality_checks方法
    run_enhancement = '''
    def run_quality_checks(self, samples):
        """运行所有质量检查（增强版）"""
        print("Running enhanced quality checks...")

        # 基础检查
        field_results = self.check_field_completeness(samples)
        question_results = self.check_clarification_questions(samples)
        type_results = self.check_task_type_enum(samples)
        license_results = self.check_licensing_format(samples)
        text_results = self.check_text_lengths(samples)
        duplicate_results = self.check_near_duplicates(samples)

        # 新增检查
        evidence_overlaps = self.check_evidence_overlap(samples)
        license_errors = self.check_license_whitelist(samples)

        # 计算统计
        total_samples = len(samples)
        alignment_errors = question_results['alignment_errors']

        # 按分片统计
        by_shard = self.calculate_by_shard_stats(samples)

        # 证据关联度统计
        if evidence_overlaps:
            evidence_stats = {
                'mean': sum(evidence_overlaps) / len(evidence_overlaps),
                'min': min(evidence_overlaps),
                'max': max(evidence_overlaps),
                'count': len(evidence_overlaps)
            }
        else:
            evidence_stats = {'mean': 0.0, 'min': 0.0, 'max': 0.0, 'count': 0}

        return {
            'total_samples': total_samples,
            'field_completeness': field_results,
            'clarification_questions': question_results,
            'task_type_enum': type_results,
            'licensing_format': license_results,
            'text_lengths': text_results,
            'near_duplicates': duplicate_results,
            'evidence_overlap': evidence_stats,
            'license_whitelist_errors': license_errors,
            'by_shard': by_shard,
            'drop_reasons': dict(self.drop_reasons)
        }
'''

    # 8. 添加按分片统计方法
    shard_stats = '''
    def calculate_by_shard_stats(self, samples):
        """计算按分片的统计信息"""
        from collections import defaultdict

        shard_stats = defaultdict(lambda: {
            'total': 0,
            'alignment_ok': 0,
            'duplicates': 0,
            'evidence_overlaps': []
        })

        for sample in samples:
            source = sample.get('source', 'unknown')
            shard_stats[source]['total'] += 1

            # 对齐检查
            questions = sample.get('clarification_questions', [])
            response = sample.get('assistant_response', '')
            if questions and response:
                expected_answers = len(questions)
                actual_answers = response.count('；') + 1
                if expected_answers == actual_answers:
                    shard_stats[source]['alignment_ok'] += 1

            # 证据关联度
            if '_evidence_overlap' in sample and sample['_evidence_overlap'] is not None:
                shard_stats[source]['evidence_overlaps'].append(sample['_evidence_overlap'])

        # 计算平均值
        for source, stats in shard_stats.items():
            if stats['evidence_overlaps']:
                stats['evidence_overlap_mean'] = sum(stats['evidence_overlaps']) / len(stats['evidence_overlaps'])
            else:
                stats['evidence_overlap_mean'] = 0.0
            del stats['evidence_overlaps']  # 清理原始数据

        return dict(shard_stats)
'''

    # 组合所有增强
    enhanced_content = content
    enhanced_content = enhanced_content.replace(
        "import argparse",
        "import argparse\nimport re"
    )

    # 添加新函数
    enhanced_content = enhanced_content.replace(
        "class QualityChecker:",
        f"{evidence_overlap_func}\n{license_func}\nclass QualityChecker:"
    )

    # 增强__init__方法
    enhanced_content = enhanced_content.replace(
        "    def __init__(self):",
        "    def __init__(self):\n        self.license_whitelist = {'cc-by-sa-3.0', 'cc-by-sa-4.0', 'mit', 'apache-2.0'}\n        self.drop_reasons = Counter()\n        self.evidence_overlaps = []"
    )

    # 添加新方法
    enhanced_content = enhanced_content.replace(
        "    def check_near_duplicates(self, samples):",
        f"{evidence_check}\n{license_check}\n{failure_stats}\n{shard_stats}\n    def check_near_duplicates(self, samples):"
    )

    # 替换主运行方法
    enhanced_content = enhanced_content.replace(
        "    def run_quality_checks(self, samples):",
        "    def run_quality_checks(self, samples):\n        \"\"\"运行所有质量检查（增强版）\"\"\"\n        print(\"Running enhanced quality checks...\")\n        \n        # 基础检查\n        field_results = self.check_field_completeness(samples)\n        question_results = self.check_clarification_questions(samples)\n        type_results = self.check_task_type_enum(samples)\n        license_results = self.check_licensing_format(samples)\n        text_results = self.check_text_lengths(samples)\n        duplicate_results = self.check_near_duplicates(samples)\n        \n        # 新增检查\n        evidence_overlaps = self.check_evidence_overlap(samples)\n        license_errors = self.check_license_whitelist(samples)\n        \n        # 计算统计\n        total_samples = len(samples)\n        alignment_errors = question_results['alignment_errors']\n        \n        # 按分片统计\n        by_shard = self.calculate_by_shard_stats(samples)\n        \n        # 证据关联度统计\n        if evidence_overlaps:\n            evidence_stats = {\n                'mean': sum(evidence_overlaps) / len(evidence_overlaps),\n                'min': min(evidence_overlaps),\n                'max': max(evidence_overlaps),\n                'count': len(evidence_overlaps)\n            }\n        else:\n            evidence_stats = {'mean': 0.0, 'min': 0.0, 'max': 0.0, 'count': 0}\n        \n        return {\n            'total_samples': total_samples,\n            'field_completeness': field_results,\n            'clarification_questions': question_results,\n            'task_type_enum': type_results,\n            'licensing_format': license_results,\n            'text_lengths': text_results,\n            'near_duplicates': duplicate_results,\n            'evidence_overlap': evidence_stats,\n            'license_whitelist_errors': license_errors,\n            'by_shard': by_shard,\n            'drop_reasons': dict(self.drop_reasons)\n        }"
    )

    # 保存增强后的脚本
    enhanced_script = Path("tools/stage2_quality_checks_v1.1.py")
    with open(enhanced_script, 'w', encoding='utf-8') as f:
        f.write(enhanced_content)

    print(f"✅ 增强后的质检脚本已保存到 {enhanced_script}")
    print("🎯 新增功能：")
    print("  - 证据关联度计算（HotpotQA/ASQA）")
    print("  - 许可白名单校验")
    print("  - 失败原因统计")
    print("  - 按分片统计")

if __name__ == "__main__":
    enhance_quality_checks()
