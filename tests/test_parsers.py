#!/usr/bin/env python3
"""
Parser Unit Tests

Tests for template parsing and control symbol validation.
No external API calls, pure parsing testing.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schema_validator import SchemaValidator

class TestParsers:
    """Parser functionality tests"""

    def setup_method(self):
        """Setup test fixtures"""
        self.validator = SchemaValidator()

    def test_single_control_symbol_validation(self):
        """Test single control symbol requirement"""
        # Valid: single ASK
        text_ask = "<ASK>What is your name?</ASK>"
        valid_ask, _ = self.validator._validate_control_symbols(text_ask)
        assert valid_ask

        # Valid: single FINAL
        text_final = "<FINAL>The answer is 42</FINAL>"
        valid_final, _ = self.validator._validate_control_symbols(text_final)
        assert valid_final

        # Invalid: both ASK and FINAL
        text_both = "<ASK>Question?</ASK><FINAL>Answer</FINAL>"
        valid_both, errors = self.validator._validate_control_symbols(text_both)
        assert not valid_both
        assert any("只能包含一个控制符" in str(error) for error in errors)

        # Invalid: no control symbols
        text_none = "This is just plain text"
        valid_none, errors = self.validator._validate_control_symbols(text_none)
        assert not valid_none
        assert any("必须包含" in str(error) for error in errors)

    def test_control_symbol_format_validation(self):
        """Test control symbol format validation"""
        # Valid formats
        valid_cases = [
            "<ASK>Simple question?</ASK>",
            "<FINAL>Detailed answer here</FINAL>",
            "<ASK>Multi word question here?</ASK>"
        ]

        for case in valid_cases:
            valid, _ = self.validator._validate_control_symbols(case)
            assert valid, f"Failed to validate: {case}"

        # Invalid formats
        invalid_cases = [
            "<ASK>Incomplete",  # Missing closing tag
            "Incomplete</ASK>",  # Missing opening tag
            "<ASK></ASK>",  # Empty content
            "<FINAL>   </FINAL>"  # Only whitespace
        ]

        for case in invalid_cases:
            valid, errors = self.validator._validate_control_symbols(case)
            assert not valid, f"Should reject: {case}"

    def test_cot_leakage_detection(self):
        """Test CoT leakage detection"""
        # Cases with CoT leakage
        cot_cases = [
            "<think>I'm thinking about this</think><ASK>Question?</ASK>",
            "<ASK>Question?</ASK><think>Now I need to reason</think>",
            "<FINAL>Answer<think>with thinking</think></FINAL>"
        ]

        for case in cot_cases:
            valid, errors = self.validator._validate_control_symbols(case)
            assert not valid, f"Should detect CoT in: {case}"
            assert any("不能包含<think>" in str(error) for error in errors)

        # Valid cases without CoT
        clean_cases = [
            "<ASK>Simple question?</ASK>",
            "<FINAL>Direct answer</FINAL>",
            "<ASK>Question with reasoning but no think tags</ASK>"
        ]

        for case in clean_cases:
            valid, _ = self.validator._validate_control_symbols(case)
            assert valid, f"Should accept clean text: {case}"

    def test_politeness_phrase_detection(self):
        """Test politeness phrase detection"""
        # Cases with politeness phrases
        polite_cases = [
            "<ASK>请问您想要什么？</ASK>",
            "<FINAL>谢谢您的提问</FINAL>",
            "<ASK>您好，请告诉我</ASK>",
            "<FINAL>对不起，我需要澄清</FINAL>"
        ]

        for case in polite_cases:
            valid, errors = self.validator._validate_control_symbols(case)
            assert not valid, f"Should detect politeness in: {case}"
            assert any("礼貌语" in str(error) for error in errors)

        # Clean cases
        clean_cases = [
            "<ASK>What do you want?</ASK>",
            "<FINAL>Here's the answer</FINAL>",
            "<ASK>Tell me more</ASK>"
        ]

        for case in clean_cases:
            valid, _ = self.validator._validate_control_symbols(case)
            assert valid, f"Should accept clean text: {case}"

    def test_json_parsing_robustness(self):
        """Test JSON parsing with various formats"""
        # Clean JSON
        clean_json = '''{
            "turns": [{"role": "user", "text": "Hi"}, {"role": "model_target", "text": "<ASK>Hello?</ASK>"}],
            "labels": {"ask_required": true},
            "reasoning": {"actions": ["ASK"]},
            "source": "test"
        }'''

        sample = self.validator.extract_largest_json(clean_json)
        assert sample is not None
        parsed = self.validator._parse_response(sample, "test query")
        assert parsed is not None

        # JSON with markdown wrapper
        markdown_json = '''```json
        {
            "turns": [{"role": "user", "text": "Hi"}],
            "labels": {"ask_required": true},
            "reasoning": {"actions": ["ASK"]},
            "source": "test"
        }
        ```'''

        sample = self.validator.extract_largest_json(markdown_json)
        assert sample is not None

        # Malformed JSON
        malformed_json = '''{
            "turns": [{"role": "user", "text": "Hi"},
            "labels": {"ask_required": true},
        }'''

        sample = self.validator.extract_largest_json(malformed_json)
        assert sample is None  # Should fail to parse

    def test_minimal_completion(self):
        """Test minimal JSON completion"""
        # Valid JSON (no completion needed)
        valid_json = '{"test": "value"}'
        completed = self.validator.minimal_completion(valid_json, {})
        assert completed == valid_json

        # Incomplete JSON
        incomplete_json = '{"test": "value"'
        completed = self.validator.minimal_completion(incomplete_json, {})
        assert completed == '{"test": "value"}'

        # Empty or invalid
        invalid_json = "not json at all"
        completed = self.validator.minimal_completion(invalid_json, {})
        assert completed == invalid_json  # Should return as-is

    def test_ambiguity_type_validation(self):
        """Test ambiguity type validation"""
        valid_types = ["person", "time", "location", "preference", "budget",
                      "method", "scope", "context", "quantity", "quality"]

        # Test valid types
        for amb_type in valid_types:
            sample = {
                "turns": [{"role": "user", "text": "Test"}, {"role": "model_target", "text": "<ASK>Test?</ASK>"}],
                "labels": {"ask_required": True, "ambiguity_types": [amb_type]},
                "reasoning": {"actions": ["ASK"]},
                "source": "test"
            }
            is_valid, _ = self.validator.validate_sample(sample)
            assert is_valid, f"Should accept valid ambiguity type: {amb_type}"

        # Test invalid type
        sample = {
            "turns": [{"role": "user", "text": "Test"}, {"role": "model_target", "text": "<ASK>Test?</ASK>"}],
            "labels": {"ask_required": True, "ambiguity_types": ["invalid_type"]},
            "reasoning": {"actions": ["ASK"]},
            "source": "test"
        }
        is_valid, errors = self.validator.validate_sample(sample)
        assert not is_valid
        assert any("invalid" in str(error).lower() for error in errors)

    def test_connector_validation(self):
        """Test reasoning connector validation"""
        valid_connectors = ["if", "then", "because", "therefore", "compare", "contrast", "and", "or", "but"]

        # Test valid connectors
        for connector in valid_connectors:
            sample = {
                "turns": [{"role": "user", "text": "Test"}, {"role": "model_target", "text": "<ASK>Test?</ASK>"}],
                "labels": {"ask_required": True},
                "reasoning": {
                    "actions": ["ASK"],
                    "compact_rationale": {
                        "connectors": [connector],
                        "steps": 2
                    }
                },
                "source": "test"
            }
            is_valid, _ = self.validator.validate_sample(sample)
            assert is_valid, f"Should accept valid connector: {connector}"

        # Test invalid connector
        sample = {
            "turns": [{"role": "user", "text": "Test"}, {"role": "model_target", "text": "<ASK>Test?</ASK>"}],
            "labels": {"ask_required": True},
            "reasoning": {
                "actions": ["ASK"],
                "compact_rationale": {
                    "connectors": ["invalid_connector"],
                    "steps": 2
                }
            },
            "source": "test"
        }
        is_valid, errors = self.validator.validate_sample(sample)
        assert not is_valid
        assert any("无效的连接词" in str(error) for error in errors)

if __name__ == "__main__":
    # Run basic smoke tests
    print("Running parser smoke tests...")

    validator = SchemaValidator()

    # Test control symbols
    test_cases = [
        ("<ASK>Valid question?</ASK>", True, "single ASK"),
        ("<FINAL>Valid answer</FINAL>", True, "single FINAL"),
        ("<ASK>Q?</ASK><FINAL>A</FINAL>", False, "both symbols"),
        ("No symbols", False, "no symbols")
    ]

    passed = 0
    for text, expected_valid, description in test_cases:
        is_valid, _ = validator._validate_control_symbols(text)
        if is_valid == expected_valid:
            print(f"✅ {description}: {'PASS' if is_valid else 'PASS (correctly invalid)'}")
            passed += 1
        else:
            print(f"❌ {description}: FAIL")

    # Test politeness detection
    polite_text = "<ASK>请问您好吗？</ASK>"
    is_valid, _ = validator._validate_control_symbols(polite_text)
    if not is_valid:
        print("✅ Politeness detection: PASS")
        passed += 1
    else:
        print("❌ Politeness detection: FAIL")

    # Test CoT detection
    cot_text = "<ASK>Question?</ASK><think>thinking</think>"
    is_valid, _ = validator._validate_control_symbols(cot_text)
    if not is_valid:
        print("✅ CoT detection: PASS")
        passed += 1
    else:
        print("❌ CoT detection: FAIL")

    if passed >= 5:
        print(f"✅ Parser smoke tests passed ({passed}/6)")
    else:
        print(f"❌ Parser smoke tests failed ({passed}/6)")
        sys.exit(1)
