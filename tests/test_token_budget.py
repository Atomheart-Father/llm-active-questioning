#!/usr/bin/env python3
"""
Token Budget Unit Tests

Tests for adaptive token allocation based on complexity scoring.
No external API calls, pure calculation testing.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from generators.token_budget import TokenBudgetAllocator

class TestTokenBudget:
    """Token budget allocation tests"""

    def setup_method(self):
        """Setup test fixtures"""
        self.allocator = TokenBudgetAllocator()

    def test_complexity_scoring_basic(self):
        """Test basic complexity scoring"""
        sample = {
            "source": "hotpotqa",
            "turns": [{"role": "user", "text": "What is the capital of France?"}],
            "labels": {"ask_required": True}
        }

        score = self.allocator.calculate_complexity_score(sample)
        assert 0.0 <= score <= 1.0
        assert score > 0.1  # Should have some complexity

    def test_source_weight_application(self):
        """Test source weight application"""
        # High weight source
        hotpot_sample = {
            "source": "hotpotqa",
            "turns": [{"role": "user", "text": "Test"}],
            "labels": {}
        }

        # Low weight source
        gsm8k_sample = {
            "source": "gsm8k",
            "turns": [{"role": "user", "text": "Test"}],
            "labels": {}
        }

        hotpot_score = self.allocator.calculate_complexity_score(hotpot_sample)
        gsm8k_score = self.allocator.calculate_complexity_score(gsm8k_sample)

        # Hotpot should have higher complexity score due to source weight
        assert hotpot_score > gsm8k_score

    def test_query_length_complexity(self):
        """Test query length complexity calculation"""
        short_sample = {
            "source": "synthetic",
            "turns": [{"role": "user", "text": "Hi"}],
            "labels": {}
        }

        long_sample = {
            "source": "synthetic",
            "turns": [{"role": "user", "text": " ".join(["word"] * 100)}],
            "labels": {}
        }

        short_score = self.allocator.calculate_complexity_score(short_sample)
        long_score = self.allocator.calculate_complexity_score(long_sample)

        assert long_score > short_score

    def test_ambiguity_complexity(self):
        """Test ambiguity type complexity"""
        low_ambiguity = {
            "source": "synthetic",
            "turns": [{"role": "user", "text": "Test"}],
            "labels": {"ambiguity_types": []}
        }

        high_ambiguity = {
            "source": "synthetic",
            "turns": [{"role": "user", "text": "Test"}],
            "labels": {"ambiguity_types": ["person", "time", "location", "preference", "budget"]}
        }

        low_score = self.allocator.calculate_complexity_score(low_ambiguity)
        high_score = self.allocator.calculate_complexity_score(high_ambiguity)

        assert high_score > low_score

    def test_structural_complexity(self):
        """Test structural complexity (multi-hop/numerical)"""
        simple_sample = {
            "source": "synthetic",
            "turns": [{"role": "user", "text": "What is 2+2?"}],
            "labels": {}
        }

        complex_sample = {
            "source": "synthetic",
            "turns": [{"role": "user", "text": "How many people live in cities that were founded after 1800 and have populations over 1 million?"}],
            "labels": {}
        }

        simple_score = self.allocator.calculate_complexity_score(simple_sample)
        complex_score = self.allocator.calculate_complexity_score(complex_sample)

        assert complex_score > simple_score

    def test_token_allocation_alc(self):
        """Test ALC token allocation"""
        # Low complexity
        simple_sample = {
            "source": "gsm8k",
            "turns": [{"role": "user", "text": "Hi"}],
            "labels": {"ambiguity_types": []}
        }

        # High complexity
        complex_sample = {
            "source": "hotpotqa",
            "turns": [{"role": "user", "text": " ".join(["complex"] * 50)}],
            "labels": {"ambiguity_types": ["person", "time", "location"]}
        }

        simple_tokens = self.allocator.allocate_tokens("ALC", self.allocator.calculate_complexity_score(simple_sample))
        complex_tokens = self.allocator.allocate_tokens("ALC", self.allocator.calculate_complexity_score(complex_sample))

        assert simple_tokens >= 512
        assert complex_tokens > simple_tokens
        assert complex_tokens <= 3072

    def test_token_allocation_ar(self):
        """Test AR token allocation"""
        sample = {
            "source": "synthetic",
            "turns": [{"role": "user", "text": "Test"}],
            "labels": {}
        }

        tokens = self.allocator.allocate_tokens("AR", self.allocator.calculate_complexity_score(sample))
        assert tokens >= 512
        assert tokens <= 3072

    def test_token_allocation_rsd(self):
        """Test RSD token allocation"""
        sample = {
            "source": "synthetic",
            "turns": [{"role": "user", "text": "Test"}],
            "labels": {}
        }

        tokens = self.allocator.allocate_tokens("RSD", self.allocator.calculate_complexity_score(sample))
        assert tokens >= 512
        assert tokens <= 3072

    def test_truncation_recovery(self):
        """Test truncation recovery allocation"""
        original_allocation = 1000

        # Normal recovery
        normal_recovery = self.allocator.handle_truncation_recovery(original_allocation)
        assert normal_recovery == 1500

        # Final field priority
        final_recovery = self.allocator.handle_truncation_recovery(original_allocation, is_final_field=True)
        assert final_recovery == 1500  # Same as normal for this case

        # Max cap
        large_allocation = 3000
        capped_recovery = self.allocator.handle_truncation_recovery(large_allocation)
        assert capped_recovery <= 3072

    def test_sample_allocation_integration(self):
        """Test full sample allocation integration"""
        sample = {
            "source": "hotpotqa",
            "turns": [{"role": "user", "text": "Complex multi-hop question requiring clarification"}],
            "labels": {"ambiguity_types": ["person", "time"]}
        }

        tokens = self.allocator.allocate_tokens_for_sample(sample)
        assert isinstance(tokens, int)
        assert 512 <= tokens <= 3072

    def test_allocation_statistics(self):
        """Test allocation statistics calculation"""
        samples = [
            {"source": "hotpotqa", "turns": [{"role": "user", "text": "Test"}], "labels": {}},
            {"source": "gsm8k", "turns": [{"role": "user", "text": "Test"}], "labels": {}}
        ]

        stats = self.allocator.get_allocation_stats(samples)

        assert "total_samples" in stats
        assert "avg_complexity" in stats
        assert "avg_allocation" in stats
        assert stats["total_samples"] == 2
        assert stats["avg_complexity"] > 0
        assert stats["avg_allocation"] > 0

if __name__ == "__main__":
    # Run basic smoke test
    allocator = TokenBudgetAllocator()

    sample = {
        "source": "synthetic",
        "turns": [{"role": "user", "text": "Test query"}],
        "labels": {"ambiguity_types": ["time"]}
    }

    score = allocator.calculate_complexity_score(sample)
    tokens = allocator.allocate_tokens_for_sample(sample)

    print(f"✅ Complexity score: {score:.3f}")
    print(f"✅ Allocated tokens: {tokens}")

    if 512 <= tokens <= 3072 and 0 <= score <= 1:
        print("✅ Token budget smoke test passed")
    else:
        print("❌ Token budget smoke test failed")
        sys.exit(1)
