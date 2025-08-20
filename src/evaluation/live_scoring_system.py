#!/usr/bin/env python3
"""
Live Scoring System - 真实评分系统
基于GPT-5指导实现的live_mode真实Gemini评分
"""

import os
import json
import time
import asyncio
import statistics
from typing import Dict, List, Any, Tuple, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 设置环境变量开关
REWARD_LIVE_MODE = os.getenv("REWARD_LIVE_MODE", "false").lower() == "true"

@dataclass
class ScoringConfig:
    """评分配置"""
    model_name: str = "gemini-2.5-pro"
    temperature: float = 0.0
    top_p: float = 0.0
    k_evaluations: int = 3
    variance_threshold: float = 0.08
    max_retries: int = 3
    timeout_seconds: int = 30

class LiveGeminiEvaluator:
    """真实Gemini评分器
    
    特性:
    - 支持K=3多评估求median
    - 方差检测和稳定性标记
    - 指数退避重试机制
    - 并发限制和rate limiting
    """
    
    def __init__(self, config: ScoringConfig = None):
        self.config = config or ScoringConfig()
        
        # API配置检查
        self.api_key = os.getenv("GEMINI_API_KEY")
        if REWARD_LIVE_MODE and not self.api_key:
            logger.warning("REWARD_LIVE_MODE=true但未设置GEMINI_API_KEY，将使用模拟模式")
        
        # 并发控制
        self.semaphore = asyncio.Semaphore(5)  # 最多5个并发请求
        self.request_times = []  # 用于rate limiting
        
        # 评分提示模板
        self.scoring_prompt = """
请对以下对话进行多维度质量评估，返回JSON格式结果。

对话内容:
{dialogue_text}

评估维度（0-1分）：
1. logic_rigor: 逻辑严谨性 - 推理是否连贯、无矛盾、逻辑链完整
2. question_quality: 提问质量 - 澄清问题是否精准、必要、有针对性
3. reasoning_completeness: 推理完整性 - 步骤是否完整、清晰、易懂
4. natural_interaction: 交互自然度 - 对话是否流畅、礼貌、人性化

评分标准：
- 0.9-1.0: 优秀，该维度表现杰出
- 0.7-0.8: 良好，该维度表现不错
- 0.5-0.6: 一般，该维度有改进空间  
- 0.3-0.4: 较差，该维度存在明显问题
- 0.0-0.2: 极差，该维度表现很不理想

请返回格式：
{{
    "logic_rigor": 0.85,
    "question_quality": 0.78,
    "reasoning_completeness": 0.82,
    "natural_interaction": 0.76,
    "explanation": "简要说明各维度评分理由（50字以内）"
}}

重要：只返回JSON，不要其他文字。
"""
    
    async def evaluate_dialogue_live(self, dialogue: Dict) -> Tuple[Dict[str, float], float, Dict[str, Any]]:
        """实时评估对话质量"""
        if not REWARD_LIVE_MODE or not self.api_key:
            return await self._simulate_evaluation(dialogue)
        
        dialogue_text = self._extract_dialogue_text(dialogue)
        
        # 执行K次评估
        evaluations = []
        metadata = {
            "api_calls": 0,
            "total_latency_ms": 0,
            "retries": 0,
            "errors": []
        }
        
        for i in range(self.config.k_evaluations):
            try:
                async with self.semaphore:
                    scores, latency_ms, retry_count = await self._single_evaluation(dialogue_text)
                    evaluations.append(scores)
                    metadata["api_calls"] += 1
                    metadata["total_latency_ms"] += latency_ms
                    metadata["retries"] += retry_count
                    
            except Exception as e:
                logger.error(f"评估失败 (轮次 {i+1}): {e}")
                metadata["errors"].append(str(e))
                # 使用备用评分
                fallback_scores = await self._get_fallback_scores(dialogue_text)
                evaluations.append(fallback_scores)
        
        if not evaluations:
            # 所有评估都失败，返回默认值
            return self._get_default_scores(), 0.0, metadata
        
        # 计算median和方差
        median_scores, variance = self._aggregate_evaluations(evaluations)
        
        metadata["variance"] = variance
        metadata["stability"] = "stable" if variance <= self.config.variance_threshold else "unstable"
        
        return median_scores, variance, metadata
    
    async def _single_evaluation(self, dialogue_text: str) -> Tuple[Dict[str, float], int, int]:
        """单次API评估调用"""
        start_time = time.time()
        retry_count = 0
        
        for attempt in range(self.config.max_retries):
            try:
                # Rate limiting
                await self._rate_limit()
                
                # 调用Gemini API (这里需要实际的API实现)
                scores = await self._call_gemini_api(dialogue_text)
                
                latency_ms = int((time.time() - start_time) * 1000)
                return scores, latency_ms, retry_count
                
            except Exception as e:
                retry_count += 1
                if attempt < self.config.max_retries - 1:
                    # 指数退避
                    wait_time = (2 ** attempt) + (time.time() % 1) * 0.3
                    await asyncio.sleep(wait_time)
                    logger.warning(f"API调用失败，重试 {attempt + 1}/{self.config.max_retries}: {e}")
                else:
                    raise
        
        # 不应该到达这里
        raise Exception("所有重试都失败")
    
    async def _call_gemini_api(self, dialogue_text: str) -> Dict[str, float]:
        """调用Gemini API（需要实际实现）"""
        # 这里需要实际的Gemini API调用
        # 由于我们没有真实的API key，暂时使用模拟
        logger.warning("使用模拟Gemini API调用")
        return await self._simulate_single_evaluation(dialogue_text)
    
    async def _simulate_single_evaluation(self, dialogue_text: str) -> Dict[str, float]:
        """模拟单次评估"""
        import random
        
        # 模拟API延迟
        await asyncio.sleep(random.uniform(0.5, 2.0))
        
        # 基于文本特征生成合理的评分
        base_scores = self._analyze_text_features(dialogue_text)
        
        # 添加小幅随机变化模拟API不确定性
        noise_level = 0.05
        scores = {}
        for key, base_score in base_scores.items():
            if key != "explanation":
                noise = random.gauss(0, noise_level)
                scores[key] = max(0.0, min(1.0, base_score + noise))
        
        return scores
    
    def _analyze_text_features(self, text: str) -> Dict[str, float]:
        """基于文本特征分析评分"""
        scores = {
            "logic_rigor": 0.70,
            "question_quality": 0.65,
            "reasoning_completeness": 0.68,
            "natural_interaction": 0.72
        }
        
        # 逻辑严谨性
        if any(word in text for word in ["因为", "所以", "首先", "然后", "因此"]):
            scores["logic_rigor"] += 0.15
        if "<think>" in text:
            scores["logic_rigor"] += 0.10
        
        # 提问质量
        question_count = text.count("?") + text.count("？")
        if question_count > 0:
            scores["question_quality"] += min(0.20, question_count * 0.05)
        if any(word in text for word in ["请问", "能否", "是否"]):
            scores["question_quality"] += 0.10
        
        # 推理完整性
        step_indicators = ["步骤", "第一", "第二", "→", "计算"]
        step_count = sum(text.count(indicator) for indicator in step_indicators)
        scores["reasoning_completeness"] += min(0.25, step_count * 0.03)
        
        # 交互自然度
        if any(word in text for word in ["请", "谢谢", "好的", "您"]):
            scores["natural_interaction"] += 0.15
        if any(emoji in text for emoji in ["😊", "✨", "🎯"]):
            scores["natural_interaction"] += 0.10
        
        # 确保分数在合理范围
        for key in scores:
            scores[key] = max(0.1, min(1.0, scores[key]))
        
        return scores
    
    async def _simulate_evaluation(self, dialogue: Dict) -> Tuple[Dict[str, float], float, Dict[str, Any]]:
        """模拟完整评估流程"""
        dialogue_text = self._extract_dialogue_text(dialogue)
        
        # 生成K次评估
        evaluations = []
        total_latency = 0
        
        for i in range(self.config.k_evaluations):
            start_time = time.time()
            scores = await self._simulate_single_evaluation(dialogue_text)
            latency = int((time.time() - start_time) * 1000)
            total_latency += latency
            evaluations.append(scores)
        
        # 聚合结果
        median_scores, variance = self._aggregate_evaluations(evaluations)
        
        metadata = {
            "api_calls": self.config.k_evaluations,
            "total_latency_ms": total_latency,
            "retries": 0,
            "errors": [],
            "variance": variance,
            "stability": "stable" if variance <= self.config.variance_threshold else "unstable",
            "mode": "simulation"
        }
        
        return median_scores, variance, metadata
    
    def _aggregate_evaluations(self, evaluations: List[Dict[str, float]]) -> Tuple[Dict[str, float], float]:
        """聚合多次评估结果"""
        if not evaluations:
            return self._get_default_scores(), 0.0
        
        # 计算每个维度的median
        dimensions = ["logic_rigor", "question_quality", "reasoning_completeness", "natural_interaction"]
        median_scores = {}
        variances = []
        
        for dim in dimensions:
            values = [eval_result.get(dim, 0.5) for eval_result in evaluations]
            median_scores[dim] = statistics.median(values)
            
            # 计算方差
            if len(values) > 1:
                variance = statistics.variance(values)
                variances.append(variance)
        
        # 总体方差
        overall_variance = statistics.mean(variances) if variances else 0.0
        
        return median_scores, overall_variance
    
    async def _rate_limit(self):
        """速率限制"""
        now = time.time()
        
        # 清理旧的请求时间
        self.request_times = [t for t in self.request_times if now - t < 60]
        
        # 检查是否超过限制（每分钟60个请求）
        if len(self.request_times) >= 60:
            sleep_time = 60 - (now - self.request_times[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        self.request_times.append(now)
    
    async def _get_fallback_scores(self, dialogue_text: str) -> Dict[str, float]:
        """获取备用评分"""
        return self._analyze_text_features(dialogue_text)
    
    def _get_default_scores(self) -> Dict[str, float]:
        """获取默认评分"""
        return {
            "logic_rigor": 0.5,
            "question_quality": 0.5,
            "reasoning_completeness": 0.5,
            "natural_interaction": 0.5
        }
    
    def _extract_dialogue_text(self, dialogue: Dict) -> str:
        """提取对话文本"""
        if "turns" in dialogue:
            parts = []
            for turn in dialogue["turns"]:
                if isinstance(turn, dict):
                    role = turn.get("role", "")
                    content = turn.get("content", "")
                    parts.append(f"{role}: {content}")
            return "\n".join(parts)
        elif "content" in dialogue:
            return dialogue["content"]
        else:
            return str(dialogue)

class UnstableSampleTracker:
    """不稳定样本跟踪器"""
    
    def __init__(self, output_file: str = "logs/unstable_samples.jsonl"):
        self.output_file = output_file
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    def track_unstable_sample(self, dialogue: Dict, variance: float, 
                            scores: Dict[str, float], metadata: Dict[str, Any]):
        """记录不稳定样本"""
        record = {
            "timestamp": time.time(),
            "dialogue_id": dialogue.get("id", "unknown"),
            "variance": variance,
            "scores": scores,
            "metadata": metadata,
            "reason": "high_variance" if variance > 0.08 else "other"
        }
        
        # 追加到JSONL文件
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        
        logger.warning(f"记录不稳定样本: {dialogue.get('id')} (variance={variance:.4f})")
    
    def get_unstable_stats(self) -> Dict[str, Any]:
        """获取不稳定样本统计"""
        try:
            with open(self.output_file, "r", encoding="utf-8") as f:
                records = [json.loads(line) for line in f if line.strip()]
            
            if not records:
                return {"total": 0, "avg_variance": 0.0}
            
            return {
                "total": len(records),
                "avg_variance": sum(r["variance"] for r in records) / len(records),
                "latest_timestamp": max(r["timestamp"] for r in records),
                "reasons": [r["reason"] for r in records]
            }
        except FileNotFoundError:
            return {"total": 0, "avg_variance": 0.0}

async def test_live_scoring():
    """测试live scoring系统"""
    print(f"🧪 测试Live Scoring系统 (LIVE_MODE={REWARD_LIVE_MODE})")
    print("=" * 60)
    
    # 测试对话
    test_dialogue = {
        "id": "live_test_001",
        "turns": [
            {"role": "user", "content": "一个正方形的周长是20厘米，面积是多少？"},
            {"role": "assistant", "content": "<think>正方形周长=4×边长，所以边长=20÷4=5厘米。面积=边长²=5²=25平方厘米。</think>\n\n解题步骤：\n1. 求边长：周长÷4 = 20÷4 = 5厘米\n2. 求面积：边长² = 5² = 25平方厘米\n\n答案：25平方厘米"}
        ]
    }
    
    # 创建评估器
    config = ScoringConfig(k_evaluations=3, variance_threshold=0.08)
    evaluator = LiveGeminiEvaluator(config)
    tracker = UnstableSampleTracker()
    
    print("开始评估...")
    start_time = time.time()
    
    # 执行评估
    scores, variance, metadata = await evaluator.evaluate_dialogue_live(test_dialogue)
    
    execution_time = time.time() - start_time
    
    # 显示结果
    print(f"\n📊 评估结果:")
    print(f"执行时间: {execution_time:.2f}秒")
    print(f"方差: {variance:.4f}")
    print(f"稳定性: {'稳定' if variance <= config.variance_threshold else '不稳定'}")
    
    print(f"\n📈 各维度评分:")
    for dim, score in scores.items():
        print(f"  {dim}: {score:.3f}")
    
    print(f"\n🔧 元数据:")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    
    # 检查是否需要标记为不稳定
    if variance > config.variance_threshold:
        tracker.track_unstable_sample(test_dialogue, variance, scores, metadata)
        print(f"\n⚠️  样本已标记为不稳定！")
    
    # 统计信息
    unstable_stats = tracker.get_unstable_stats()
    print(f"\n📋 不稳定样本统计:")
    print(json.dumps(unstable_stats, indent=2, ensure_ascii=False))

def main():
    """主函数"""
    asyncio.run(test_live_scoring())

if __name__ == "__main__":
    main()
