#!/usr/bin/env python3
"""
Quality Metrics Unit Tests

Tests for Disambig-F1, Clarify-Win-Rate, and CompactnessScore calculations.
No external API calls, pure calculation testing.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from review.metrics_disambig import DisambigF1Calculator
from review.metrics_clarify_win import ClarifyWinRateCalculator
from review.metrics_compactness import CompactnessScoreCalculator

class TestMetrics:
    """Quality metrics tests"""

    def setup_method(self):
        """Setup test fixtures"""
        self.disambig_calc = DisambigF1Calculator()
        self.win_rate_calc = ClarifyWinRateCalculator()
        self.compactness_calc = CompactnessScoreCalculator()

    def test_disambig_f1_calculation(self):
        """Test Disambig-F1 calculation"""
        sample = {
            "clarify_tree": {
                "depth": 2,
                "nodes": [
                    {"id": "Q1", "children": ["Q1A", "Q1B"]},
                    {"id": "Q1A", "children": []}
                ]
            },
            "evidence_ids": ["hotpot:d123#sent5", "ambigqa:test#sent1"]
        }

        score = self.disambig_calc.calculate_disambig_f1(sample)
        assert 0.0 <= score <= 1.0

    def test_disambig_f1_no_tree(self):
        """Test Disambig-F1 with no tree"""
        sample = {
            "evidence_ids": ["hotpot:d123#sent5"]
        }

        score = self.disambig_calc.calculate_disambig_f1(sample)
        assert score == 0.5  # Default for no reference data

    def test_clarify_win_rate_calculation(self):
        """Test Clarify-Win-Rate calculation"""
        samples = [
            {
                "preference": {
                    "direct_answer": {"score": 0.4},
                    "clarify_then_answer": {"score": 0.7},
                    "label": "clarify"
                }
            },
            {
                "preference": {
                    "direct_answer": {"score": 0.8},
                    "clarify_then_answer": {"score": 0.3},
                    "label": "direct"
                }
            }
        ]

        win_rate = self.win_rate_calc.calculate_clarify_win_rate(samples)
        assert 0.0 <= win_rate <= 1.0
        assert win_rate == 0.5  # 1 win out of 2 samples

    def test_clarify_win_rate_no_preference(self):
        """Test Clarify-Win-Rate with no preference data"""
        samples = [{"turns": []}, {"labels": {}}]

        win_rate = self.win_rate_calc.calculate_clarify_win_rate(samples)
        assert win_rate == 0.0

    def test_compactness_score_calculation(self):
        """Test CompactnessScore calculation"""
        sample = {
            "reasoning": {
                "compact_rationale": {
                    "connectors": ["if", "then", "because"],
                    "steps": 3
                }
            }
        }

        score = self.compactness_calc.calculate_compactness_score(sample)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Good connectors and steps

    def test_compactness_score_no_rationale(self):
        """Test CompactnessScore with no rationale"""
        sample = {
            "reasoning": {"actions": ["ASK"]}
        }

        score = self.compactness_calc.calculate_compactness_score(sample)
        assert score == 0.0

    def test_compactness_score_invalid_connectors(self):
        """Test CompactnessScore with invalid connectors"""
        sample = {
            "reasoning": {
                "compact_rationale": {
                    "connectors": ["invalid_connector"],
                    "steps": 3
                }
            }
        }

        score = self.compactness_calc.calculate_compactness_score(sample)
        assert 0.0 <= score <= 1.0

    def test_compactness_score_invalid_steps(self):
        """Test CompactnessScore with invalid steps"""
        sample = {
            "reasoning": {
                "compact_rationale": {
                    "connectors": ["if", "then"],
                    "steps": 10  # Too many steps
                }
            }
        }

        score = self.compactness_calc.calculate_compactness_score(sample)
        assert 0.0 <= score <= 1.0
        assert score < 0.8  # Should be penalized for too many steps

    def test_batch_compactness_calculation(self):
        """Test batch compactness calculation"""
        samples = [
            {
                "reasoning": {
                    "compact_rationale": {
                        "connectors": ["if", "then"],
                        "steps": 2
                    }
                }
            },
            {
                "reasoning": {
                    "compact_rationale": {
                        "connectors": ["because", "therefore"],
                        "steps": 4
                    }
                }
            }
        ]

        stats = self.compactness_calc.calculate_batch_compactness(samples)

        assert "avg_score" in stats
        assert "distribution" in stats
        assert "connector_usage" in stats
        assert stats["total_samples"] == 2
        assert 0.0 <= stats["avg_score"] <= 1.0

    def test_preference_distribution_analysis(self):
        """Test preference distribution analysis"""
        samples = [
            {
                "preference": {
                    "direct_answer": {"score": 0.4},
                    "clarify_then_answer": {"score": 0.7},
                    "label": "clarify"
                }
            }
        ]

        stats = self.win_rate_calc.calculate_preference_distribution(samples)

        assert "total_samples" in stats
        assert "samples_with_preference" in stats
        assert "clarify_wins" in stats
        assert "direct_wins" in stats
        assert "avg_clarify_score" in stats
        assert "avg_direct_score" in stats

    def test_evidence_id_validation(self):
        """Test evidence ID validation in Disambig-F1"""
        # Valid evidence IDs
        sample = {
            "evidence_ids": ["hotpot:d123#sent5", "ambigqa:test#sent1"]
        }

        score = self.disambig_calc.calculate_disambig_f1(sample)
        assert score >= 0.0

    def test_tree_structure_validation(self):
        """Test tree structure validation in Disambig-F1"""
        # Valid tree structure
        sample = {
            "clarify_tree": {
                "depth": 2,
                "nodes": [
                    {"id": "Q1", "children": ["Q1A"]},
                    {"id": "Q1A", "children": []}
                ]
            }
        }

        score = self.disambig_calc.calculate_disambig_f1(sample)
        assert score >= 0.0

        # Invalid tree structure (depth too high)
        sample_invalid = {
            "clarify_tree": {
                "depth": 4,  # Too deep
                "nodes": []
            }
        }

        score_invalid = self.disambig_calc.calculate_disambig_f1(sample_invalid)
        assert score_invalid >= 0.0  # Should still return a score

    def test_connector_usage_analysis(self):
        """Test connector usage analysis"""
        samples = [
            {
                "reasoning": {
                    "compact_rationale": {
                        "connectors": ["if", "then", "because"],
                        "steps": 3
                    }
                }
            }
        ]

        stats = self.compactness_calc.calculate_batch_compactness(samples)

        connector_usage = stats["connector_usage"]
        assert "if" in connector_usage
        assert "then" in connector_usage
        assert "because" in connector_usage

        for conn, data in connector_usage.items():
            assert "count" in data
            assert "percentage" in data

if __name__ == "__main__":
    # Run basic smoke tests
    print("Running metrics smoke tests...")

    # Test Disambig-F1
    disambig_calc = DisambigF1Calculator()
    sample = {
        "clarify_tree": {"depth": 1, "nodes": [{"id": "Q1", "children": []}]},
        "evidence_ids": ["hotpot:d123#sent5"]
    }
    disambig_score = disambig_calc.calculate_disambig_f1(sample)
    print(f"✅ Disambig-F1 score: {disambig_score:.3f}")

    # Test Clarify-Win-Rate
    win_rate_calc = ClarifyWinRateCalculator()
    pref_samples = [{
        "preference": {
            "direct_answer": {"score": 0.4},
            "clarify_then_answer": {"score": 0.6},
            "label": "clarify"
        }
    }]
    win_rate = win_rate_calc.calculate_clarify_win_rate(pref_samples)
    print(f"✅ Clarify-Win-Rate: {win_rate:.3f}")

    # Test CompactnessScore
    compactness_calc = CompactnessScoreCalculator()
    compact_sample = {
        "reasoning": {
            "compact_rationale": {
                "connectors": ["if", "then"],
                "steps": 2
            }
        }
    }
    compactness_score = compactness_calc.calculate_compactness_score(compact_sample)
    print(f"✅ CompactnessScore: {compactness_score:.3f}")

    # Validate ranges
    if all(0 <= score <= 1 for score in [disambig_score, win_rate, compactness_score]):
        print("✅ All metrics smoke tests passed")
    else:
        print("❌ Metrics smoke test failed")
        sys.exit(1)
