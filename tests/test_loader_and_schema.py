"""Tests for Data Loader and Schema v1.1"""

import pytest
import json
from pathlib import Path
from src.data.loader import DataLoader, Sample, ValidationError, VALID_DOMAINS, VALID_SOURCES


class TestDataLoader:
    """测试数据加载器"""

    def test_valid_sample_loading(self):
        """测试有效样本加载"""
        loader = DataLoader(strict_mode=False)

        # 创建临时测试数据
        test_data = {
            "id": "TEST-001",
            "domain": "planning",
            "source": "human",
            "turns": [
                {"role": "user", "text": "测试问题"},
                {"role": "model_target", "text": "<ASK> 测试澄清 </ASK>"}
            ],
            "labels": {
                "ambiguity_types": ["test"],
                "ask_required": True,
                "good_question_set": ["测试问题"],
                "minimal_clarifications": 1,
                "oracle_answer": None
            },
            "reasoning": {
                "think_stream": "测试思考流",
                "actions": [
                    {"t": "AWARE_GAP", "vars": ["test"]},
                    {"t": "ASK", "q": "测试问题"},
                    {"t": "STOP_ASK"}
                ]
            }
        }

        # 模拟JSONL行
        import io
        json_line = json.dumps(test_data, ensure_ascii=False)

        # 测试解析
        sample = loader._parse_sample(test_data)
        assert sample.id == "TEST-001"
        assert sample.domain == "planning"
        assert sample.source == "human"
        assert len(sample.turns) == 2
        assert sample.labels["ask_required"] is True
        assert len(sample.reasoning["actions"]) == 3

    def test_schema_validation(self):
        """测试schema校验"""
        loader = DataLoader(strict_mode=False)

        # 有效的样本
        valid_sample = Sample(
            id="VALID-001",
            domain="planning",
            source="human",
            turns=[
                {"role": "user", "text": "test"},
                {"role": "model_target", "text": "<ASK> question </ASK>"}
            ],
            labels={
                "ask_required": True,
                "ambiguity_types": ["test"],
                "good_question_set": ["question"],
                "minimal_clarifications": 1,
                "oracle_answer": None
            },
            reasoning={
                "think_stream": "test",
                "actions": [{"t": "AWARE_GAP", "vars": ["test"]}]
            }
        )

        errors = loader._validate_sample(valid_sample)
        # 有效的样本应该没有错误
        error_fields = [e.field for e in errors if e.severity == "error"]
        assert len(error_fields) == 0

    def test_invalid_domain(self):
        """测试无效domain"""
        loader = DataLoader(strict_mode=False)

        invalid_sample = Sample(
            id="INVALID-001",
            domain="invalid_domain",
            source="human",
            turns=[{"role": "user", "text": "test"}],
            labels={"ask_required": True},
            reasoning={"actions": [{"t": "AWARE_GAP", "vars": []}]}
        )

        errors = loader._validate_sample(invalid_sample)
        domain_errors = [e for e in errors if "domain" in e.field and e.severity == "error"]
        assert len(domain_errors) > 0

    def test_missing_required_fields(self):
        """测试缺少必需字段"""
        loader = DataLoader(strict_mode=False)

        # 缺少ask_required
        invalid_sample = Sample(
            id="INVALID-002",
            domain="planning",
            source="human",
            turns=[{"role": "user", "text": "test"}],
            labels={},  # 缺少ask_required
            reasoning={"actions": [{"t": "AWARE_GAP", "vars": []}]}
        )

        errors = loader._validate_sample(invalid_sample)
        required_errors = [e for e in errors if "ask_required" in e.message and e.severity == "error"]
        assert len(required_errors) > 0

        # 缺少actions
        invalid_sample2 = Sample(
            id="INVALID-003",
            domain="planning",
            source="human",
            turns=[{"role": "user", "text": "test"}],
            labels={"ask_required": True},
            reasoning={}  # 缺少actions
        )

        errors2 = loader._validate_sample(invalid_sample2)
        action_errors = [e for e in errors2 if "actions" in e.message and e.severity == "error"]
        assert len(action_errors) > 0

    def test_cot_leakage_detection(self):
        """测试思维链泄漏检测"""
        loader = DataLoader(strict_mode=False)

        # 有效的<think>标签内容
        valid_text = "<think>首先分析用户需求</think><ASK> 请提供更多信息 </ASK>"
        assert not loader._contains_cot_leakage(valid_text)

        # 泄漏到model_target的思维链
        leaked_text = "首先分析这个问题：<ASK> 请澄清 </ASK>"
        assert loader._contains_cot_leakage(leaked_text)

        # 泄漏的英文关键词
        leaked_text2 = "Let me think about this <ASK> question </ASK>"
        assert loader._contains_cot_leakage(leaked_text2)

    def test_turns_validation(self):
        """测试turns校验"""
        loader = DataLoader(strict_mode=False)

        # 缺少user轮次
        invalid_sample = Sample(
            id="INVALID-004",
            domain="planning",
            source="human",
            turns=[{"role": "model_target", "text": "<ASK> test </ASK>"}],  # 只有model_target
            labels={"ask_required": True},
            reasoning={"actions": [{"t": "AWARE_GAP", "vars": []}]}
        )

        errors = loader._validate_sample(invalid_sample)
        turn_errors = [e for e in errors if "user" in e.message and e.severity == "error"]
        assert len(turn_errors) > 0

        # 缺少model_target轮次
        invalid_sample2 = Sample(
            id="INVALID-005",
            domain="planning",
            source="human",
            turns=[{"role": "user", "text": "test"}],  # 只有user
            labels={"ask_required": True},
            reasoning={"actions": [{"t": "AWARE_GAP", "vars": []}]}
        )

        errors2 = loader._validate_sample(invalid_sample2)
        turn_errors2 = [e for e in errors2 if "model_target" in e.message and e.severity == "error"]
        assert len(turn_errors2) > 0

    def test_action_types_validation(self):
        """测试动作类型校验"""
        loader = DataLoader(strict_mode=False)

        # 无效的动作类型
        invalid_sample = Sample(
            id="INVALID-006",
            domain="planning",
            source="human",
            turns=[{"role": "user", "text": "test"}],
            labels={"ask_required": True},
            reasoning={
                "actions": [
                    {"t": "INVALID_ACTION", "vars": []}  # 无效动作类型
                ]
            }
        )

        errors = loader._validate_sample(invalid_sample)
        action_type_errors = [e for e in errors if "action类型" in e.message and e.severity == "error"]
        assert len(action_type_errors) > 0

    def test_ambiguity_types_validation(self):
        """测试歧义类型校验"""
        loader = DataLoader(strict_mode=False)

        # 无效的歧义类型
        invalid_sample = Sample(
            id="INVALID-007",
            domain="planning",
            source="human",
            turns=[{"role": "user", "text": "test"}],
            labels={
                "ask_required": True,
                "ambiguity_types": ["invalid_type"]  # 无效类型
            },
            reasoning={"actions": [{"t": "AWARE_GAP", "vars": []}]}
        )

        errors = loader._validate_sample(invalid_sample)
        amb_type_errors = [e for e in errors if "ambiguity_types" in e.field and e.severity == "warning"]
        assert len(amb_type_errors) > 0


class TestConstants:
    """测试常量定义"""

    def test_valid_domains(self):
        """测试有效domain列表"""
        assert "planning" in VALID_DOMAINS
        assert "qa" in VALID_DOMAINS
        assert "reasoning" in VALID_DOMAINS
        assert "creative" in VALID_DOMAINS
        assert "invalid" not in VALID_DOMAINS

    def test_valid_sources(self):
        """测试有效source列表"""
        assert "human" in VALID_SOURCES
        assert "curated" in VALID_SOURCES
        assert "synthetic-gemini" in VALID_SOURCES
        assert "r1-distill" in VALID_SOURCES
        assert "invalid" not in VALID_SOURCES


if __name__ == "__main__":
    pytest.main([__file__])
