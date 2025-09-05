#!/usr/bin/env python3
"""
Schema v1.2 Unit Tests

Tests for new schema fields and validation rules.
No external API calls, pure validation testing.
"""

import json
import pytest
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schema_validator import SchemaValidator

class TestSchemaV1_2Validation:
    """Schema v1.2 validation tests"""

    def setup_method(self):
        """Setup test fixtures"""
        self.validator = SchemaValidator()

    def test_basic_schema_v1_1_compatibility(self):
        """Test that v1.1 samples still validate"""
        sample = {
            "turns": [
                {"role": "user", "text": "What is AI?"},
                {"role": "model_target", "text": "<ASK>What type of AI?</ASK>"}
            ],
            "labels": {
                "ask_required": True,
                "good_question_set": ["What type?"]
            },
            "reasoning": {
                "actions": ["AWARE_GAP", "ASK", "STOP_ASK"]
            },
            "source": "synthetic-gemini"
        }

        is_valid, errors = self.validator.validate_sample(sample)
        assert is_valid, f"v1.1 compatibility failed: {errors}"

    def test_atac_fields_validation(self):
        """Test ATAC field validation"""
        sample = {
            "turns": [
                {"role": "user", "text": "Help me plan a trip"},
                {"role": "model_target", "text": "<ASK>Where do you want to go?</ASK>"}
            ],
            "labels": {
                "ask_required": True,
                "ambiguity_types": ["location", "preference"],
                "ask_options": ["Beach", "Mountain", "City"],
                "branch_map": [
                    {"option": "Beach", "final_id": "F1"},
                    {"option": "Mountain", "final_id": "F2"}
                ]
            },
            "reasoning": {
                "actions": ["AWARE_GAP", "ASK", "STOP_ASK"]
            },
            "source": "synthetic-gemini"
        }

        is_valid, errors = self.validator.validate_sample(sample)
        assert is_valid, f"ATAC validation failed: {errors}"

    def test_atac_invalid_ambiguity_type(self):
        """Test invalid ambiguity type rejection"""
        sample = {
            "turns": [
                {"role": "user", "text": "Test"},
                {"role": "model_target", "text": "<ASK>Test?</ASK>"}
            ],
            "labels": {
                "ask_required": True,
                "ambiguity_types": ["invalid_type"]  # Invalid type
            },
            "reasoning": {"actions": ["ASK"]},
            "source": "synthetic-gemini"
        }

        is_valid, errors = self.validator.validate_sample(sample)
        assert not is_valid
        assert any("invalid" in str(error).lower() for error in errors)

    def test_toc_fields_validation(self):
        """Test ToC field validation"""
        sample = {
            "turns": [
                {"role": "user", "text": "What is machine learning?"},
                {"role": "model_target", "text": "<FINAL>Machine learning is...</FINAL>"}
            ],
            "labels": {
                "ask_required": False,
                "oracle_answer": "Machine learning is a subset of AI"
            },
            "reasoning": {
                "actions": ["AWARE_GAP", "STOP_ASK", "FINALIZE"]
            },
            "clarify_tree": {
                "depth": 2,
                "nodes": [
                    {
                        "id": "Q1",
                        "children": ["Q1A", "Q1B"]
                    }
                ]
            },
            "evidence_ids": ["hotpot:d123#sent5", "ambigqa:test#sent1"],
            "source": "synthetic-gemini"
        }

        is_valid, errors = self.validator.validate_sample(sample)
        assert is_valid, f"ToC validation failed: {errors}"

    def test_toc_invalid_depth(self):
        """Test invalid tree depth rejection"""
        sample = {
            "turns": [
                {"role": "user", "text": "Test"},
                {"role": "model_target", "text": "<FINAL>Answer</FINAL>"}
            ],
            "labels": {"ask_required": False},
            "reasoning": {"actions": ["FINALIZE"]},
            "clarify_tree": {
                "depth": 4,  # Invalid: > 3
                "nodes": []
            },
            "source": "synthetic-gemini"
        }

        is_valid, errors = self.validator.validate_sample(sample)
        assert not is_valid
        assert any("depth" in str(error).lower() for error in errors)

    def test_preference_fields_validation(self):
        """Test FT-Pref field validation"""
        sample = {
            "turns": [
                {"role": "user", "text": "Complex question"},
                {"role": "model_target", "text": "<ASK>Clarify?</ASK>"}
            ],
            "labels": {"ask_required": True},
            "reasoning": {"actions": ["ASK"]},
            "preference": {
                "direct_answer": {"score": 0.4},
                "clarify_then_answer": {"score": 0.7},
                "label": "clarify"
            },
            "source": "synthetic-gemini"
        }

        is_valid, errors = self.validator.validate_sample(sample)
        assert is_valid, f"FT-Pref validation failed: {errors}"

    def test_preference_invalid_score(self):
        """Test invalid preference score rejection"""
        sample = {
            "turns": [
                {"role": "user", "text": "Test"},
                {"role": "model_target", "text": "<ASK>Test</ASK>"}
            ],
            "labels": {"ask_required": True},
            "reasoning": {"actions": ["ASK"]},
            "preference": {
                "direct_answer": {"score": 1.5},  # Invalid: > 1.0
                "clarify_then_answer": {"score": 0.8},
                "label": "clarify"
            },
            "source": "synthetic-gemini"
        }

        is_valid, errors = self.validator.validate_sample(sample)
        assert not is_valid
        assert any("score" in str(error).lower() for error in errors)

    def test_control_symbols_single_only(self):
        """Test single control symbol requirement"""
        # Valid: single ASK
        sample_ask = {
            "turns": [
                {"role": "user", "text": "Test"},
                {"role": "model_target", "text": "<ASK>Question?</ASK>"}
            ],
            "labels": {"ask_required": True},
            "reasoning": {"actions": ["ASK"]},
            "source": "synthetic-gemini"
        }

        is_valid, _ = self.validator.validate_sample(sample_ask)
        assert is_valid

        # Invalid: both ASK and FINAL
        sample_both = {
            "turns": [
                {"role": "user", "text": "Test"},
                {"role": "model_target", "text": "<ASK>Question?</ASK><FINAL>Answer</FINAL>"}
            ],
            "labels": {"ask_required": True},
            "reasoning": {"actions": ["ASK"]},
            "source": "synthetic-gemini"
        }

        is_valid, errors = self.validator.validate_sample(sample_both)
        assert not is_valid
        assert any("只能包含一个控制符" in str(error) for error in errors)

    def test_no_cot_leakage(self):
        """Test CoT leakage detection"""
        sample_with_cot = {
            "turns": [
                {"role": "user", "text": "Test"},
                {"role": "model_target", "text": "<think>I'm thinking</think><ASK>Question?</ASK>"}
            ],
            "labels": {"ask_required": True},
            "reasoning": {"actions": ["ASK"]},
            "source": "synthetic-gemini"
        }

        is_valid, errors = self.validator.validate_sample(sample_with_cot)
        assert not is_valid
        assert any("不能包含<think>" in str(error) for error in errors)

    def test_politeness_filtering(self):
        """Test politeness phrase filtering"""
        sample_with_polite = {
            "turns": [
                {"role": "user", "text": "Test"},
                {"role": "model_target", "text": "<ASK>请问您想要什么？</ASK>"}
            ],
            "labels": {"ask_required": True},
            "reasoning": {"actions": ["ASK"]},
            "source": "synthetic-gemini"
        }

        is_valid, errors = self.validator.validate_sample(sample_with_polite)
        assert not is_valid
        assert any("礼貌语" in str(error) for error in errors)

    def test_compact_rationale_validation(self):
        """Test compact rationale validation"""
        sample = {
            "turns": [
                {"role": "user", "text": "Test"},
                {"role": "model_target", "text": "<ASK>Test?</ASK>"}
            ],
            "labels": {"ask_required": True},
            "reasoning": {
                "actions": ["ASK"],
                "compact_rationale": {
                    "connectors": ["if", "then", "because"],
                    "steps": 3
                }
            },
            "source": "synthetic-gemini"
        }

        is_valid, errors = self.validator.validate_sample(sample)
        assert is_valid, f"Compact rationale validation failed: {errors}"

    def test_invalid_connector(self):
        """Test invalid connector rejection"""
        sample = {
            "turns": [
                {"role": "user", "text": "Test"},
                {"role": "model_target", "text": "<ASK>Test?</ASK>"}
            ],
            "labels": {"ask_required": True},
            "reasoning": {
                "actions": ["ASK"],
                "compact_rationale": {
                    "connectors": ["invalid_connector"],
                    "steps": 3
                }
            },
            "source": "synthetic-gemini"
        }

        is_valid, errors = self.validator.validate_sample(sample)
        assert not is_valid
        assert any("无效的连接词" in str(error) for error in errors)

if __name__ == "__main__":
    # Run basic smoke test
    validator = SchemaValidator()

    # Test basic v1.1 compatibility
    sample = {
        "turns": [{"role": "user", "text": "Hello"}, {"role": "model_target", "text": "<ASK>Hi?</ASK>"}],
        "labels": {"ask_required": True},
        "reasoning": {"actions": ["ASK"]},
        "source": "test"
    }

    is_valid, errors = validator.validate_sample(sample)
    if is_valid:
        print("✅ Schema v1.2 smoke test passed")
    else:
        print(f"❌ Schema v1.2 smoke test failed: {errors}")
        sys.exit(1)
