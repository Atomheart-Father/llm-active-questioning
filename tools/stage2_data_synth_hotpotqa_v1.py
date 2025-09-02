#!/usr/bin/env python3
"""
Stage 2 Data Synthesis - HotpotQA Shard-005 Script
Synthesizes 100 additional HotpotQA samples for shard-005

Features:
- Reads HotpotQA raw data (200 samples)
- Generates clarification questions based on multi-hop reasoning
- Maps to target schema: uid, user_query, needs_clarification, clarification_questions, provided_context, assistant_response, task_type, source, licensing, gen_meta
- Outputs to data/interim/shards/stage2_v1/shard-005.jsonl
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

def generate_clarification_questions_hotpotqa(question, context, supporting_facts):
    """Generate clarification questions for HotpotQA multi-hop reasoning"""

    # 基于supporting_facts生成澄清问题
    clarification_questions = []

    if supporting_facts and 'title' in supporting_facts:
        titles = supporting_facts['title']
        if len(titles) >= 2:
            # 为多跳推理生成澄清问题
            clarification_questions.append(f"关于'{titles[0]}'的什么信息是解答这个问题所必需的？")
            clarification_questions.append(f"关于'{titles[1]}'的什么信息是解答这个问题所必需的？")
        elif len(titles) == 1:
            clarification_questions.append(f"关于'{titles[0]}'还需要什么额外信息来完全回答这个问题？")

    # 确保至少有一个问题
    if not clarification_questions:
        clarification_questions.append("这个问题需要哪些关键信息来回答？")

    return clarification_questions[:2]  # 限制为最多2个问题

def synthesize_hotpotqa_sample(raw_sample, sample_index):
    """Synthesize a single HotpotQA sample for active questioning"""

    # Extract basic information
    sample_id = raw_sample.get('id', f"hotpotqa_{sample_index}")
    question = raw_sample['question']
    context = raw_sample.get('context', {})
    supporting_facts = raw_sample.get('supporting_facts', {})

    # Generate UID
    uid = generate_uid(sample_id, "hotpotqa")

    # Generate clarification questions
    clarification_questions = generate_clarification_questions_hotpotqa(question, context, supporting_facts)

    # Format provided context
    provided_context = ""
    if context and 'sentences' in context:
        # 提取相关的supporting facts作为上下文
        relevant_sentences = []
        if supporting_facts and 'title' in supporting_facts and 'sent_id' in supporting_facts:
            titles = supporting_facts['title']
            sent_ids = supporting_facts['sent_id']

            for title, sent_id in zip(titles, sent_ids):
                if title in context.get('title', []) and sent_id < len(context['sentences']):
                    sentence_idx = context['title'].index(title)
                    if sentence_idx < len(context['sentences']):
                        relevant_sentences.extend(context['sentences'][sentence_idx][:sent_id + 1])

        if relevant_sentences:
            provided_context = " ".join(relevant_sentences[:3])  # 限制上下文长度

    # Generate assistant response based on supporting facts
    assistant_response = ""
    if supporting_facts and 'title' in supporting_facts:
        titles = supporting_facts['title']
        if len(titles) >= 2:
            assistant_response = f"若问题1则答案：需要{titles[0]}的相关信息；若问题2则答案：需要{titles[1]}的相关信息"
        elif len(titles) == 1:
            assistant_response = f"若问题1则答案：需要{titles[0]}的相关信息"

    if not assistant_response:
        assistant_response = "这是一个需要多跳推理的问题"

    # Build the synthesized sample
    synthesized = {
        "uid": uid,
        "user_query": question,
        "needs_clarification": True,
        "clarification_questions": clarification_questions,
        "provided_context": provided_context,
        "assistant_response": assistant_response,
        "task_type": "multihop",
        "source": "hotpotqa",
        "licensing": "cc-by-sa-4.0",
        "gen_meta": {
            "synthesis_method": "stage2_hotpotqa_v1",
            "raw_sample_id": sample_id,
            "synthesis_timestamp": datetime.now().isoformat(),
            "supporting_facts_count": len(supporting_facts.get('title', [])),
            "field_mapping": "supporting_facts -> clarification_questions, context -> provided_context"
        }
    }

    return synthesized

def main():
    """Main synthesis function"""
    print("=== Stage 2 HotpotQA Synthesis (shard-005) ===")

    # Configuration
    raw_data_file = "data/raw/hotpotqa/20250902/hotpotqa_200.jsonl"
    output_file = "data/interim/shards/stage2_v1/shard-005.jsonl"
    target_samples = 100

    # Load raw data
    raw_samples = []
    with open(raw_data_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                raw_samples.append(json.loads(line))

    print(f"Loaded {len(raw_samples)} raw HotpotQA samples")

    # Select samples (skip already used ones, take next 100)
    # We already used 100 samples for shard-003, so skip first 100
    skip_samples = 100
    selected_samples = raw_samples[skip_samples:skip_samples + target_samples]
    print(f"Selected {len(selected_samples)} samples for synthesis (skipping first {skip_samples})")

    # Synthesize samples
    synthesized_samples = []
    for i, raw_sample in enumerate(selected_samples):
        try:
            synthesized = synthesize_hotpotqa_sample(raw_sample, skip_samples + i)
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
    print(f"Task type distribution: all 'multihop'")
    print(f"Licensing: all 'cc-by-sa-4.0'")
    print(f"Source: all 'hotpotqa'")

    # Sample clarification questions stats
    question_counts = [len(s['clarification_questions']) for s in synthesized_samples]
    print(f"Average clarification questions per sample: {sum(question_counts) / len(question_counts):.1f}")
    print(f"Min clarification questions: {min(question_counts)}")
    print(f"Max clarification questions: {max(question_counts)}")

if __name__ == "__main__":
    main()