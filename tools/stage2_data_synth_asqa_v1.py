#!/usr/bin/env python3
"""
Stage 2 ASQA Data Synthesizer v1
Synthesizes active QA samples from ASQA dataset with long-form clarification questions.

Strategy: Zero simulation - only field mapping and cleaning from original data.
No external model calls, no content generation, strictly traceable to source.

Usage:
    python tools/stage2_data_synth_asqa_v1.py --input data/raw/asqa/20250902/asqa_200.jsonl --output data/interim/shards/stage2_v1/shard-004.jsonl --count 100 --seed 20240906
"""

import argparse
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import random

# Fixed seed for reproducibility
SEED = 20240906

class ASQASynthesizer:
    """Synthesizes active QA samples from ASQA with long-form clarification questions."""

    def __init__(self, seed: int = SEED):
        self.seed = seed
        random.seed(seed)

    def load_raw_data(self, input_file: Path) -> List[Dict[str, Any]]:
        """Load raw ASQA data from JSONL file."""
        samples = []
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    samples.append(json.loads(line))
        print(f"Loaded {len(samples)} raw samples from {input_file}")
        return samples

    def generate_uid(self, sample_id: str) -> str:
        """Generate unique identifier for synthesized sample."""
        content = f"{sample_id}_{self.seed}_{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def extract_longform_questions(self, sample: Dict[str, Any]) -> List[str]:
        """Extract 1-2 clarification questions from qa_pairs based on ambiguity."""
        qa_pairs = sample.get("qa_pairs", [])

        if not qa_pairs:
            return []

        # Select 1-2 questions that best represent the ambiguity
        questions = []
        for qa_pair in qa_pairs[:3]:  # Limit to first 3 qa_pairs
            question = qa_pair.get("question", "").strip()
            if question and len(questions) < 2:
                questions.append(question)

        # Ensure we have at least 1 question
        if not questions and qa_pairs:
            # Fallback: use the first question
            first_question = qa_pairs[0].get("question", "").strip()
            if first_question:
                questions = [first_question]

        return questions

    def generate_longform_response(self, sample: Dict[str, Any], selected_questions: List[str]) -> str:
        """Generate enumerated response based on qa_pairs short_answers."""
        qa_pairs = sample.get("qa_pairs", [])

        if not qa_pairs:
            return "无答案信息"

        # Collect answers for each selected question
        answers = []
        for selected_question in selected_questions:
            # Find matching qa_pair
            for qa_pair in qa_pairs:
                if qa_pair.get("question") == selected_question:
                    short_answers = qa_pair.get("short_answers", [])
                    if short_answers:
                        # Use the first short answer
                        answers.append(short_answers[0])
                    break

        if not answers:
            # Fallback: use answers from first qa_pair
            first_qa_pair = qa_pairs[0]
            short_answers = first_qa_pair.get("short_answers", [])
            if short_answers:
                answers = [short_answers[0]]

        # Generate enumerated response
        if len(answers) == 1:
            return f"根据信息：{answers[0]}"
        elif len(answers) == 2:
            return f"若{selected_questions[0]}则{answers[0]}；若{selected_questions[1]}则{answers[1]}"
        else:
            return f"答案：{answers[0] if answers else '无答案'}"

    def extract_longform_context(self, sample: Dict[str, Any]) -> str:
        """Extract context information from long_answer."""
        annotations = sample.get("annotations", [])
        if not annotations:
            return "长答案格式问题"

        long_answer = annotations[0].get("long_answer", "").strip()
        if long_answer:
            # Truncate to first 100 characters for context
            return long_answer[:100] + "..." if len(long_answer) > 100 else long_answer

        return "长答案格式问题"

    def synthesize_sample(self, raw_sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Synthesize a single active QA sample from raw ASQA data."""
        try:
            # Extract data from raw sample
            sample_id = raw_sample.get("sample_id", "")
            ambiguous_question = raw_sample.get("ambiguous_question", "").strip()

            if not ambiguous_question:
                return None

            # Generate clarification questions
            clarification_questions = self.extract_longform_questions(raw_sample)

            # Skip if no clarification questions found
            if not clarification_questions:
                return None

            # Generate answer enumeration
            assistant_response = self.generate_longform_response(raw_sample, clarification_questions)

            # Extract context
            provided_context = self.extract_longform_context(raw_sample)

            # Generate metadata
            gen_meta = {
                "generator_version": "stage2_data_synth_asqa_v1",
                "generation_timestamp": datetime.now().isoformat(),
                "seed": self.seed,
                "source_dataset": "asqa",
                "source_config": "",
                "quality_score": None
            }

            # Build synthesized sample
            synthesized_sample = {
                "uid": self.generate_uid(sample_id),
                "user_query": ambiguous_question,
                "needs_clarification": True,
                "clarification_questions": clarification_questions,
                "provided_context": provided_context,
                "assistant_response": assistant_response,
                "task_type": "longform",
                "source": "asqa",
                "licensing": "apache-2.0",
                "gen_meta": gen_meta
            }

            return synthesized_sample

        except Exception as e:
            print(f"Error synthesizing sample {raw_sample.get('sample_id', 'unknown')}: {e}")
            return None

    def synthesize_batch(self, raw_samples: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
        """Synthesize a batch of active QA samples."""
        # Shuffle for randomization (but with fixed seed)
        shuffled_samples = raw_samples.copy()
        random.shuffle(shuffled_samples)

        synthesized_samples = []
        processed_count = 0

        for raw_sample in shuffled_samples:
            if processed_count >= count:
                break

            synthesized = self.synthesize_sample(raw_sample)
            if synthesized:
                synthesized_samples.append(synthesized)
                processed_count += 1

        print(f"Successfully synthesized {len(synthesized_samples)} samples")
        return synthesized_samples

    def save_synthesized_data(self, samples: List[Dict[str, Any]], output_file: Path):
        """Save synthesized samples to JSONL file."""
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            for sample in samples:
                json.dump(sample, f, ensure_ascii=False)
                f.write('\n')

        print(f"Saved {len(samples)} synthesized samples to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Synthesize active QA samples from ASQA")
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input raw ASQA JSONL file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output synthesized JSONL file"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of samples to synthesize (default: 100)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help=f"Random seed for reproducibility (default: {SEED})"
    )

    args = parser.parse_args()

    # Validate input file
    if not args.input.exists():
        print(f"Error: Input file {args.input} does not exist")
        exit(1)

    # Initialize synthesizer
    synthesizer = ASQASynthesizer(seed=args.seed)

    # Load raw data
    print(f"Loading raw data from {args.input}")
    raw_samples = synthesizer.load_raw_data(args.input)

    # Synthesize samples
    print(f"Synthesizing {args.count} samples with seed {args.seed}")
    synthesized_samples = synthesizer.synthesize_batch(raw_samples, args.count)

    # Save results
    synthesizer.save_synthesized_data(synthesized_samples, args.output)

    print(f"\nSynthesis completed!")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"Synthesized: {len(synthesized_samples)} samples")
    print(f"Seed: {args.seed}")

if __name__ == "__main__":
    main()
