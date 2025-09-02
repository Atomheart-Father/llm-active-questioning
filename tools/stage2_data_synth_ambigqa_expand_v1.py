#!/usr/bin/env python3
"""
Stage 2 Data Synthesis - AmbigQA Expansion Script (shard-004a)
Synthesizes 500 additional AmbigQA samples for expansion

Features:
- Reads expanded raw AmbigQA data (≥2000 samples)
- Skips first 712 samples to ensure non-overlap with previous shards
- Generates clarification questions based on ambiguity
- Maps to target schema: uid, user_query, needs_clarification, clarification_questions, provided_context, assistant_response, task_type, source, licensing, gen_meta
- Outputs to data/interim/shards/stage2_v1/shard-004a.jsonl
"""

import json
import hashlib
import random
from pathlib import Path
from datetime import datetime

def generate_uid(source_id, dataset_name):
    """Generate unique ID based on source ID and dataset"""
    content = f"{dataset_name}_{source_id}_{datetime.now().isoformat()}"
    return hashlib.md5(content.encode()).hexdigest()

def synthesize_ambigqa_sample(raw_sample, sample_index):
    """Synthesize a single AmbigQA sample for active questioning"""

    # Extract basic information
    sample_id = raw_sample.get('id', f"ambigqa_{sample_index}")
    question = raw_sample['question']
    annotations = raw_sample['annotations']

    # Generate UID
    uid = generate_uid(sample_id, "ambigqa")

    # Extract clarification questions from qaPairs
    clarification_questions = []
    provided_context = ""
    assistant_response = ""

    if 'qaPairs' in annotations and annotations['qaPairs']:
        qa_pairs = annotations['qaPairs'][0]  # Take first qaPairs entry

        # Extract clarification questions
        if 'question' in qa_pairs:
            clarification_questions = qa_pairs['question'][:2]  # Limit to 2 questions

        # Extract provided context from first qa pair
        if 'context' in qa_pairs and qa_pairs.get('context'):
            provided_context = qa_pairs['context']

        # Generate assistant response as enumerated summary
        if 'answer' in qa_pairs and qa_pairs['answer']:
            answers = qa_pairs['answer']
            if isinstance(answers[0], list):
                answers = answers[0]

            enumerated_answers = []
            for i, answer in enumerate(answers[:len(clarification_questions)]):
                enumerated_answers.append(f"若问题{i+1}则答案：{answer}")

            assistant_response = "；".join(enumerated_answers)

    # Ensure we have at least one clarification question
    if not clarification_questions:
        clarification_questions = ["这个问题存在什么歧义？"]

    # Ensure assistant response
    if not assistant_response:
        assistant_response = "这是一个需要澄清的问题"

    # Build the synthesized sample
    synthesized = {
        "uid": uid,
        "user_query": question,
        "needs_clarification": True,
        "clarification_questions": clarification_questions,
        "provided_context": provided_context,
        "assistant_response": assistant_response,
        "task_type": "ambiguous",
        "source": "ambigqa",
        "licensing": "cc-by-sa-3.0",
        "gen_meta": {
            "synthesis_method": "stage2_ambigqa_expand_v1",
            "raw_sample_id": sample_id,
            "synthesis_timestamp": datetime.now().isoformat(),
            "field_mapping": "qaPairs.question -> clarification_questions, qaPairs.answer -> assistant_response"
        }
    }

    return synthesized

def main():
    """Main synthesis function"""
    print("=== Stage 2 AmbigQA Expansion Synthesis (shard-004a) ===")

    # Configuration
    raw_data_file = "data/raw/ambigqa/20250903/ambigqa_2000.jsonl"
    output_file = "data/interim/shards/stage2_v1/shard-004a.jsonl"
    skip_samples = 712  # Skip first 712 to ensure non-overlap
    target_samples = 500

    # Load raw data
    raw_samples = []
    with open(raw_data_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                raw_samples.append(json.loads(line))

    print(f"Loaded {len(raw_samples)} raw AmbigQA samples")
    print(f"Will skip first {skip_samples} samples, synthesize {target_samples} new samples")

    # Select samples (skip first 712, take next 500)
    selected_samples = raw_samples[skip_samples:skip_samples + target_samples]
    print(f"Selected {len(selected_samples)} samples for synthesis")

    # Synthesize samples
    synthesized_samples = []
    for i, raw_sample in enumerate(selected_samples):
        try:
            synthesized = synthesize_ambigqa_sample(raw_sample, skip_samples + i)
            synthesized_samples.append(synthesized)
        except Exception as e:
            print(f"Error synthesizing sample {skip_samples + i}: {e}")
            continue

    print(f"Successfully synthesized {len(synthesized_samples)} samples")

    # Save synthesized data
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        for sample in synthesized_samples:
            f.write(json.dumps(sample, ensure_ascii=False))
            f.write('\n')

    print(f"Saved synthesized data to {output_file}")

    # Print sample statistics
    print("\n=== Synthesis Statistics ===")
    print(f"Total synthesized: {len(synthesized_samples)}")
    print(f"Task type distribution: all 'ambiguous'")
    print(f"Licensing: all 'cc-by-sa-3.0'")
    print(f"Source: all 'ambigqa'")

    # Sample clarification questions stats
    question_counts = [len(s['clarification_questions']) for s in synthesized_samples]
    print(f"Average clarification questions per sample: {sum(question_counts) / len(question_counts):.1f}")
    print(f"Min clarification questions: {min(question_counts)}")
    print(f"Max clarification questions: {max(question_counts)}")

if __name__ == "__main__":
    main()
