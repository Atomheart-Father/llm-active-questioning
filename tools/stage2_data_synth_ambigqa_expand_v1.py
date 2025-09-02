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
    """Synthesize a single AmbigQA sample for active questioning with strict alignment constraints"""

    # Extract basic information
    sample_id = raw_sample.get('id', f"ambigqa_{sample_index}")
    question = raw_sample['question']
    annotations = raw_sample['annotations']

    # Generate UID
    uid = generate_uid(sample_id, "ambigqa")

    # HARD CONSTRAINT: Only process samples with valid qaPairs
    if not annotations.get('qaPairs') or not annotations['qaPairs']:
        return None  # Skip this sample

    qa_pairs = annotations['qaPairs'][0]  # Take first qaPairs entry

    # HARD CONSTRAINT: Must have questions
    if not qa_pairs.get('question') or not qa_pairs['question']:
        return None  # Skip this sample

    # Extract and clean clarification questions (1-3 questions)
    raw_questions = qa_pairs['question']
    clarification_questions = []

    for q in raw_questions[:3]:  # Limit to 3 questions max
        if q and len(q.strip()) > 5:  # Filter out empty or too short questions
            clarification_questions.append(q.strip())

    if not clarification_questions:  # Must have at least 1 valid question
        return None

    # Extract answers with length alignment
    answers = []
    if 'answer' in qa_pairs and qa_pairs['answer']:
        raw_answers = qa_pairs['answer']
        if isinstance(raw_answers[0], list):
            raw_answers = raw_answers[0]

        # Take min length between questions and answers
        min_len = min(len(clarification_questions), len(raw_answers))
        answers = raw_answers[:min_len]
        clarification_questions = clarification_questions[:min_len]  # Trim to match

    if not answers:  # Must have at least 1 answer
        return None

    # Generate assistant response with perfect alignment
    enumerated_answers = []
    for i, answer in enumerate(answers):
        enumerated_answers.append(f"若问题{i+1}则答案：{answer}")

    assistant_response = "；".join(enumerated_answers)

    # Extract provided context from first qa pair if available
    provided_context = ""
    if 'context' in qa_pairs and qa_pairs.get('context'):
        provided_context = qa_pairs['context']

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
            "synthesis_method": "stage2_ambigqa_expand_v1_fixed",
            "raw_sample_id": sample_id,
            "synthesis_timestamp": datetime.now().isoformat(),
            "alignment_verification": f"questions={len(clarification_questions)}, answers={len(answers)}",
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

    # Synthesize samples with filtering
    synthesized_samples = []
    processed_count = 0
    skipped_count = 0
    skip_reasons = {
        'no_qapairs': 0,
        'no_questions': 0,
        'empty_questions': 0,
        'no_answers': 0,
        'processing_error': 0
    }

    # Process samples starting from skip_samples
    current_index = skip_samples

    while len(synthesized_samples) < target_samples and current_index < len(raw_samples):
        raw_sample = raw_samples[current_index]

        try:
            synthesized = synthesize_ambigqa_sample(raw_sample, current_index)

            if synthesized is None:
                # Determine skip reason
                annotations = raw_sample.get('annotations', {})
                if not annotations.get('qaPairs'):
                    skip_reasons['no_qapairs'] += 1
                elif not annotations['qaPairs'][0].get('question'):
                    skip_reasons['no_questions'] += 1
                elif not any(q and len(q.strip()) > 5 for q in annotations['qaPairs'][0]['question'][:3]):
                    skip_reasons['empty_questions'] += 1
                elif not annotations['qaPairs'][0].get('answer'):
                    skip_reasons['no_answers'] += 1
                else:
                    skip_reasons['processing_error'] += 1

                skipped_count += 1
            else:
                synthesized_samples.append(synthesized)

        except Exception as e:
            print(f"Error processing sample {current_index}: {e}")
            skip_reasons['processing_error'] += 1
            skipped_count += 1

        current_index += 1
        processed_count += 1

    print(f"Processed {processed_count} samples, synthesized {len(synthesized_samples)} valid samples, skipped {skipped_count}")

    if len(synthesized_samples) < target_samples:
        print(f"⚠️  Warning: Could only generate {len(synthesized_samples)} valid samples (target: {target_samples})")
        print("This may require expanding the source data range or relaxing constraints")

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

    # Calculate question statistics
    question_counts = [len(s['clarification_questions']) for s in synthesized_samples]
    if question_counts:
        print(f"Average clarification questions per sample: {sum(question_counts) / len(question_counts):.1f}")
        print(f"Min clarification questions: {min(question_counts)}")
        print(f"Max clarification questions: {max(question_counts)}")

    print(f"\nSkip reasons: {skip_reasons}")

if __name__ == "__main__":
    main()
