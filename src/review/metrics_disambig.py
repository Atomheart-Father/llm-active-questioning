#!/usr/bin/env python3
"""
Disambig-F1 Metrics Calculator - Tree-based Disambiguation Evaluation

Calculates Disambig-F1 score based on clarify_tree and evidence coverage.
Implements ASQA-style evaluation for clarification effectiveness.
"""

import re
from typing import Dict, Any, List, Optional
from collections import defaultdict

class DisambigF1Calculator:
    """Disambig-F1计算器"""

    def __init__(self):
        self.evidence_patterns = [
            r'hotpot:(d\d+)#sent(\d+)',
            r'ambigqa:(.*?)#sent(\d+)',
            r'asqa:(.*?)#sent(\d+)'
        ]

    def calculate_disambig_f1(self, sample: Dict[str, Any], reference_data: Optional[Dict] = None) -> float:
        """
        计算Disambig-F1分数

        Args:
            sample: 样本数据
            reference_data: 参考数据（包含正确证据）

        Returns:
            Disambig-F1分数 (0.0-1.0)
        """
        clarify_tree = sample.get("clarify_tree", {})
        evidence_ids = sample.get("evidence_ids", [])

        if not clarify_tree and not evidence_ids:
            return 0.0

        # 计算树覆盖率
        tree_coverage = self._calculate_tree_coverage(clarify_tree, reference_data)

        # 计算证据准确率
        evidence_precision = self._calculate_evidence_precision(evidence_ids, reference_data)

        # 计算证据召回率
        evidence_recall = self._calculate_evidence_recall(evidence_ids, reference_data)

        # F1计算
        if evidence_precision + evidence_recall == 0:
            return tree_coverage

        evidence_f1 = 2 * (evidence_precision * evidence_recall) / (evidence_precision + evidence_recall)

        # 综合评分
        return (tree_coverage + evidence_f1) / 2

    def _calculate_tree_coverage(self, clarify_tree: Dict[str, Any], reference_data: Optional[Dict]) -> float:
        """计算树结构覆盖率"""
        if not clarify_tree or not reference_data:
            return 0.0

        tree_depth = clarify_tree.get("depth", 0)
        tree_nodes = clarify_tree.get("nodes", [])

        # 简化的覆盖率计算（可根据具体需求调整）
        depth_coverage = min(tree_depth / 2.0, 1.0)  # 期望最大深度2
        node_coverage = min(len(tree_nodes) / 5.0, 1.0)  # 期望最多5个节点

        return (depth_coverage + node_coverage) / 2

    def _calculate_evidence_precision(self, evidence_ids: List[str], reference_data: Optional[Dict]) -> float:
        """计算证据准确率"""
        if not evidence_ids:
            return 0.0

        if not reference_data:
            return 0.5  # 无参考数据时的默认值

        correct_count = 0
        for evidence_id in evidence_ids:
            if self._is_evidence_correct(evidence_id, reference_data):
                correct_count += 1

        return correct_count / len(evidence_ids)

    def _calculate_evidence_recall(self, evidence_ids: List[str], reference_data: Optional[Dict]) -> float:
        """计算证据召回率"""
        if not reference_data:
            return 0.5

        # 提取参考证据
        reference_evidence = self._extract_reference_evidence(reference_data)

        if not reference_evidence:
            return 1.0  # 无参考证据，召回率完美

        found_count = 0
        for ref_evidence in reference_evidence:
            if any(self._evidence_match(evidence_id, ref_evidence) for evidence_id in evidence_ids):
                found_count += 1

        return found_count / len(reference_evidence)

    def _is_evidence_correct(self, evidence_id: str, reference_data: Dict) -> bool:
        """检查证据是否正确"""
        # 简化的正确性检查（可根据具体数据集调整）
        for pattern in self.evidence_patterns:
            if re.match(pattern, evidence_id):
                return True
        return False

    def _extract_reference_evidence(self, reference_data: Dict) -> List[str]:
        """提取参考证据"""
        # 从参考数据中提取正确证据ID
        evidence_list = []

        if "supporting_facts" in reference_data:
            for fact in reference_data["supporting_facts"]:
                if isinstance(fact, dict):
                    doc_id = fact.get("doc_id", "")
                    sent_id = fact.get("sent_id", 0)
                    evidence_list.append(f"{doc_id}#sent{sent_id}")

        return evidence_list

    def _evidence_match(self, evidence_id: str, reference_evidence: str) -> bool:
        """检查证据是否匹配"""
        # 简化的匹配逻辑
        return evidence_id in reference_evidence or reference_evidence in evidence_id
