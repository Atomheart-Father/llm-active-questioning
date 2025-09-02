#!/usr/bin/env python3
"""
Stage 2 Data Synthesizer v1
Synthesizes active QA samples from AmbigQA dataset with clarification questions.

Strategy: Zero simulation - only field mapping and cleaning from original data.
No external model calls, no content generation, strictly traceable to source.

Usage:
    python tools/stage2_data_synth_v1.py --input data/raw/ambigqa/20250902/ambigqa_200.jsonl --output data/interim/shards/stage2_v1/shard-000.jsonl --count 100 --seed 20240902
"""

import argparse
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import random

# Fixed seed for reproducibility
SEED = 20240902

class AmbigQASynthesizer:
    """Synthesizes active QA samples from AmbigQA with clarification questions."""

    def __init__(self, seed: int = SEED):
        self.seed = seed
        random.seed(seed)

    def load_raw_data(self, input_file: Path) -> List[Dict[str, Any]]:
        """Load raw AmbigQA data from JSONL file."""
        samples = []
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    samples.append(json.loads(line))
        print(f"Loaded {len(samples)} raw samples from {input_file}")
        return samples

    def generate_uid(self, source_id: str) -> str:
        """Generate unique identifier for synthesized sample."""
        content = f"{source_id}_{self.seed}_{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def clean_clarification_questions(self, qa_pairs: List[Dict[str, Any]]) -> List[str]:
        """Clean and extract clarification questions from qaPairs."""
        questions = []

        for pair in qa_pairs:
            if "question" in pair:
                pair_questions = pair["question"]
                if isinstance(pair_questions, list):
                    for q in pair_questions:
                        if isinstance(q, str) and q.strip():
                            # Clean and truncate question
                            cleaned_q = q.strip()
                            if len(cleaned_q) > 512:
                                cleaned_q = cleaned_q[:509] + "..."
                            if cleaned_q not in questions:  # Remove duplicates
                                questions.append(cleaned_q)
                elif isinstance(pair_questions, str) and pair_questions.strip():
                    cleaned_q = pair_questions.strip()
                    if len(cleaned_q) > 512:
                        cleaned_q = cleaned_q[:509] + "..."
                    if cleaned_q not in questions:
                        questions.append(cleaned_q)

        # Limit to 1-3 questions, prioritize first ones
        return questions[:3] if questions else []

    def generate_answer_enumeration(self, qa_pairs: List[Dict[str, Any]], selected_questions: List[str]) -> str:
        """Generate enumerated answer from qaPairs, matching selected questions."""
        answers = []

        # Collect all answers from qaPairs
        all_answers = []
        for pair in qa_pairs:
            if "answer" in pair:
                pair_answers = pair["answer"]
                if isinstance(pair_answers, list):
                    # Each pair may have multiple answers
                    for answer_list in pair_answers:
                        if isinstance(answer_list, list) and answer_list:
                            # Take first answer from each answer list
                            first_answer = answer_list[0]
                            if isinstance(first_answer, str):
                                answer_text = first_answer
                            else:
                                answer_text = str(first_answer)
                            all_answers.append(answer_text)

        # Only use answers for the selected questions (limit to same count)
        num_questions = len(selected_questions)
        answers = all_answers[:num_questions]

        # Generate enumerated response
        if answers:
            enumerated_answers = []
            for i, answer in enumerate(answers):
                enumerated_answers.append(f"若选项{i+1}则{answer}")
            return "；".join(enumerated_answers)
        return ""

    def extract_context(self, annotations: Dict[str, Any]) -> str:
        """Extract context information from annotations."""
        context_parts = []

        # Add type information
        if "type" in annotations:
            types = annotations["type"]
            if isinstance(types, list) and types:
                context_parts.append(f"歧义类型: {', '.join(types)}")

        # Add any additional context from qaPairs structure
        if "qaPairs" in annotations:
            qa_pairs = annotations["qaPairs"]
            if isinstance(qa_pairs, list) and len(qa_pairs) > 1:
                context_parts.append(f"包含 {len(qa_pairs)} 个澄清选项")

        return "。".join(context_parts) if context_parts else ""

    def synthesize_sample(self, raw_sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Synthesize a single active QA sample from raw AmbigQA data."""
        try:
            # Extract data from raw sample
            source_id = raw_sample.get("id", "")
            question = raw_sample.get("question", "").strip()
            annotations = raw_sample.get("annotations", {})

            if not question or not annotations:
                return None

            # Generate clarification questions
            clarification_questions = []
            if "qaPairs" in annotations:
                clarification_questions = self.clean_clarification_questions(annotations["qaPairs"])

            # Skip if no clarification questions found
            if not clarification_questions:
                return None

            # Generate answer enumeration - only for selected questions
            assistant_response = ""
            if "qaPairs" in annotations:
                assistant_response = self.generate_answer_enumeration(annotations["qaPairs"], clarification_questions)

            # Extract context
            provided_context = self.extract_context(annotations)

            # Generate metadata
            gen_meta = {
                "generator_version": "stage2_data_synth_v1",
                "generation_timestamp": datetime.now().isoformat(),
                "seed": self.seed,
                "source_dataset": "ambigqa",
                "source_config": "light",
                "quality_score": None
            }

            # Build synthesized sample
            synthesized_sample = {
                "uid": self.generate_uid(source_id),
                "user_query": question,
                "needs_clarification": True,
                "clarification_questions": clarification_questions,
                "provided_context": provided_context,
                "assistant_response": assistant_response,
                "task_type": "ambiguous",
                "source": "ambigqa",
                "licensing": "cc-by-sa-3.0",
                "gen_meta": gen_meta
            }

            return synthesized_sample

        except Exception as e:
            print(f"Error synthesizing sample {raw_sample.get('id', 'unknown')}: {e}")
            return None

    def synthesize_batch(self, raw_samples: List[Dict[str, Any]], count: int, skip: int = 0) -> List[Dict[str, Any]]:
        """Synthesize a batch of active QA samples."""
        # Skip the first 'skip' samples to avoid overlap with previous shards
        available_samples = raw_samples[skip:]

        # Shuffle for randomization (but with fixed seed)
        shuffled_samples = available_samples.copy()
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

        print(f"Successfully synthesized {len(synthesized_samples)} samples (skipped {skip} samples)")
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
    parser = argparse.ArgumentParser(description="Synthesize active QA samples from AmbigQA")
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input raw AmbigQA JSONL file"
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
    parser.add_argument(
        "--skip",
        type=int,
        default=0,
        help="Number of samples to skip from the beginning (default: 0)"
    )

    args = parser.parse_args()

    # Validate input file
    if not args.input.exists():
        print(f"Error: Input file {args.input} does not exist")
        exit(1)

    # Initialize synthesizer
    synthesizer = AmbigQASynthesizer(seed=args.seed)

    # Load raw data
    print(f"Loading raw data from {args.input}")
    raw_samples = synthesizer.load_raw_data(args.input)

    # Synthesize samples
    print(f"Synthesizing {args.count} samples with seed {args.seed} (skipping {args.skip} samples)")
    synthesized_samples = synthesizer.synthesize_batch(raw_samples, args.count, args.skip)

    # Save results
    synthesizer.save_synthesized_data(synthesized_samples, args.output)

    print(f"\nSynthesis completed!")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"Synthesized: {len(synthesized_samples)} samples")
    print(f"Seed: {args.seed}")

if __name__ == "__main__":
    main()
