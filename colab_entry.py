#!/usr/bin/env python3
"""
colab_entry.py - One-click data generation entrypoint for Colab/Owner-run

Features:
- Reads environment variables (GEMINI/DeepSeek API keys)
- Generates ALC=4, AR=3, RSD=3 samples
- JSON-only with schema validation
- Provider failover and retry logic
- Outputs to data/gen/<DATE>/<TASK>/ and artifacts_review/
- Owner-run only (long tasks in this script, not CLI)
"""

import os
import json
import time
import uuid
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import project modules
try:
    from streaming_client import StreamingLLMClient as LLMClient
    STREAMING_CLIENT_AVAILABLE = True
except ImportError:
    print("⚠️ streaming_client not available (missing openai), using mock client")
    STREAMING_CLIENT_AVAILABLE = False
    class LLMClient:
        def __init__(self, api_key=None):
            self.client = None
            self.api_key = api_key

        def stream_chat(self, provider, model, messages, max_tokens=1024, json_only=False):
            """Mock stream_chat method"""
            # Return a mock response that always fails to trigger proper error handling
            raise Exception("Mock client: streaming_client not available")

try:
    from schema_validator import SchemaValidator
    from schema_validator import minimal_completion, extract_largest_json
except ImportError:
    print("⚠️ schema_validator not available, using mock validator")
    class SchemaValidator:
        def validate_sample(self, sample):
            return True, []
    def minimal_completion(text, schema):
        return text
    def extract_largest_json(text):
        return text

# Configuration
DATE = datetime.now().strftime("%Y-%m-%d")
TARGETS = {"ALC": 4, "AR": 3, "RSD": 3}
TOKENS = {"ALC": 768, "RSD": 1024, "AR": 1536}
TIMEOUTS = {"idle": 90, "read": 240, "connect": 10}
ALLOW_RSD_FALLBACK = os.getenv("ALLOW_RSD_FALLBACK", "true").lower() == "true"
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "4"))

# Provider routing
PROVIDER_CHAINS = {
    "ALC": ["gemini_flash", "gemini_flash_lite", "deepseek_chat"],
    "AR": ["gemini_pro", "deepseek_reasoner", "gemini_flash"],
    "RSD": ["deepseek_reasoner"] + (["gemini_pro"] if ALLOW_RSD_FALLBACK else [])
}

# Schema definitions
SCHEMAS = {
    "ALC": {
        "type": "object",
        "properties": {
            "turns": {"type": "array", "minItems": 2},
            "labels": {"type": "object"},
            "reasoning": {"type": "string"},
            "source": {"type": "string"}
        },
        "required": ["turns", "labels", "reasoning", "source"]
    },
    "AR": {
        "type": "object",
        "properties": {
            "turns": {"type": "array", "minItems": 3},
            "labels": {"type": "object"},
            "reasoning": {"type": "string"},
            "source": {"type": "string"}
        },
        "required": ["turns", "labels", "reasoning", "source"]
    },
    "RSD": {
        "type": "object",
        "properties": {
            "turns": {"type": "array", "minItems": 2},
            "labels": {"type": "object"},
            "reasoning": {"type": "string"},
            "source": {"type": "string"}
        },
        "required": ["turns", "labels", "reasoning", "source"]
    }
}

SYSTEM_JSON_ONLY = (
    "You MUST output ONE JSON object validating the given schema. "
    "No markdown, no explanations, no polite words. Exactly one control token in model_target."
)


class DataGenerator:
    def __init__(self):
        # Initialize LLM client with API key (prefer GEMINI over DEEPSEEK)
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        if api_key:
            self.client = LLMClient(api_key)
            logger.info("LLM client initialized with API key")
        else:
            logger.warning("No API key found in environment variables (GEMINI_API_KEY or DEEPSEEK_API_KEY)")
            # Create a mock client for testing
            self.client = self._create_mock_client()

        self.validator = SchemaValidator()
        self.stats = {}
        logger.info("DataGenerator initialized")

    def _create_mock_client(self):
        """Create a mock client for testing when no API key is available"""
        class MockLLMClient:
            def __init__(self, api_key=None):
                self.api_key = api_key

            def stream_chat(self, provider, model, messages, max_tokens=1024, json_only=False):
                """Mock stream_chat method that always fails gracefully"""
                raise Exception("No API key available - please set DEEPSEEK_API_KEY or GEMINI_API_KEY")

        return MockLLMClient()

    def has_polite_content(self, text: str) -> bool:
        """Check for polite phrases that should be avoided"""
        polite_phrases = ["谢谢", "请", "please", "kindly", "thank you"]
        return any(phrase in text.lower() for phrase in polite_phrases)

    def validate_model_target(self, sample: Dict) -> bool:
        """Validate model_target has exactly one control token"""
        model_targets = [turn for turn in sample.get("turns", []) if turn.get("role") == "model_target"]
        if len(model_targets) != 1:
            return False

        text = model_targets[0].get("text", "")
        control_tokens = ["<ASK>", "<FINAL>"]
        token_count = sum(1 for token in control_tokens if token in text)
        return token_count == 1 and not self.has_polite_content(text)

    async def generate_single(self, task: str, seed: int) -> Optional[Dict[str, Any]]:
        """Generate a single sample with provider failover"""
        provider_chain = PROVIDER_CHAINS[task]
        max_tokens = TOKENS[task]

        messages = [
            {"role": "system", "content": SYSTEM_JSON_ONLY},
            {"role": "user", "content": f"Task={task}. Return valid JSON only per schema."}
        ]

        for provider_idx, provider in enumerate(provider_chain):
            try:
                logger.info(f"Attempting {task} with {provider} (attempt {provider_idx + 1})")

                # First attempt
                out = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.stream_chat(
                        provider, provider, messages,
                        max_tokens=max_tokens, json_only=True
                    )
                )
                text = out.get("text", "") if isinstance(out, dict) else str(out)

                # Parse and validate
                data = self._parse_and_validate_json(text, task)
                if data and self.validate_model_target(data):
                    logger.info(f"✓ {task} sample generated successfully with {provider}")
                    return data

            except Exception as e:
                logger.warning(f"✗ {task} failed with {provider}: {str(e)[:100]}")
                continue

        # If all providers failed and max_tokens not exceeded, try with higher limit (one retry only)
        if max_tokens < 3072:
            logger.info(f"Retrying {task} with increased token limit: {min(max_tokens * 2, 3072)}")
            return await self.generate_single_with_retry(task, seed, min(max_tokens * 2, 3072))

        logger.error(f"✗ {task} failed all providers and retries")
        return None

    async def generate_single_with_retry(self, task: str, seed: int, retry_tokens: int) -> Optional[Dict[str, Any]]:
        """Retry generation with higher token limit"""
        provider_chain = PROVIDER_CHAINS[task]
        messages = [
            {"role": "system", "content": SYSTEM_JSON_ONLY},
            {"role": "user", "content": f"Task={task}. Return valid JSON only per schema."}
        ]

        for provider in provider_chain[:1]:  # Only try first provider for retry
            try:
                out = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.stream_chat(
                        provider, provider, messages,
                        max_tokens=retry_tokens, json_only=True
                    )
                )
                text = out.get("text", "") if isinstance(out, dict) else str(out)
                data = self._parse_and_validate_json(text, task)
                if data and self.validate_model_target(data):
                    logger.info(f"✓ {task} retry successful with {provider} ({retry_tokens} tokens)")
                    return data
            except Exception as e:
                logger.warning(f"✗ {task} retry failed with {provider}: {str(e)[:100]}")

        return None

    def _parse_and_validate_json(self, text: str, task: str) -> Optional[Dict[str, Any]]:
        """Parse JSON with multiple fallback strategies"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract largest JSON
            candidate = extract_largest_json(text) or text
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                # Use minimal completion
                try:
                    fixed = minimal_completion(text, SCHEMAS[task])
                    return json.loads(fixed)
                except Exception:
                    logger.warning(f"Could not parse JSON for {task}: {text[:200]}...")
                    return None

    async def generate_batch(self, task: str, count: int) -> Dict[str, int]:
        """Generate a batch of samples with concurrency control"""
        logger.info(f"Starting batch generation for {task}: {count} samples")

        # Create directories
        run_dir = Path(f"runs/{DATE}/{task}")
        out_dir = Path(f"data/gen/{DATE}/{task}")
        run_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)

        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        success_count = 0
        fail_count = 0

        async def generate_with_semaphore(seed: int):
            async with semaphore:
                sample = await self.generate_single(task, seed)
                if sample:
                    nonlocal success_count
                    success_count += 1

                    # Save partial
                    sample_id = str(uuid.uuid4())[:8]
                    partial_file = run_dir / f"{sample_id}.partial.jsonl"
                    with open(partial_file, 'w', encoding='utf-8') as f:
                        f.write(json.dumps(sample, ensure_ascii=False) + "\n")

                    logger.info(f"Saved partial for {task} sample {seed + 1}/{count}")
                else:
                    nonlocal fail_count
                    fail_count += 1
                    logger.error(f"Failed to generate {task} sample {seed + 1}/{count}")

        # Generate all samples
        tasks = [generate_with_semaphore(i) for i in range(count)]
        await asyncio.gather(*tasks)

        # Save final batch file
        if success_count > 0:
            partial_files = list(run_dir.glob("*.partial.jsonl"))
            batch_data = []
            for pf in partial_files:
                with open(pf, 'r', encoding='utf-8') as f:
                    batch_data.extend([json.loads(line) for line in f if line.strip()])

            batch_file = out_dir / "part-001.jsonl"
            with open(batch_file, 'w', encoding='utf-8') as f:
                for item in batch_data:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")

            logger.info(f"Saved batch file: {batch_file} ({len(batch_data)} samples)")

        stats = {"success": success_count, "failed": fail_count, "total": count}
        logger.info(f"Batch generation complete for {task}: {stats}")
        return stats

    def generate_quality_report(self):
        """Generate quality report for all generated data"""
        logger.info("Generating quality report...")

        # Load data
        data = {}
        for task in TARGETS.keys():
            folder = Path(f"data/gen/{DATE}/{task}")
            items = []
            for f in ["part-merged.jsonl", "part-001.jsonl"]:
                if (folder / f).exists():
                    with open(folder / f, 'r', encoding='utf-8') as file:
                        items.extend([json.loads(line) for line in file if line.strip()])
            data[task] = items

        # Quality metrics
        metrics = {}
        total_ok = 0
        total_samples = 0

        for task, items in data.items():
            ok_count = 0
            ask_count = 0
            cot_leak = 0

            for sample in items:
                total_samples += 1
                try:
                    is_valid, _ = self.validator.validate_sample(sample)
                    if is_valid and self.validate_model_target(sample):
                        ok_count += 1
                        total_ok += 1

                    # ASK count for ALC
                    if task == "ALC":
                        mt = [t for t in sample.get("turns", []) if t.get("role") == "model_target"]
                        if mt and "<ASK>" in mt[0].get("text", ""):
                            ask_count += 1

                    # CoT leak detection
                    if any(k in json.dumps(sample, ensure_ascii=False) for k in ["<think>", "chain-of-thought", "思维链"]):
                        cot_leak += 1

                except Exception:
                    continue

            metrics[task] = {
                "schema_ok": ok_count,
                "count": len(items),
                "ask": ask_count,
                "cot_leak": cot_leak
            }

        # Distinct-2 for ALC
        import re
        asks = []
        for sample in data.get("ALC", []):
            mt = [t for t in sample.get("turns", []) if t.get("role") == "model_target"]
            if mt and "<ASK>" in mt[0].get("text", ""):
                q = re.sub(r"</?ASK>", "", mt[0].get("text"))
                asks.append(q)

        bg = set()
        total_bg = 0
        for ask in asks:
            tokens = re.findall(r"\w+|[^\s\w]", ask.lower())
            bigrams = list(zip(tokens, tokens[1:]))
            total_bg += len(bigrams)
            bg.update(bigrams)
        distinct2 = len(bg) / total_bg if total_bg else 0.0

        # Save quality report
        art_dir = Path("artifacts_review")
        art_dir.mkdir(exist_ok=True)

        report_content = f"""# Quality Review Report
Date: {DATE}

## Overall Metrics
- Schema OK Total: {total_ok}
- Total Samples: {total_samples}
- Success Rate: {(f"{total_ok/total_samples*100:.1f}%" if total_samples > 0 else "No samples generated")}

## Task Breakdown
"""

        for task, metric in metrics.items():
            report_content += f"""
### {task}
- Schema OK: {metric['schema_ok']}/{metric['count']}
- ASK Rate: {metric['ask']}/{metric['count']} ({(f"{metric['ask']/metric['count']*100:.1f}%" if metric['count'] > 0 else 'N/A')})""" + ("(ALC only)" if task == "ALC" else "")
            report_content += f"""
- CoT Leak: {metric['cot_leak']}/{metric['count']} ({(f"{metric['cot_leak']/metric['count']*100:.1f}%" if metric['count'] > 0 else 'N/A')})
"""

        report_content += f"""
## Diversity Metrics
- ASK Distinct-2: {distinct2:.3f} (ALC only)

## Generation Stats
"""

        for task, stats in self.stats.items():
            report_content += f"- {task}: {stats['success']}/{stats['total']} successful ({(f\"{stats['success']/stats['total']*100:.1f}%\" if stats['total'] > 0 else 'No samples')})\n"

        report_file = art_dir / "quality_review_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        logger.info(f"Quality report saved: {report_file}")

        # Export samples
        samples_dir = art_dir / "samples"
        samples_dir.mkdir(exist_ok=True)

        for task in TARGETS.keys():
            if data[task]:
                sample_file = samples_dir / f"{task}_sample.json"
                with open(sample_file, 'w', encoding='utf-8') as f:
                    json.dump(data[task][0], f, ensure_ascii=False, indent=2)
                logger.info(f"Sample exported: {sample_file}")

    def generate_summary_report(self):
        """Generate generation summary"""
        art_dir = Path("artifacts_review")
        art_dir.mkdir(exist_ok=True)

        summary = f"""# Generation Summary Report
Date: {DATE}
Timestamp: {datetime.now().isoformat()}

## Configuration
- Max Concurrency: {MAX_CONCURRENCY}
- Timeouts: idle={TIMEOUTS['idle']}s, read={TIMEOUTS['read']}s, connect={TIMEOUTS['connect']}s
- Allow RSD Fallback: {ALLOW_RSD_FALLBACK}

## Token Limits
- ALC: {TOKENS['ALC']} (max 3072)
- AR: {TOKENS['AR']} (max 3072)
- RSD: {TOKENS['RSD']} (max 3072)

## Provider Chains
"""

        for task, chain in PROVIDER_CHAINS.items():
            summary += f"- {task}: {' → '.join(chain)}\n"

        summary += ".1f"".1f"".1f"f"""
## Results
"""

        total_success = sum(stats['success'] for stats in self.stats.values())
        total_total = sum(stats['total'] for stats in self.stats.values())

        for task, stats in self.stats.items():
            summary += f"- {task}: {stats['success']}/{stats['total']} ({stats['success']/stats['total']*100:.1f}% if stats['total'] > 0 else 'No samples')\n"

        summary += f"""
## Files Generated
- data/gen/{DATE}/<TASK>/part-001.jsonl (batch files)
- runs/{DATE}/<TASK>/*.partial.jsonl (partial files)
- artifacts_review/quality_review_report.md (quality metrics)
- artifacts_review/samples/<TASK>_sample.json (review samples)

Total Success Rate: {total_success/total_total*100:.1f}% if total_total > 0 else "No samples generated"
"""

        summary_file = art_dir / "generation_summary.md"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(summary)

        logger.info(f"Summary report saved: {summary_file}")


async def main():
    """Main execution function"""
    logger.info("🚀 Starting Colab One-Click Generation")
    logger.info(f"Date: {DATE}")
    logger.info(f"Targets: {TARGETS}")

    generator = DataGenerator()

    # Generate all tasks
    for task, count in TARGETS.items():
        if count > 0:
            logger.info(f"Starting {task} generation: {count} samples")
            stats = await generator.generate_batch(task, count)
            generator.stats[task] = stats

    # Generate reports
    logger.info("Generating quality and summary reports...")
    generator.generate_quality_report()
    generator.generate_summary_report()

    logger.info("✅ Generation complete!")
    logger.info("Review artifacts_review/ directory for results")

    # Show final stats
    total_success = sum(stats['success'] for stats in generator.stats.values())
    total_total = sum(stats['total'] for stats in generator.stats.values())
    if total_total > 0:
        success_rate = total_success/total_total*100
        logger.info(f"Final Stats: {total_success}/{total_total} successful ({success_rate:.1f}%)")
    else:
        logger.info(f"Final Stats: {total_success}/{total_total} successful (no samples generated)")


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())
