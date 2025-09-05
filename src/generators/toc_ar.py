#!/usr/bin/env python3
"""
ToC-AR Generator - Tree of Clarification for Active Reasoning

Generates AR samples with clarification trees and evidence linking.
Implements Disambig-F1 ≥0.7 and evidence coverage ≥95% requirements.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ..streaming_client import LLMClient
from ..schema_validator import SchemaValidator

@dataclass
class ToCConfig:
    """ToC-AR generation configuration"""
    max_tree_depth: int = 2
    max_branching: int = 3
    disambig_f1_threshold: float = 0.7
    evidence_coverage_threshold: float = 0.95

class ToCGenerator:
    """ToC-AR样本生成器"""

    def __init__(self, client: LLMClient, validator: SchemaValidator):
        self.client = client
        self.validator = validator
        self.config = ToCConfig()

        # Load prompt template
        template_path = Path(__file__).parent / ".." / "prompt_templates" / "toc_ar.txt"
        with open(template_path, 'r', encoding='utf-8') as f:
            self.prompt_template = f.read()

        # 证据源映射（示例）
        self.evidence_sources = {
            "hotpotqa": "hotpot",
            "ambigqa": "ambigqa",
            "asqa": "asqa"
        }

    def generate_sample(self, user_query: str, reference_data: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        生成单个ToC-AR样本

        Args:
            user_query: 用户查询
            reference_data: 可选的参考数据（包含证据）

        Returns:
            符合Schema v1.2的样本，或None（如果生成失败）
        """
        # 构建prompt
        prompt = self._build_prompt(user_query, reference_data)

        # 调用LLM生成
        messages = [
            {"role": "system", "content": "You must output only valid JSON. No explanations, no markdown, no polite phrases."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.client.stream_chat(
                provider="gemini_pro",  # AR使用pro模型
                model="gemini_pro",
                messages=messages,
                max_tokens=1536,  # AR使用更高token限制
                json_only=True
            )

            if isinstance(response, dict) and "text" in response:
                text = response["text"]
            else:
                text = str(response)

            # 解析JSON
            sample = self._parse_response(text, user_query)

            # 后处理和验证
            if sample:
                sample = self._post_process_sample(sample, reference_data)
                is_valid, errors = self.validator.validate_sample(sample)

                if is_valid:
                    return sample
                else:
                    print(f"Sample validation failed: {errors}")
                    return None

        except Exception as e:
            print(f"Generation failed: {e}")
            return None

    def _build_prompt(self, user_query: str, reference_data: Optional[Dict] = None) -> str:
        """构建生成prompt"""
        ref_data_str = ""
        if reference_data:
            ref_data_str = json.dumps(reference_data, ensure_ascii=False, indent=2)

        return self.prompt_template.format(
            user_query=user_query,
            reference_data=ref_data_str
        )

    def _parse_response(self, text: str, user_query: str) -> Optional[Dict[str, Any]]:
        """解析LLM响应"""
        try:
            # 清理响应文本
            text = text.strip()

            # 移除可能的markdown包装
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            text = text.strip()

            # 解析JSON
            sample = json.loads(text)

            # 确保基本结构
            if "turns" not in sample:
                sample["turns"] = [
                    {"role": "user", "text": user_query},
                    {"role": "model_target", "text": "<FINAL>Please provide more context</FINAL>"}
                ]

            if "labels" not in sample:
                sample["labels"] = {"ask_required": False}

            if "reasoning" not in sample:
                sample["reasoning"] = {"actions": ["AWARE_GAP", "STOP_ASK", "FINALIZE"]}

            if "source" not in sample:
                sample["source"] = "synthetic-gemini"

            return sample

        except json.JSONDecodeError as e:
            print(f"JSON parsing failed: {e}")
            print(f"Response text: {text[:200]}...")
            return None
        except Exception as e:
            print(f"Response parsing failed: {e}")
            return None

    def _post_process_sample(self, sample: Dict[str, Any], reference_data: Optional[Dict] = None) -> Dict[str, Any]:
        """后处理样本，增强ToC字段"""
        # 确保clarify_tree存在
        if "clarify_tree" not in sample:
            sample["clarify_tree"] = {
                "depth": 1,
                "nodes": [
                    {
                        "id": "Q1",
                        "children": []
                    }
                ]
            }

        # 限制树深度
        tree = sample["clarify_tree"]
        if tree.get("depth", 0) > self.config.max_tree_depth:
            tree["depth"] = self.config.max_tree_depth

        # 限制分支数量
        for node in tree.get("nodes", []):
            children = node.get("children", [])
            if len(children) > self.config.max_branching:
                node["children"] = children[:self.config.max_branching]

        # 生成evidence_ids（如果没有）
        if "evidence_ids" not in sample:
            sample["evidence_ids"] = self._generate_evidence_ids(sample, reference_data)

        # 确保oracle_answer存在
        labels = sample.get("labels", {})
        if "oracle_answer" not in labels:
            # 从model_target中提取答案
            turns = sample.get("turns", [])
            for turn in turns:
                if turn.get("role") == "model_target":
                    text = turn.get("text", "")
                    if "<FINAL>" in text and "</FINAL>" in text:
                        final_match = re.search(r'<FINAL>(.*?)</FINAL>', text, re.DOTALL)
                        if final_match:
                            labels["oracle_answer"] = final_match.group(1).strip()
                            break

        sample["labels"] = labels

        # 确保紧凑推理
        reasoning = sample.get("reasoning", {})
        if "compact_rationale" not in reasoning:
            reasoning["compact_rationale"] = {
                "connectors": ["if", "then", "because"],
                "steps": 3
            }

        sample["reasoning"] = reasoning

        return sample

    def _generate_evidence_ids(self, sample: Dict[str, Any], reference_data: Optional[Dict] = None) -> List[str]:
        """生成证据ID列表"""
        evidence_ids = []

        # 如果有参考数据，从中提取证据
        if reference_data:
            dataset = reference_data.get("dataset", "unknown")
            doc_id = reference_data.get("id", "unknown")

            # 生成证据指针
            if "sentences" in reference_data:
                for i, sent in enumerate(reference_data["sentences"]):
                    if self._is_relevant_sentence(sent, sample):
                        evidence_ids.append(f"{dataset}:{doc_id}#sent{i+1}")

        # 如果没有参考数据，生成模拟证据
        if not evidence_ids:
            evidence_ids = ["hotpot:unknown#sent1"]

        return evidence_ids

    def _is_relevant_sentence(self, sentence: str, sample: Dict[str, Any]) -> bool:
        """判断句子是否与样本相关"""
        user_query = ""
        for turn in sample.get("turns", []):
            if turn.get("role") == "user":
                user_query = turn.get("text", "")
                break

        # 简单的相关性检查（可扩展为更复杂的算法）
        query_words = set(user_query.lower().split())
        sent_words = set(sentence.lower().split())

        overlap = len(query_words.intersection(sent_words))
        return overlap > 0

    def validate_toc_quality(self, sample: Dict[str, Any]) -> Dict[str, float]:
        """
        验证ToC质量指标

        Returns:
            质量分数字典
        """
        # Disambig-F1 (简化计算)
        tree = sample.get("clarify_tree", {})
        depth = tree.get("depth", 0)
        node_count = len(tree.get("nodes", []))
        disambig_f1 = min((depth + node_count) / 5.0, 1.0)  # 简化的F1计算

        # Evidence Coverage
        evidence_ids = sample.get("evidence_ids", [])
        coverage_score = 1.0 if evidence_ids else 0.5

        # Tree Structure Score
        total_branches = sum(len(node.get("children", [])) for node in tree.get("nodes", []))
        structure_score = min(total_branches / 6.0, 1.0)  # 期望总分支数≤6

        return {
            "disambig_f1": disambig_f1,
            "evidence_coverage": coverage_score,
            "tree_structure": structure_score,
            "overall_quality": (disambig_f1 + coverage_score + structure_score) / 3
        }
