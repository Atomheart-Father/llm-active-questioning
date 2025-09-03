"""
奖励系统模块
实现多种奖励机制的组合计算
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from sklearn.metrics import f1_score
from rouge_score import rouge_scorer

# Optional import for GPT-4 evaluation (Sidecar)
try:
    from integrations.simulation.gpt4_simulator import GPT4UserSimulator
    GPT4_AVAILABLE = True
except ImportError:
    GPT4_AVAILABLE = False
    GPT4UserSimulator = None
from ..utils.config import get_config
from ..utils.logging import get_logger


class RewardCalculator:
    """奖励计算器"""
    
    def __init__(self, gpt4_simulator = None):
        """
        初始化奖励计算器
        
        Args:
            gpt4_simulator: GPT-4模拟器实例，用于偏好评估
        """
        self.config = get_config()
        self.logger = get_logger()
        self.gpt4_simulator = gpt4_simulator
        
        # 奖励权重
        self.reward_weights = self.config.get("training.reward_weights", {
            "correctness": 0.6,
            "gpt4_preference": 0.3,
            "safety_penalty": 0.1
        })
        
        # 安全关键词
        self.safety_keywords = self.config.get("reward.safety_keywords", [
            "harmful", "offensive", "illegal", "dangerous", "inappropriate"
        ])
        
        # ROUGE评分器
        self.rouge_scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
        
        self.logger.info("奖励计算器初始化完成")
    
    def extract_final_answer(self, text: str) -> str:
        """
        从回答中提取最终答案
        
        Args:
            text: 回答文本
            
        Returns:
            提取的最终答案
        """
        # 尝试提取数学答案
        math_patterns = [
            r'最终答案是[：:]?\s*([^。\n]+)',
            r'答案是[：:]?\s*([^。\n]+)',
            r'因此[，,]?\s*([^。\n]+)',
            r'####\s*([^\n]+)',
            r'答案[：:]?\s*([^。\n]+)'
        ]
        
        for pattern in math_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        # 如果没有明确的答案标记，返回最后一句话
        sentences = text.split('。')
        if sentences:
            return sentences[-1].strip()
        
        return text.strip()
    
    def calculate_exact_match(self, prediction: str, reference: str) -> float:
        """
        计算精确匹配分数
        
        Args:
            prediction: 预测答案
            reference: 参考答案
            
        Returns:
            精确匹配分数 (0 or 1)
        """
        pred_clean = self.extract_final_answer(prediction).lower().strip()
        ref_clean = reference.lower().strip()
        
        return 1.0 if pred_clean == ref_clean else 0.0
    
    def calculate_f1_score(self, prediction: str, reference: str) -> float:
        """
        计算F1分数
        
        Args:
            prediction: 预测答案
            reference: 参考答案
            
        Returns:
            F1分数
        """
        pred_tokens = set(prediction.lower().split())
        ref_tokens = set(reference.lower().split())
        
        if not ref_tokens:
            return 1.0 if not pred_tokens else 0.0
        
        if not pred_tokens:
            return 0.0
        
        # 计算精确率和召回率
        intersection = pred_tokens.intersection(ref_tokens)
        precision = len(intersection) / len(pred_tokens)
        recall = len(intersection) / len(ref_tokens)
        
        if precision + recall == 0:
            return 0.0
        
        f1 = 2 * precision * recall / (precision + recall)
        return f1
    
    def calculate_rouge_score(self, prediction: str, reference: str) -> float:
        """
        计算ROUGE分数
        
        Args:
            prediction: 预测答案
            reference: 参考答案
            
        Returns:
            ROUGE-L F1分数
        """
        try:
            scores = self.rouge_scorer.score(reference, prediction)
            return scores['rougeL'].fmeasure
        except Exception as e:
            self.logger.warning(f"计算ROUGE分数失败: {e}")
            return 0.0
    
    def calculate_correctness_reward(self, sample: Dict[str, Any], prediction: str) -> float:
        """
        计算正确性奖励
        
        Args:
            sample: 样本数据
            prediction: 模型预测
            
        Returns:
            正确性奖励分数 (0-1)
        """
        dataset_type = sample.get('dataset', 'unknown')
        
        if dataset_type == 'gsm8k':
            return self._calculate_gsm8k_reward(sample, prediction)
        elif dataset_type == 'hotpotqa':
            return self._calculate_hotpotqa_reward(sample, prediction)
        elif dataset_type == 'ambigqa':
            return self._calculate_ambigqa_reward(sample, prediction)
        else:
            return self._calculate_generic_reward(sample, prediction)
    
    def _calculate_gsm8k_reward(self, sample: Dict[str, Any], prediction: str) -> float:
        """计算GSM8K数学问题的奖励"""
        reference_answer = sample.get('answer', '')
        
        # 提取数值答案
        pred_answer = self.extract_final_answer(prediction)
        
        # 尝试提取参考答案中的数值
        ref_match = re.search(r'####\s*([^\n]+)', reference_answer)
        if ref_match:
            ref_answer = ref_match.group(1).strip()
        else:
            ref_answer = reference_answer
        
        # 精确匹配
        exact_match = self.calculate_exact_match(pred_answer, ref_answer)
        
        if exact_match > 0:
            return 1.0
        
        # 尝试数值比较
        try:
            pred_num = float(re.sub(r'[^\d.-]', '', pred_answer))
            ref_num = float(re.sub(r'[^\d.-]', '', ref_answer))
            
            if abs(pred_num - ref_num) < 0.01:  # 允许小误差
                return 1.0
        except:
            pass
        
        # 使用F1分数作为后备
        return self.calculate_f1_score(prediction, reference_answer) * 0.5
    
    def _calculate_hotpotqa_reward(self, sample: Dict[str, Any], prediction: str) -> float:
        """计算HotpotQA的奖励"""
        reference_answer = sample.get('answer', '')
        
        # F1分数
        f1 = self.calculate_f1_score(prediction, reference_answer)
        
        # ROUGE分数
        rouge = self.calculate_rouge_score(prediction, reference_answer)
        
        # 综合分数
        return (f1 + rouge) / 2
    
    def _calculate_ambigqa_reward(self, sample: Dict[str, Any], prediction: str) -> float:
        """计算AmbigQA的奖励"""
        answers = sample.get('answers', [])
        
        if not answers:
            return 0.0
        
        # 检查是否识别了歧义
        ambiguity_indicators = ['歧义', '不同理解', '多种答案', '可能是']
        has_ambiguity_recognition = any(indicator in prediction for indicator in ambiguity_indicators)
        
        # 计算与各个参考答案的最高匹配度
        max_score = 0.0
        for answer in answers:
            f1 = self.calculate_f1_score(prediction, str(answer))
            max_score = max(max_score, f1)
        
        # 如果识别了歧义，额外奖励
        if has_ambiguity_recognition and len(answers) > 1:
            max_score = min(1.0, max_score + 0.3)
        
        return max_score
    
    def _calculate_generic_reward(self, sample: Dict[str, Any], prediction: str) -> float:
        """计算通用任务的奖励"""
        reference = sample.get('answer', sample.get('assistant', ''))
        
        if not reference:
            return 0.5  # 没有参考答案时给中等分数
        
        # 使用F1和ROUGE的组合
        f1 = self.calculate_f1_score(prediction, reference)
        rouge = self.calculate_rouge_score(prediction, reference)
        
        return (f1 + rouge) / 2
    
    def calculate_safety_penalty(self, prediction: str) -> float:
        """
        计算安全惩罚
        
        Args:
            prediction: 模型预测
            
        Returns:
            安全惩罚分数 (0-1, 越高越安全)
        """
        prediction_lower = prediction.lower()
        
        # 检查有害关键词
        harmful_count = 0
        for keyword in self.safety_keywords:
            if keyword in prediction_lower:
                harmful_count += 1
        
        # 检查其他不当内容
        inappropriate_patterns = [
            r'我不知道',
            r'无法回答',
            r'抱歉.*无法',
            r'这超出了我的能力'
        ]
        
        appropriate_refusal = any(re.search(pattern, prediction) for pattern in inappropriate_patterns)
        
        if harmful_count > 0:
            return max(0.0, 1.0 - harmful_count * 0.3)
        elif appropriate_refusal:
            return 0.8  # 适当的拒绝回答
        else:
            return 1.0  # 安全内容
    
    def calculate_gpt4_preference_reward(self, question: str, prediction: str) -> float:
        """
        使用GPT-4计算偏好奖励
        
        Args:
            question: 用户问题
            prediction: 模型预测
            
        Returns:
            GPT-4偏好分数 (0-1)
        """
        if self.gpt4_simulator is None or not GPT4_AVAILABLE:
            self.logger.warning("GPT-4模拟器不可用，跳过偏好评估")
            return 0.5
        
        try:
            evaluation = self.gpt4_simulator.evaluate_response(question, prediction)
            overall_score = evaluation.get('overall_score', 5.0)
            
            # 将1-10分数转换为0-1分数
            normalized_score = (overall_score - 1) / 9
            return max(0.0, min(1.0, normalized_score))
            
        except Exception as e:
            self.logger.error(f"GPT-4偏好评估失败: {e}")
            return 0.5
    
    def calculate_total_reward(self, sample: Dict[str, Any], prediction: str, question: str = None) -> Dict[str, float]:
        """
        计算总奖励
        
        Args:
            sample: 样本数据
            prediction: 模型预测
            question: 用户问题（用于GPT-4评估）
            
        Returns:
            奖励分解和总分
        """
        # 计算各项奖励
        correctness = self.calculate_correctness_reward(sample, prediction)
        safety = self.calculate_safety_penalty(prediction)
        
        # GPT-4偏好评估（可选）
        if question and self.gpt4_simulator and GPT4_AVAILABLE and self.config.get("reward.gpt4_evaluation.enabled", True):
            gpt4_preference = self.calculate_gpt4_preference_reward(question, prediction)
        else:
            gpt4_preference = 0.5  # 默认中等分数
        
        # 计算加权总分
        total_reward = (
            correctness * self.reward_weights["correctness"] +
            gpt4_preference * self.reward_weights["gpt4_preference"] +
            safety * self.reward_weights["safety_penalty"]
        )
        
        reward_breakdown = {
            'correctness': correctness,
            'gpt4_preference': gpt4_preference,
            'safety': safety,
            'total': total_reward
        }
        
        self.logger.debug(f"奖励计算: {reward_breakdown}")
        
        return reward_breakdown
    
    def batch_calculate_rewards(self, samples: List[Dict[str, Any]], predictions: List[str], questions: List[str] = None) -> List[Dict[str, float]]:
        """
        批量计算奖励
        
        Args:
            samples: 样本列表
            predictions: 预测列表
            questions: 问题列表
            
        Returns:
            奖励列表
        """
        self.logger.info(f"开始批量计算{len(samples)}个样本的奖励...")
        
        rewards = []
        for i, (sample, prediction) in enumerate(zip(samples, predictions)):
            question = questions[i] if questions else None
            reward = self.calculate_total_reward(sample, prediction, question)
            rewards.append(reward)
            
            if (i + 1) % 100 == 0:
                self.logger.info(f"已处理{i + 1}/{len(samples)}个样本")
        
        # 统计信息
        avg_total = np.mean([r['total'] for r in rewards])
        avg_correctness = np.mean([r['correctness'] for r in rewards])
        avg_safety = np.mean([r['safety'] for r in rewards])
        
        self.logger.info(f"批量奖励计算完成 - 平均总分: {avg_total:.3f}, 平均正确性: {avg_correctness:.3f}, 平均安全性: {avg_safety:.3f}")
        
        return rewards
