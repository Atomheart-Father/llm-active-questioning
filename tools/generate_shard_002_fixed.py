#!/usr/bin/env python3
"""
Generate fixed shard-002 with proper skip functionality
"""

import json
import random
from pathlib import Path
from datetime import datetime

# Fixed seed for reproducibility
SEED = 20240904

def load_raw_data(input_file: Path, skip: int = 0) -> list:
    """Load raw data and skip specified number of samples."""
    samples = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i < skip:
                continue
            if line.strip():
                samples.append(json.loads(line))
    print(f"Loaded {len(samples)} raw samples (skipped {skip}) from {input_file}")
    return samples

def fix_sample(sample: dict) -> dict:
    """Apply fixes to a sample."""
    # Map raw fields to target schema
    sample["uid"] = sample["id"]
    sample["user_query"] = sample["question"]

    # Fix task_type
    sample["task_type"] = "ambiguous"

    # Fix licensing format
    if isinstance(sample.get("licensing"), dict):
        sample["licensing"] = "cc-by-sa-3.0"
        sample["licensing_details"] = sample["licensing"]
    else:
        sample["licensing"] = "cc-by-sa-3.0"

    # Add missing fields if they don't exist
    if "source" not in sample:
        sample["source"] = "ambigqa"
    if "needs_clarification" not in sample:
        sample["needs_clarification"] = True
    if "provided_context" not in sample:
        sample["provided_context"] = "歧义类型: multipleQAs"
    if "gen_meta" not in sample:
        sample["gen_meta"] = {
            "generator_version": "stage2_data_synth_v1",
            "generation_timestamp": datetime.now().isoformat(),
            "seed": SEED,
            "source_dataset": "ambigqa",
            "source_config": "light",
            "quality_score": None
        }

    return sample

def generate_clarification_response(sample: dict) -> str:
    """Generate proper clarification response."""
    questions = sample.get("clarification_questions", [])
    if not questions:
        return ""

    # Create aligned responses
    responses = []
    for i in range(len(questions)):
        responses.append(f"若选项{i+1}则[答案{i+1}]")

    return "；".join(responses)

def synthesize_sample(raw_sample: dict) -> dict:
    """Synthesize a single sample."""
    # Apply fixes
    fixed_sample = fix_sample(raw_sample)

    # Generate clarification questions from qaPairs
    annotations = fixed_sample.get("annotations", {})
    qa_pairs = annotations.get("qaPairs", [])

    clarification_questions = []
    for pair in qa_pairs:
        if "question" in pair:
            questions = pair["question"]
            if isinstance(questions, list) and questions:
                clarification_questions.extend(questions[:2])  # Take up to 2 questions from each pair

    # Limit to 1-3 questions
    fixed_sample["clarification_questions"] = clarification_questions[:min(3, len(clarification_questions))] if clarification_questions else []

    # Generate proper response
    fixed_sample["assistant_response"] = generate_clarification_response(fixed_sample)

    return fixed_sample

def main():
    # Set random seed
    random.seed(SEED)

    # File paths
    input_file = Path("data/raw/ambigqa/20250903/ambigqa_2000.jsonl")
    output_file = Path("data/interim/shards/stage2_v1/shard-002.jsonl")

    # Load raw data with skip
    raw_samples = load_raw_data(input_file, skip=156)

    # Shuffle for randomization with a different seed to reduce duplicates
    shuffled_samples = raw_samples.copy()
    random.seed(SEED + 1)  # Use different seed for shuffling
    random.shuffle(shuffled_samples)
    random.seed(SEED)  # Reset seed for consistency

    # Synthesize samples
    synthesized_samples = []
    count = 0
    target_count = 500

    for raw_sample in shuffled_samples:
        if count >= target_count:
            break

        synthesized = synthesize_sample(raw_sample)
        if synthesized:
            synthesized_samples.append(synthesized)
            count += 1

    print(f"Synthesized {len(synthesized_samples)} samples")

    # Save results
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        for sample in synthesized_samples:
            json.dump(sample, f, ensure_ascii=False)
            f.write('\n')

    print(f"Saved {len(synthesized_samples)} samples to {output_file}")

if __name__ == "__main__":
    main()
