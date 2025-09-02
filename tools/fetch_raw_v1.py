#!/usr/bin/env python3
"""
Stage 2 Raw Data Fetcher v1
Fetches raw datasets from Hugging Face and saves them locally with provenance tracking.

Supported datasets:
- ambigqa: AmbigQA dataset for ambiguous questions (sewon/ambig_qa, light config)
- gsm8k: GSM8K dataset for math reasoning (openai/gsm8k)
- hotpotqa: HotpotQA dataset for multi-hop reasoning (hotpotqa/hotpot_qa, distractor config)
- asqa: ASQA dataset for ambiguous long-form QA (din0s/asqa)
- strategyqa: StrategyQA dataset for implicit multi-step reasoning (voidful/StrategyQA)

Usage:
    python tools/fetch_raw_v1.py --name ambigqa --n 200 --out data/raw/ambigqa/20250902/ambigqa_200.jsonl
    python tools/fetch_raw_v1.py --name gsm8k --n 200 --out data/raw/gsm8k/20250902/gsm8k_200.jsonl
"""

import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import hashlib

try:
    from datasets import load_dataset
    from tqdm import tqdm
except ImportError as e:
    print(f"Missing required packages: {e}")
    print("Please install with: pip install datasets tqdm")
    exit(1)

# Dataset mappings - only configuration, no business logic
DATASETS = {
    "ambigqa": {
        "hf_id": "sewon/ambig_qa",
        "config": "light",
        "split": "train",
        "license": "CC-BY-SA-4.0"
    },
    "gsm8k": {
        "hf_id": "openai/gsm8k",
        "config": None,
        "split": "train",
        "license": "MIT"
    },
    "hotpotqa": {
        "hf_id": "hotpotqa/hotpot_qa",
        "config": "distractor",
        "split": "train",
        "license": "CC-BY-SA-4.0"
    },
    "asqa": {
        "hf_id": "din0s/asqa",
        "config": None,
        "split": "train",
        "license": "MIT"
    },
    "strategyqa": {
        "hf_id": "voidful/StrategyQA",
        "config": None,
        "split": "train",
        "license": "CC-BY-4.0"
    }
}


class RawDataFetcher:
    """Fetches and processes raw datasets with provenance tracking."""

    def __init__(self):
        self.provenance_fields = [
            'uid', 'source_dataset', 'source_id', 'url_or_path',
            'license', 'created_at'
        ]

    def fetch_ambigqa(self, count: int, output_dir: Path) -> List[Dict[str, Any]]:
        """Fetch AmbigQA dataset samples from Hugging Face."""
        print(f"Loading AmbigQA dataset from sewon/ambig_qa (light config)...")

        try:
            # Load the AmbigQA dataset using the correct HF ID
            dataset = load_dataset("sewon/ambig_qa", "light", split="train")

            # Take first 'count' samples
            samples = []
            for i, item in enumerate(dataset):
                if i >= count:
                    break

                sample = {
                    "id": item.get("id", f"ambigqa_{i}"),
                    "question": item.get("question", ""),
                    "annotations": item.get("annotations", {}),
                    "nq_answer": item.get("nq_answer", ""),
                    "aq_answers": item.get("aq_answers", []),
                    "disambiguations": item.get("disambiguations", [])
                }
                samples.append(sample)

            print(f"Successfully loaded {len(samples)} AmbigQA samples from sewon/ambig_qa")
            return samples

        except Exception as e:
            print(f"Error loading AmbigQA dataset: {e}")
            print("Please ensure you have internet connection and required permissions")
            print("If HF is unavailable, download from: https://nlp.cs.washington.edu/ambigqa/")
            return []

    def fetch_gsm8k(self, count: int, output_dir: Path) -> List[Dict[str, Any]]:
        """Fetch GSM8K dataset samples."""
        print(f"Loading GSM8K dataset...")

        try:
            # Load the GSM8K dataset
            dataset = load_dataset("gsm8k", "main", split="train")

            # Take first 'count' samples
            samples = []
            for i, item in enumerate(dataset):
                if i >= count:
                    break

                sample = {
                    "id": item.get("id", f"gsm8k_{i}"),
                    "question": item.get("question", ""),
                    "answer": item.get("answer", ""),
                    "solution": item.get("solution", "") if "solution" in item else ""
                }
                samples.append(sample)

            print(f"Successfully loaded {len(samples)} GSM8K samples")
            return samples

        except Exception as e:
            print(f"Error loading GSM8K dataset: {e}")
            print("Please ensure you have internet connection and required permissions")
            return []

    def save_samples(self, samples: List[Dict[str, Any]], output_file: Path):
        """Save samples to JSON file."""
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            for sample in samples:
                json.dump(sample, f, ensure_ascii=False)
                f.write('\n')

        print(f"Saved {len(samples)} samples to {output_file}")

    def generate_uid(self, source_dataset: str, source_id: str) -> str:
        """Generate unique identifier for a sample."""
        content = f"{source_dataset}_{source_id}_{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def update_provenance(self, provenance_file: Path, samples: List[Dict[str, Any]],
                         source_dataset: str, license_info: str = "unknown"):
        """Update provenance CSV file with sample information."""
        provenance_file.parent.mkdir(parents=True, exist_ok=True)

        # Read existing provenance if file exists
        existing_uids = set()
        if provenance_file.exists():
            with open(provenance_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_uids.add(row['uid'])

        # Append new entries
        with open(provenance_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.provenance_fields)

            # Write header if file is new
            if not existing_uids:
                writer.writeheader()

            created_at = datetime.now().isoformat()

            for sample in samples:
                source_id = sample.get("id", "unknown")
                uid = self.generate_uid(source_dataset, source_id)

                # Skip if already exists
                if uid in existing_uids:
                    continue

                row = {
                    'uid': uid,
                    'source_dataset': source_dataset,
                    'source_id': source_id,
                    'url_or_path': f"huggingface:{source_dataset}",
                    'license': license_info,
                    'created_at': created_at
                }
                writer.writerow(row)

        print(f"Updated provenance file: {provenance_file}")

    def print_sample_stats(self, samples: List[Dict[str, Any]], dataset_name: str):
        """Print statistics about the fetched samples."""
        print(f"\n=== {dataset_name.upper()} Dataset Statistics ===")
        print(f"Total samples: {len(samples)}")

        if samples:
            print("\nSample entries:")
            for i, sample in enumerate(samples[:3]):
                print(f"\n--- Sample {i+1} ---")
                for key, value in sample.items():
                    if isinstance(value, (list, dict)):
                        print(f"{key}: {type(value).__name__} with {len(value)} items")
                    else:
                        print(f"{key}: {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")

    def fetch_dataset(self, dataset_name: str, count: int, output_file: Path,
                     provenance_file: Path):
        """Main method to fetch a specific dataset."""
        print(f"Fetching {count} samples from {dataset_name}...")

        # Get dataset configuration
        if dataset_name.lower() not in DATASETS:
            print(f"Unsupported dataset: {dataset_name}")
            print(f"Available datasets: {list(DATASETS.keys())}")
            return False

        config = DATASETS[dataset_name.lower()]

        # Fetch samples based on dataset
        if dataset_name.lower() == "ambigqa":
            samples = self.fetch_ambigqa(count, output_file.parent)
        elif dataset_name.lower() == "gsm8k":
            samples = self.fetch_gsm8k(count, output_file.parent)
        else:
            print(f"Fetching method not implemented for {dataset_name}")
            return False

        if not samples:
            print(f"No samples fetched for {dataset_name}")
            return False

        # Save samples
        self.save_samples(samples, output_file)

        # Update provenance
        self.update_provenance(provenance_file, samples, dataset_name.lower(), config["license"])

        # Print statistics
        self.print_sample_stats(samples, dataset_name)

        print(f"\nSuccessfully processed {dataset_name} dataset!")
        return True


def main():
    parser = argparse.ArgumentParser(description="Fetch raw datasets for Stage 2")
    parser.add_argument(
        "--name",
        required=True,
        choices=list(DATASETS.keys()),
        help="Dataset to fetch"
    )
    parser.add_argument(
        "--n",
        type=int,
        default=200,
        help="Number of samples to fetch (default: 200)"
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output file path (e.g., data/raw/ambigqa/20250902/ambigqa_200.jsonl)"
    )
    parser.add_argument(
        "--provenance-file",
        type=Path,
        default=Path("data/processed/active_qa_v1/provenance.csv"),
        help="Path to provenance CSV file"
    )

    args = parser.parse_args()

    # Validate output file directory
    if not args.out.parent.exists():
        print(f"Creating output directory: {args.out.parent}")
        args.out.parent.mkdir(parents=True, exist_ok=True)

    # Initialize fetcher and process
    fetcher = RawDataFetcher()
    success = fetcher.fetch_dataset(
        args.name,
        args.n,
        args.out,
        args.provenance_file
    )

    if success:
        print("\nDataset fetch completed successfully!")
        print(f"Data saved to: {args.out}")
        print(f"Provenance information saved to {args.provenance_file}")
    else:
        print("\nDataset fetch failed!")
        exit(1)


if __name__ == "__main__":
    main()
