#!/usr/bin/env python3
"""
Stage 2 Quality Checks v1
Performs quality validation on synthesized active QA samples.

Checks performed:
- Field completeness
- Clarification questions presence when needed
- Text length thresholds
- Near-duplicate detection using simple hashing

Usage:
    python tools/stage2_quality_checks_v1.py --input data/interim/shards/stage2_v1/shard-000.jsonl --output data/processed/active_qa_v1/metrics.json
"""

import argparse
import re
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Set
from collections import defaultdict, Counter


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

class QualityChecker:
    """Performs quality checks on synthesized active QA samples."""

    def __init__(self):
        self.license_whitelist = {'cc-by-sa-3.0', 'cc-by-sa-4.0', 'mit', 'apache-2.0'}
        self.drop_reasons = Counter()
        self.evidence_overlaps = []
        self.required_fields = [
            "uid", "user_query", "needs_clarification",
            "clarification_questions", "provided_context",
            "assistant_response", "task_type", "source",
            "licensing", "gen_meta"
        ]

    def load_samples(self, input_file: Path) -> List[Dict[str, Any]]:
        """Load synthesized samples from JSONL file."""
        samples = []
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    samples.append(json.loads(line))
        print(f"Loaded {len(samples)} samples for quality check")
        return samples

    def check_field_completeness(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check field completeness for all samples."""
        total_samples = len(samples)
        field_counts = defaultdict(int)
        missing_fields = defaultdict(list)

        for i, sample in enumerate(samples):
            for field in self.required_fields:
                if field in sample and sample[field] is not None:
                    field_counts[field] += 1
                else:
                    missing_fields[field].append(i)

        # Calculate completeness percentages
        completeness = {}
        for field in self.required_fields:
            completeness[field] = {
                "present": field_counts[field],
                "missing": total_samples - field_counts[field],
                "percentage": round(field_counts[field] / total_samples * 100, 2) if total_samples > 0 else 0
            }

        return {
            "field_completeness": completeness,
            "missing_samples": dict(missing_fields)
        }

    def check_clarification_questions(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check clarification questions presence and quality."""
        needs_clarification_count = 0
        has_questions_count = 0
        total_questions = 0
        question_lengths = []
        alignment_errors = 0

        for sample in samples:
            if sample.get("needs_clarification", False):
                needs_clarification_count += 1

                questions = sample.get("clarification_questions", [])
                assistant_response = sample.get("assistant_response", "")

                if questions:
                    has_questions_count += 1
                    total_questions += len(questions)

                    # Check alignment between questions and response
                    expected_options = len(questions)
                    actual_options = assistant_response.count("；") + 1 if assistant_response else 0

                    if assistant_response and expected_options != actual_options:
                        alignment_errors += 1

                    for q in questions:
                        if isinstance(q, str):
                            question_lengths.append(len(q))

        return {
            "needs_clarification_samples": needs_clarification_count,
            "has_clarification_questions": has_questions_count,
            "missing_questions": needs_clarification_count - has_questions_count,
            "alignment_errors": alignment_errors,
            "avg_questions_per_sample": round(total_questions / max(has_questions_count, 1), 2),
            "question_length_stats": {
                "min": min(question_lengths) if question_lengths else 0,
                "max": max(question_lengths) if question_lengths else 0,
                "avg": round(sum(question_lengths) / len(question_lengths), 2) if question_lengths else 0
            }
        }

    def check_task_type_enum(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check task_type enum values."""
        valid_task_types = {"ambiguous", "math", "multihop", "longform"}
        invalid_samples = []

        for i, sample in enumerate(samples):
            task_type = sample.get("task_type")
            if task_type not in valid_task_types:
                invalid_samples.append((i, task_type))

        return {
            "valid_task_types": list(valid_task_types),
            "invalid_count": len(invalid_samples),
            "invalid_samples": invalid_samples
        }

    def check_licensing_format(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check licensing format."""
        valid_formats = {"cc-by-sa-3.0", "cc-by-sa-4.0", "mit", "apache-2.0"}
        format_errors = []
        type_errors = []

        for i, sample in enumerate(samples):
            licensing = sample.get("licensing")

            # Check type
            if not isinstance(licensing, str):
                type_errors.append((i, type(licensing).__name__))
                continue

            # Check value
            if licensing not in valid_formats:
                format_errors.append((i, licensing))

        return {
            "valid_formats": list(valid_formats),
            "type_errors": type_errors,
            "format_errors": format_errors,
            "total_errors": len(type_errors) + len(format_errors)
        }

    def check_text_lengths(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check text length thresholds."""
        thresholds = {
            "user_query": 2048,
            "clarification_questions": 512,  # per question
            "provided_context": 4096,
            "assistant_response": 4096
        }

        violations = defaultdict(list)

        for i, sample in enumerate(samples):
            # Check user_query length
            if len(sample.get("user_query", "")) > thresholds["user_query"]:
                violations["user_query"].append(i)

            # Check clarification questions lengths
            for j, question in enumerate(sample.get("clarification_questions", [])):
                if isinstance(question, str) and len(question) > thresholds["clarification_questions"]:
                    violations["clarification_questions"].append(f"sample_{i}_q{j}")

            # Check provided_context length
            if len(sample.get("provided_context", "")) > thresholds["provided_context"]:
                violations["provided_context"].append(i)

            # Check assistant_response length
            if len(sample.get("assistant_response", "")) > thresholds["assistant_response"]:
                violations["assistant_response"].append(i)

        return {
            "thresholds": thresholds,
            "violations": dict(violations),
            "violation_counts": {field: len(indices) for field, indices in violations.items()}
        }

    def check_near_duplicates(self, samples: List[Dict[str, Any]], threshold: float = 0.9) -> Dict[str, Any]:
        """Check for near-duplicate samples using simple hashing."""
        def get_content_hash(sample: Dict[str, Any]) -> str:
            """Generate hash of sample content for duplicate detection."""
            content_parts = [
                sample.get("user_query", ""),
                str(sample.get("clarification_questions", [])),
                sample.get("assistant_response", "")
            ]
            content = "|".join(content_parts)
            return hashlib.md5(content.encode()).hexdigest()

        # Group by content hash
        hash_groups = defaultdict(list)
        for i, sample in enumerate(samples):
            content_hash = get_content_hash(sample)
            hash_groups[content_hash].append(i)

        # Find duplicate groups
        duplicate_groups = {}
        singleton_groups = 0

        for content_hash, indices in hash_groups.items():
            if len(indices) > 1:
                duplicate_groups[content_hash] = indices
            else:
                singleton_groups += 1

        # Calculate duplicate ratio
        total_samples = len(samples)
        duplicate_samples = sum(len(indices) for indices in duplicate_groups.values())
        unique_samples = len(hash_groups)

        return {
            "total_samples": total_samples,
            "unique_samples": unique_samples,
            "duplicate_samples": duplicate_samples,
            "duplicate_ratio": round(duplicate_samples / total_samples * 100, 2) if total_samples > 0 else 0,
            "duplicate_groups": len(duplicate_groups),
            "singleton_groups": singleton_groups,
            "duplicate_details": duplicate_groups
        }

    def check_evidence_overlap(self, samples: List[Dict[str, Any]]) -> List[float]:
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

    def check_license_whitelist(self, samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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

    def calculate_by_shard_stats(self, samples: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
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

    def run_all_checks(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run all quality checks (enhanced v1.1)."""
        print("Running field completeness check...")
        field_check = self.check_field_completeness(samples)

        print("Running clarification questions check...")
        clarification_check = self.check_clarification_questions(samples)

        print("Running task_type enum check...")
        task_type_check = self.check_task_type_enum(samples)

        print("Running licensing format check...")
        licensing_check = self.check_licensing_format(samples)

        print("Running text length check...")
        length_check = self.check_text_lengths(samples)

        print("Running near-duplicate check...")
        duplicate_check = self.check_near_duplicates(samples)

        # 新增：证据关联度检查
        print("Running evidence overlap check...")
        evidence_overlaps = self.check_evidence_overlap(samples)

        # 新增：许可白名单检查
        print("Running license whitelist check...")
        license_errors = self.check_license_whitelist(samples)

        # 新增：按分片统计
        print("Calculating by-shard statistics...")
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
            "timestamp": datetime.now().isoformat(),
            "total_samples": len(samples),
            "field_completeness": field_check,
            "clarification_questions": clarification_check,
            "task_type_enum": task_type_check,
            "licensing_format": licensing_check,
            "text_lengths": length_check,
            "near_duplicates": duplicate_check,
            "evidence_overlap": evidence_stats,
            "license_whitelist_errors": license_errors,
            "by_shard": by_shard,
            "drop_reasons": dict(self.drop_reasons)
        }

    def save_metrics(self, metrics: Dict[str, Any], output_file: Path):
        """Save metrics to JSON file."""
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)

        print(f"Saved quality metrics to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Quality check synthesized active QA samples")
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input synthesized JSONL file to check"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output metrics JSON file"
    )
    parser.add_argument(
        "--duplicate-threshold",
        type=float,
        default=0.9,
        help="Threshold for near-duplicate detection (default: 0.9)"
    )

    args = parser.parse_args()

    # Validate input file
    if not args.input.exists():
        print(f"Error: Input file {args.input} does not exist")
        exit(1)

    # Initialize checker and load data
    checker = QualityChecker()
    samples = checker.load_samples(args.input)

    # Run all checks
    print(f"Running quality checks on {len(samples)} samples...")
    metrics = checker.run_all_checks(samples)

    # Save results
    checker.save_metrics(metrics, args.output)

    # Print summary
    print("\nQuality Check Summary:")
    print(f"Total samples: {metrics['total_samples']}")
    print("Field completeness (%):")
    for field, stats in metrics['field_completeness']['field_completeness'].items():
        print(f"  {field}: {stats['percentage']}%")

    clarification = metrics['clarification_questions']
    print(f"Clarification questions: {clarification['has_clarification_questions']}/{clarification['needs_clarification_samples']}")
    print(f"  - Alignment errors: {clarification['alignment_errors']}")

    task_type = metrics['task_type_enum']
    print(f"Task type enum: {task_type['invalid_count']} invalid samples")

    licensing = metrics['licensing_format']
    print(f"Licensing format: {licensing['total_errors']} errors")

    print(f"Near duplicates: {metrics['near_duplicates']['duplicate_ratio']}%")

if __name__ == "__main__":
    main()
