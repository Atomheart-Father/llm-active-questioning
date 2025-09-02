#!/usr/bin/env python3
"""
Stage 2 HotpotQA Data Synthesizer v1
Synthesizes active QA samples from HotpotQA dataset with multi-hop clarification questions.

Strategy: Zero simulation - only field mapping and cleaning from original data.
No external model calls, no content generation, strictly traceable to source.

Usage:
    python tools/stage2_data_synth_hotpotqa_v1.py --input data/raw/hotpotqa/20250902/hotpotqa_200.jsonl --output data/interim/shards/stage2_v1/shard-003.jsonl --count 100 --seed 20240905
"""

import argparse
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import random

# Fixed seed for reproducibility
SEED = 20240905

class HotpotQASynthesizer:
    """Synthesizes active QA samples from HotpotQA with multi-hop clarification questions."""

    def __init__(self, seed: int = SEED):
        self.seed = seed
        random.seed(seed)

    def load_raw_data(self, input_file: Path) -> List[Dict[str, Any]]:
        """Load raw HotpotQA data from JSONL file."""
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

    def extract_supporting_sentences(self, sample: Dict[str, Any]) -> List[str]:
        """Extract supporting sentences from context based on supporting_facts."""
        supporting_sentences = []
        context = sample.get("context", {})
        supporting_facts = sample.get("supporting_facts", {})

        if not context or not supporting_facts:
            return supporting_sentences

        titles = context.get("title", [])
        sentences = context.get("sentences", [])
        fact_titles = supporting_facts.get("title", [])
        fact_sent_ids = supporting_facts.get("sent_id", [])

        # Extract supporting sentences
        for title, sent_id in zip(fact_titles, fact_sent_ids):
            try:
                title_idx = titles.index(title)
                if title_idx < len(sentences) and sent_id < len(sentences[title_idx]):
                    supporting_sentences.append(sentences[title_idx][sent_id])
            except (ValueError, IndexError):
                continue

        return supporting_sentences

    def generate_multihop_questions(self, sample: Dict[str, Any]) -> List[str]:
        """Generate 1-2 clarification questions for multi-hop reasoning."""
        questions = []
        supporting_sentences = self.extract_supporting_sentences(sample)

        if len(supporting_sentences) < 2:
            return questions

        question_text = sample.get("question", "")
        answer_text = sample.get("answer", "")
        level = sample.get("level", "medium")
        q_type = sample.get("type", "bridge")

        # Generate questions based on type and level
        if q_type == "bridge" and level in ["medium", "hard"]:
            # For bridge questions, ask about intermediate connections
            if len(supporting_sentences) >= 2:
                questions.append(f"What connects the information about {answer_text.lower()}?")

        elif q_type == "comparison":
            # For comparison questions, ask about differences/similarities
            questions.append(f"What distinguishes the entities compared in '{question_text}'?")

        # Add a second question if we have enough supporting facts
        if len(supporting_sentences) >= 3 and len(questions) < 2:
            questions.append(f"What evidence supports the answer '{answer_text}'?")

        # Limit to 1-2 questions
        return questions[:2] if questions else []

    def generate_multihop_response(self, sample: Dict[str, Any], selected_questions: List[str]) -> str:
        """Generate enumerated response based on supporting facts."""
        supporting_sentences = self.extract_supporting_sentences(sample)
        answer_text = sample.get("answer", "")

        if not supporting_sentences:
            return f"根据证据：{answer_text}"

        # Generate response for each question
        responses = []
        for i, question in enumerate(selected_questions):
            if i == 0:
                responses.append(f"根据多跳推理：{answer_text}")
            else:
                responses.append(f"基于支持证据：{answer_text}")

        return "；".join(responses) if responses else f"答案：{answer_text}"

    def extract_multihop_context(self, sample: Dict[str, Any]) -> str:
        """Extract context information for multi-hop reasoning."""
        context_parts = []

        # Add question type and level
        q_type = sample.get("type", "bridge")
        level = sample.get("level", "medium")
        context_parts.append(f"推理类型: {q_type}，难度: {level}")

        # Add supporting facts count
        supporting_sentences = self.extract_supporting_sentences(sample)
        if supporting_sentences:
            context_parts.append(f"包含 {len(supporting_sentences)} 个支持事实")

        return "。".join(context_parts) if context_parts else ""

    def synthesize_sample(self, raw_sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Synthesize a single active QA sample from raw HotpotQA data."""
        try:
            # Extract data from raw sample
            source_id = raw_sample.get("id", "")
            question = raw_sample.get("question", "").strip()
            answer = raw_sample.get("answer", "")

            if not question or not answer:
                return None

            # Generate clarification questions
            clarification_questions = self.generate_multihop_questions(raw_sample)

            # Skip if no clarification questions found
            if not clarification_questions:
                return None

            # Generate answer enumeration
            assistant_response = self.generate_multihop_response(raw_sample, clarification_questions)

            # Extract context
            provided_context = self.extract_multihop_context(raw_sample)

            # Generate metadata
            gen_meta = {
                "generator_version": "stage2_data_synth_hotpotqa_v1",
                "generation_timestamp": datetime.now().isoformat(),
                "seed": self.seed,
                "source_dataset": "hotpotqa",
                "source_config": "distractor",
                "quality_score": None
            }

            # Build synthesized sample
            synthesized_sample = {
                "uid": self.generate_uid(source_id or str(hash(question))),
                "user_query": question,
                "needs_clarification": True,
                "clarification_questions": clarification_questions,
                "provided_context": provided_context,
                "assistant_response": assistant_response,
                "task_type": "multihop",
                "source": "hotpotqa",
                "licensing": "cc-by-sa-4.0",
                "gen_meta": gen_meta
            }

            return synthesized_sample

        except Exception as e:
            print(f"Error synthesizing sample {raw_sample.get('id', 'unknown')}: {e}")
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
    parser = argparse.ArgumentParser(description="Synthesize active QA samples from HotpotQA")
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input raw HotpotQA JSONL file"
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
    synthesizer = HotpotQASynthesizer(seed=args.seed)

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
