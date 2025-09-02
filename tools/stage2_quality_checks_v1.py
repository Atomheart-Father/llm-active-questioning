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
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Set
from collections import defaultdict, Counter

class QualityChecker:
    """Performs quality checks on synthesized active QA samples."""

    def __init__(self):
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

        for sample in samples:
            if sample.get("needs_clarification", False):
                needs_clarification_count += 1

                questions = sample.get("clarification_questions", [])
                if questions:
                    has_questions_count += 1
                    total_questions += len(questions)

                    for q in questions:
                        if isinstance(q, str):
                            question_lengths.append(len(q))

        return {
            "needs_clarification_samples": needs_clarification_count,
            "has_clarification_questions": has_questions_count,
            "missing_questions": needs_clarification_count - has_questions_count,
            "avg_questions_per_sample": round(total_questions / max(has_questions_count, 1), 2),
            "question_length_stats": {
                "min": min(question_lengths) if question_lengths else 0,
                "max": max(question_lengths) if question_lengths else 0,
                "avg": round(sum(question_lengths) / len(question_lengths), 2) if question_lengths else 0
            }
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

    def run_all_checks(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run all quality checks."""
        print("Running field completeness check...")
        field_check = self.check_field_completeness(samples)

        print("Running clarification questions check...")
        clarification_check = self.check_clarification_questions(samples)

        print("Running text length check...")
        length_check = self.check_text_lengths(samples)

        print("Running near-duplicate check...")
        duplicate_check = self.check_near_duplicates(samples)

        return {
            "timestamp": datetime.now().isoformat(),
            "total_samples": len(samples),
            "field_completeness": field_check,
            "clarification_questions": clarification_check,
            "text_lengths": length_check,
            "near_duplicates": duplicate_check
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

    print(f"Clarification questions: {metrics['clarification_questions']['has_clarification_questions']}/{metrics['clarification_questions']['needs_clarification_samples']}")
    print(f"Near duplicates: {metrics['near_duplicates']['duplicate_ratio']}%")

if __name__ == "__main__":
    main()
