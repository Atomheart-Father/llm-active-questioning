#!/usr/bin/env python3
"""
多维度数据质量评分工具
基于GPT-5反馈优化的质量审核标准
"""

import json
import re
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path

class QuestionType(Enum):
    """问题类型枚举"""
    MATH_REASONING = "math_reasoning"
    MULTI_HOP = "multi_hop"
    AMBIGUITY_CLARIFICATION = "ambiguity_clarification"

class QualityGrade(Enum):
    """质量等级枚举"""
    EXCELLENT = "A"
    GOOD = "B"
    NEEDS_IMPROVEMENT = "C"

@dataclass
class QualityMetrics:
    """质量指标数据类"""
    logic_rigor: float = 0.0        # 逻辑严谨性
    calc_accuracy: float = 0.0      # 计算准确性
    expression_clarity: float = 0.0 # 表达清晰度
    completeness: float = 0.0       # 步骤完整性
    clarification: float = 0.0      # 澄清合理性
    naturalness: float = 0.0        # 对话自然度
    educational: float = 0.0        # 教育价值

class QualityScorer:
    """多维度质量评分器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 基础权重配置
        self.base_weights = {
            "logic_rigor": 0.20,
            "calc_accuracy": 0.20,
            "expression_clarity": 0.15,
            "completeness": 0.15,
            "clarification": 0.10,
            "naturalness": 0.10,
            "educational": 0.10
        }
        
        # 不同问题类型的权重调整
        self.type_weight_adjustments = {
            QuestionType.MATH_REASONING: {
                "calc_accuracy": 0.25,
                "expression_clarity": 0.10,
                "logic_rigor": 0.20,
                "completeness": 0.20,
                "clarification": 0.10,
                "naturalness": 0.08,
                "educational": 0.07
            },
            QuestionType.MULTI_HOP: {
                "logic_rigor": 0.25,
                "completeness": 0.20,
                "calc_accuracy": 0.10,
                "expression_clarity": 0.15,
                "clarification": 0.15,
                "naturalness": 0.08,
                "educational": 0.07
            },
            QuestionType.AMBIGUITY_CLARIFICATION: {
                "clarification": 0.30,
                "naturalness": 0.20,
                "logic_rigor": 0.15,
                "expression_clarity": 0.15,
                "completeness": 0.10,
                "calc_accuracy": 0.05,
                "educational": 0.05
            }
        }
        
        # 核心指标硬性要求
        self.core_requirements = {
            QuestionType.MATH_REASONING: {
                "logic_rigor": 70,
                "calc_accuracy": 75,
                "expression_clarity": 65
            },
            QuestionType.MULTI_HOP: {
                "logic_rigor": 75,
                "completeness": 70,
                "clarification": 65
            },
            QuestionType.AMBIGUITY_CLARIFICATION: {
                "clarification": 75,
                "naturalness": 70,
                "logic_rigor": 65
            }
        }
    
    def get_weights(self, question_type: QuestionType) -> Dict[str, float]:
        """获取指定问题类型的权重配置"""
        if question_type in self.type_weight_adjustments:
            return self.type_weight_adjustments[question_type]
        return self.base_weights
    
    def check_core_requirements(self, metrics: QualityMetrics, question_type: QuestionType) -> bool:
        """检查核心指标是否满足硬性要求"""
        requirements = self.core_requirements.get(question_type, {})
        
        for metric_name, threshold in requirements.items():
            metric_value = getattr(metrics, metric_name)
            if metric_value < threshold:
                self.logger.warning(f"核心指标不达标: {metric_name}={metric_value} < {threshold}")
                return False
        
        return True
    
    def calculate_total_score(self, metrics: QualityMetrics, question_type: QuestionType) -> float:
        """计算加权总分"""
        weights = self.get_weights(question_type)
        total_score = 0.0
        
        for metric_name, weight in weights.items():
            metric_value = getattr(metrics, metric_name)
            total_score += metric_value * weight
        
        return total_score
    
    def determine_grade(self, total_score: float, metrics: QualityMetrics, 
                       question_type: QuestionType) -> QualityGrade:
        """确定质量等级"""
        core_ok = self.check_core_requirements(metrics, question_type)
        
        if total_score >= 85 and core_ok:
            return QualityGrade.EXCELLENT
        elif total_score >= 70:
            return QualityGrade.GOOD
        else:
            return QualityGrade.NEEDS_IMPROVEMENT
    
    def score_dialogue(self, dialogue_data: Dict[str, Any], question_type: QuestionType) -> Dict[str, Any]:
        """评分单个对话数据"""
        # 提取对话内容
        original_question = dialogue_data.get("original_question", "")
        turns = dialogue_data.get("turns", [])
        
        # 自动评估各维度指标
        metrics = self._evaluate_metrics(dialogue_data, question_type)
        
        # 计算总分
        total_score = self.calculate_total_score(metrics, question_type)
        
        # 确定等级
        grade = self.determine_grade(total_score, metrics, question_type)
        
        # 生成详细报告
        detailed_analysis = self._generate_detailed_analysis(dialogue_data, metrics, question_type)
        
        return {
            "dialogue_id": dialogue_data.get("id", "unknown"),
            "question_type": question_type.value,
            "total_score": round(total_score, 2),
            "grade": grade.value,
            "metrics": {
                "logic_rigor": metrics.logic_rigor,
                "calc_accuracy": metrics.calc_accuracy,
                "expression_clarity": metrics.expression_clarity,
                "completeness": metrics.completeness,
                "clarification": metrics.clarification,
                "naturalness": metrics.naturalness,
                "educational": metrics.educational
            },
            "core_requirements_met": self.check_core_requirements(metrics, question_type),
            "detailed_analysis": detailed_analysis,
            "weights_used": self.get_weights(question_type)
        }
    
    def _evaluate_metrics(self, dialogue_data: Dict[str, Any], question_type: QuestionType) -> QualityMetrics:
        """评估各维度指标"""
        metrics = QualityMetrics()
        
        # 逻辑严谨性评估
        metrics.logic_rigor = self._evaluate_logic_rigor(dialogue_data, question_type)
        
        # 计算准确性评估（主要针对数学推理）
        metrics.calc_accuracy = self._evaluate_calculation_accuracy(dialogue_data, question_type)
        
        # 表达清晰度评估
        metrics.expression_clarity = self._evaluate_expression_clarity(dialogue_data)
        
        # 步骤完整性评估
        metrics.completeness = self._evaluate_completeness(dialogue_data, question_type)
        
        # 澄清合理性评估
        metrics.clarification = self._evaluate_clarification_quality(dialogue_data, question_type)
        
        # 对话自然度评估
        metrics.naturalness = self._evaluate_naturalness(dialogue_data)
        
        # 教育价值评估
        metrics.educational = self._evaluate_educational_value(dialogue_data, question_type)
        
        return metrics
    
    def _evaluate_logic_rigor(self, dialogue_data: Dict[str, Any], question_type: QuestionType) -> float:
        """评估逻辑严谨性"""
        turns = dialogue_data.get("turns", [])
        score = 85.0  # 基础分
        
        # 检查推理步骤的逻辑性
        for turn in turns:
            if turn.get("role") == "assistant":
                content = turn.get("content", "")
                
                # 检查逻辑连接词
                logic_indicators = ["因为", "所以", "由于", "因此", "首先", "然后", "接下来", "最后"]
                logic_count = sum(1 for indicator in logic_indicators if indicator in content)
                
                # 检查是否有明显的逻辑跳跃
                if len(content) > 100 and logic_count == 0:
                    score -= 10  # 缺乏逻辑连接
                
                # 检查是否有自相矛盾
                if "但是" in content and "然而" in content:
                    contradictions = content.count("但是") + content.count("然而")
                    if contradictions > 2:
                        score -= 15  # 过多矛盾表述
        
        # 针对不同问题类型的特殊检查
        if question_type == QuestionType.MULTI_HOP:
            # 检查多跳推理的因果关系
            if not self._check_causal_relationships(dialogue_data):
                score -= 20
        
        return max(0, min(100, score))
    
    def _evaluate_calculation_accuracy(self, dialogue_data: Dict[str, Any], question_type: QuestionType) -> float:
        """评估计算准确性"""
        if question_type != QuestionType.MATH_REASONING:
            return 80.0  # 非数学问题给基础分
        
        turns = dialogue_data.get("turns", [])
        score = 90.0
        
        for turn in turns:
            if turn.get("role") == "assistant":
                content = turn.get("content", "")
                
                # 检查是否包含数学计算
                math_patterns = [
                    r'\d+\s*[+\-*/]\s*\d+',  # 基本运算
                    r'=\s*\d+',              # 等号和结果
                    r'\d+\s*[×÷]\s*\d+'      # 中文运算符
                ]
                
                has_calculation = any(re.search(pattern, content) for pattern in math_patterns)
                
                if has_calculation:
                    # 简单验证计算结果
                    if not self._verify_calculations(content):
                        score -= 30  # 计算错误
                
                # 检查单位是否一致
                units = re.findall(r'\d+\s*([a-zA-Z\u4e00-\u9fff]+)', content)
                if len(set(units)) > 1:  # 可能存在单位不一致
                    if not self._check_unit_consistency(content):
                        score -= 15
        
        return max(0, min(100, score))
    
    def _evaluate_expression_clarity(self, dialogue_data: Dict[str, Any]) -> float:
        """评估表达清晰度"""
        turns = dialogue_data.get("turns", [])
        score = 80.0
        
        total_content = ""
        for turn in turns:
            if turn.get("role") == "assistant":
                total_content += turn.get("content", "")
        
        if not total_content:
            return 0.0
        
        # 检查句子长度（过长可能不清晰）
        sentences = re.split(r'[。！？]', total_content)
        avg_sentence_length = sum(len(s) for s in sentences) / max(len(sentences), 1)
        
        if avg_sentence_length > 50:
            score -= 10  # 句子过长
        elif avg_sentence_length < 10:
            score -= 5   # 句子过短可能不完整
        
        # 检查标点符号使用
        punctuation_count = len(re.findall(r'[，。！？；：]', total_content))
        content_length = len(total_content)
        
        if content_length > 0:
            punctuation_ratio = punctuation_count / content_length
            if punctuation_ratio < 0.02:  # 标点过少
                score -= 15
        
        # 检查是否有明显的语法错误
        grammar_issues = [
            r'的的',      # 重复的字
            r'了了',      # 重复的字
            r'是是',      # 重复的字
        ]
        
        for pattern in grammar_issues:
            if re.search(pattern, total_content):
                score -= 5
        
        return max(0, min(100, score))
    
    def _evaluate_completeness(self, dialogue_data: Dict[str, Any], question_type: QuestionType) -> float:
        """评估步骤完整性"""
        turns = dialogue_data.get("turns", [])
        score = 80.0
        
        # 检查对话轮次是否合理
        if len(turns) < 2:
            score -= 30  # 对话过短
        elif len(turns) > 8:
            score -= 10  # 对话过长可能冗余
        
        # 检查是否有完整的问答流程
        has_user_question = any(turn.get("role") == "user" for turn in turns)
        has_assistant_answer = any(turn.get("role") == "assistant" for turn in turns)
        
        if not has_user_question:
            score -= 20
        if not has_assistant_answer:
            score -= 20
        
        # 针对不同类型的特殊检查
        if question_type == QuestionType.MULTI_HOP:
            # 检查是否包含多步推理
            assistant_turns = [turn for turn in turns if turn.get("role") == "assistant"]
            if len(assistant_turns) > 0:
                content = " ".join(turn.get("content", "") for turn in assistant_turns)
                step_indicators = ["第一", "第二", "首先", "然后", "接下来", "最后", "步骤"]
                step_count = sum(1 for indicator in step_indicators if indicator in content)
                
                if step_count < 2:
                    score -= 20  # 缺乏明显的步骤划分
        
        return max(0, min(100, score))
    
    def _evaluate_clarification_quality(self, dialogue_data: Dict[str, Any], question_type: QuestionType) -> float:
        """评估澄清合理性"""
        turns = dialogue_data.get("turns", [])
        score = 75.0
        
        if question_type != QuestionType.AMBIGUITY_CLARIFICATION:
            # 非澄清类问题给基础分
            return score
        
        # 查找澄清问题
        clarification_turns = []
        for turn in turns:
            if turn.get("role") == "assistant" and ("？" in turn.get("content", "") or "?" in turn.get("content", "")):
                clarification_turns.append(turn)
        
        if not clarification_turns:
            return 30.0  # 澄清类问题但没有澄清
        
        # 评估澄清问题质量
        for turn in clarification_turns:
            content = turn.get("content", "")
            
            # 检查礼貌用语
            polite_indicators = ["请问", "可以", "能否", "抱歉", "不好意思"]
            has_politeness = any(indicator in content for indicator in polite_indicators)
            
            if has_politeness:
                score += 10
            
            # 检查是否针对具体歧义点
            specific_indicators = ["哪", "什么", "具体", "明确", "详细"]
            has_specificity = any(indicator in content for indicator in specific_indicators)
            
            if has_specificity:
                score += 10
            else:
                score -= 15  # 澄清问题不够具体
        
        # 检查澄清次数（避免重复澄清）
        if len(clarification_turns) > 2:
            score -= 20  # 澄清过多
        
        return max(0, min(100, score))
    
    def _evaluate_naturalness(self, dialogue_data: Dict[str, Any]) -> float:
        """评估对话自然度"""
        turns = dialogue_data.get("turns", [])
        score = 80.0
        
        for turn in turns:
            content = turn.get("content", "")
            role = turn.get("role", "")
            
            # 检查语言流畅度
            if role == "assistant":
                # 检查是否过于正式或生硬
                formal_indicators = ["根据上述分析", "综上所述", "经过计算", "通过推理"]
                formal_count = sum(1 for indicator in formal_indicators if indicator in content)
                
                if formal_count > 2:
                    score -= 10  # 过于正式
                
                # 检查是否有自然的对话词汇
                natural_indicators = ["好的", "明白", "让我", "我来", "我们", "你"]
                has_natural = any(indicator in content for indicator in natural_indicators)
                
                if has_natural:
                    score += 5
            
            elif role == "user":
                # 检查用户语言是否自然
                if len(content) > 100:
                    score -= 5  # 用户回答过长可能不自然
        
        return max(0, min(100, score))
    
    def _evaluate_educational_value(self, dialogue_data: Dict[str, Any], question_type: QuestionType) -> float:
        """评估教育价值"""
        turns = dialogue_data.get("turns", [])
        score = 75.0
        
        total_content = ""
        for turn in turns:
            if turn.get("role") == "assistant":
                total_content += turn.get("content", "")
        
        if not total_content:
            return 0.0
        
        # 检查是否包含解释性内容
        explanation_indicators = ["因为", "由于", "原理", "规律", "方法", "技巧", "步骤"]
        explanation_count = sum(1 for indicator in explanation_indicators if indicator in total_content)
        
        if explanation_count >= 3:
            score += 15  # 解释充分
        elif explanation_count == 0:
            score -= 20  # 缺乏解释
        
        # 检查是否有举例
        example_indicators = ["例如", "比如", "举例", "例子"]
        has_examples = any(indicator in total_content for indicator in example_indicators)
        
        if has_examples:
            score += 10
        
        # 检查思路的可复制性
        reproducible_indicators = ["步骤", "方法", "过程", "流程"]
        has_method = any(indicator in total_content for indicator in reproducible_indicators)
        
        if has_method:
            score += 10
        
        return max(0, min(100, score))
    
    def _check_causal_relationships(self, dialogue_data: Dict[str, Any]) -> bool:
        """检查因果关系的正确性"""
        turns = dialogue_data.get("turns", [])
        
        for turn in turns:
            if turn.get("role") == "assistant":
                content = turn.get("content", "")
                
                # 检查时间逻辑
                time_patterns = [r'(\d{4})年', r'(\d+)世纪']
                years = []
                
                for pattern in time_patterns:
                    matches = re.findall(pattern, content)
                    years.extend([int(match) for match in matches])
                
                if len(years) >= 2:
                    # 检查时间顺序是否合理
                    for i in range(len(years) - 1):
                        if years[i] > years[i + 1]:
                            # 可能存在时间逻辑错误
                            return False
        
        return True
    
    def _verify_calculations(self, content: str) -> bool:
        """验证计算结果"""
        # 简单的计算验证
        calc_patterns = [
            r'(\d+)\s*\+\s*(\d+)\s*=\s*(\d+)',
            r'(\d+)\s*-\s*(\d+)\s*=\s*(\d+)',
            r'(\d+)\s*\*\s*(\d+)\s*=\s*(\d+)',
            r'(\d+)\s*/\s*(\d+)\s*=\s*(\d+)',
            r'(\d+)\s*×\s*(\d+)\s*=\s*(\d+)'
        ]
        
        for pattern in calc_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                a, b, result = map(int, match)
                
                if '+' in pattern or '加' in pattern:
                    if a + b != result:
                        return False
                elif '-' in pattern or '减' in pattern:
                    if a - b != result:
                        return False
                elif '*' in pattern or '×' in pattern or '乘' in pattern:
                    if a * b != result:
                        return False
                elif '/' in pattern or '÷' in pattern or '除' in pattern:
                    if b != 0 and a / b != result:
                        return False
        
        return True
    
    def _check_unit_consistency(self, content: str) -> bool:
        """检查单位一致性"""
        # 简化的单位检查
        common_units = {
            '长度': ['米', 'm', '厘米', 'cm', '公里', 'km'],
            '重量': ['克', 'g', '公斤', 'kg', '斤'],
            '时间': ['秒', 's', '分钟', 'min', '小时', 'h']
        }
        
        # 这里可以添加更复杂的单位检查逻辑
        return True  # 简化处理，返回True
    
    def _generate_detailed_analysis(self, dialogue_data: Dict[str, Any], 
                                  metrics: QualityMetrics, question_type: QuestionType) -> Dict[str, Any]:
        """生成详细分析报告"""
        analysis = {
            "question_type_analysis": f"该问题属于{question_type.value}类型",
            "strengths": [],
            "weaknesses": [],
            "suggestions": []
        }
        
        # 分析优势
        if metrics.logic_rigor >= 80:
            analysis["strengths"].append("逻辑推理严谨清晰")
        if metrics.expression_clarity >= 80:
            analysis["strengths"].append("表达清晰易懂")
        if metrics.naturalness >= 80:
            analysis["strengths"].append("对话自然流畅")
        
        # 分析劣势
        if metrics.logic_rigor < 70:
            analysis["weaknesses"].append("逻辑推理存在漏洞或跳跃")
            analysis["suggestions"].append("加强推理步骤的逻辑连接，确保每步都有明确依据")
        
        if metrics.calc_accuracy < 70 and question_type == QuestionType.MATH_REASONING:
            analysis["weaknesses"].append("计算准确性有待提高")
            analysis["suggestions"].append("仔细检查计算过程，确保数值和单位正确")
        
        if metrics.clarification < 70 and question_type == QuestionType.AMBIGUITY_CLARIFICATION:
            analysis["weaknesses"].append("澄清策略需要改进")
            analysis["suggestions"].append("澄清问题应更加精准，使用礼貌自然的语言")
        
        return analysis
    
    def batch_score_dialogues(self, dialogues: List[Dict[str, Any]], 
                            question_types: List[QuestionType]) -> Dict[str, Any]:
        """批量评分对话数据"""
        if len(dialogues) != len(question_types):
            raise ValueError("对话数量与问题类型数量不匹配")
        
        results = []
        stats = {
            "total_count": len(dialogues),
            "grade_distribution": {"A": 0, "B": 0, "C": 0},
            "avg_scores_by_type": {},
            "avg_metrics": {}
        }
        
        # 逐一评分
        for dialogue, question_type in zip(dialogues, question_types):
            score_result = self.score_dialogue(dialogue, question_type)
            results.append(score_result)
            
            # 统计等级分布
            grade = score_result["grade"]
            stats["grade_distribution"][grade] += 1
        
        # 计算平均分数
        type_scores = {}
        for result in results:
            q_type = result["question_type"]
            if q_type not in type_scores:
                type_scores[q_type] = []
            type_scores[q_type].append(result["total_score"])
        
        for q_type, scores in type_scores.items():
            stats["avg_scores_by_type"][q_type] = sum(scores) / len(scores)
        
        # 计算平均指标
        all_metrics = [result["metrics"] for result in results]
        if all_metrics:
            for metric_name in all_metrics[0].keys():
                values = [metrics[metric_name] for metrics in all_metrics]
                stats["avg_metrics"][metric_name] = sum(values) / len(values)
        
        return {
            "results": results,
            "statistics": stats,
            "timestamp": self._get_timestamp()
        }
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def save_scoring_results(self, results: Dict[str, Any], output_file: str):
        """保存评分结果"""
        output_path = Path(output_file)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"评分结果已保存到: {output_path}")

def main():
    """测试质量评分工具"""
    # 配置日志
    logging.basicConfig(level=logging.INFO)
    
    # 创建评分器
    scorer = QualityScorer()
    
    # 测试数据
    test_dialogue = {
        "id": "test_001",
        "original_question": "一个矩形的长是10米，宽是5米，请问面积是多少？",
        "turns": [
            {"role": "user", "content": "一个矩形的长是10米，宽是5米，请问面积是多少？"},
            {"role": "assistant", "content": "要计算矩形的面积，我们使用公式：面积 = 长 × 宽。根据题目，长 = 10米，宽 = 5米，所以面积 = 10 × 5 = 50平方米。"}
        ]
    }
    
    # 评分
    result = scorer.score_dialogue(test_dialogue, QuestionType.MATH_REASONING)
    
    print("评分结果:")
    print(f"总分: {result['total_score']}")
    print(f"等级: {result['grade']}")
    print(f"核心要求满足: {result['core_requirements_met']}")
    print("\n各维度得分:")
    for metric, score in result["metrics"].items():
        print(f"  {metric}: {score}")

if __name__ == "__main__":
    main()
