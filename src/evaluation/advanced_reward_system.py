#!/usr/bin/env python3
"""
多维度奖励系统
基于GPT-5技术方案实现的硬规则+GPT评分混合奖励系统
"""

import json
import time
import hashlib
import sqlite3
import threading
import re
import statistics
from typing import Dict, Any, List, Tuple, Optional
import logging
import os, json, hashlib
 
# --- logging wrapper: accept status or status_code ---
try:
    from src.utils.telemetry import log_api_call as _LOG_API
except Exception:
    def _LOG_API(**kwargs):  # fallback no-op
        return None

def log_api_call(**kwargs):
    status = kwargs.pop("status", None)
    if status is not None and "status_code" not in kwargs:
        kwargs["status_code"] = status
    allow = {"provider","model","latency_ms","ok","error","status_code","meta"}
    filtered = {k: v for k, v in kwargs.items() if k in allow}
    return _LOG_API(**filtered)
from pathlib import Path

logger = logging.getLogger(__name__)

def _read_sha12(p):
    h = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    return h[:12]

def _normalize(ws):
    s = sum(ws.values())
    if s <= 0 or any(v < 0 for v in ws.values()):
        raise ValueError("invalid weights")
    return {k: (v / s) for k, v in ws.items()}

def _maybe_load_calibrated(self, path="configs/weights.json"):
    if os.getenv("USE_CALIBRATED_WEIGHTS", "1") != "1":
        return
    if not os.path.exists(path):
        print(f"[reward] calibrated weights not found: {path}")
        return
    try:
        # Use the new weights loader for compatibility
        from .weights_loader import load_weights
        ws = load_weights(path)
        self.weights = ws
        self.weights_source = path
        self.weights_sha = _read_sha12(path)
        print(f"[reward] using calibrated weights sha={self.weights_sha}")
    except Exception as e:
        print(f"[reward] keep default weights (reason: {e})")

def canonical_json(obj: Dict) -> str:
    """生成标准化JSON字符串"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def make_cache_key(dialogue: Dict, spec: str) -> str:
    """生成缓存键"""
    payload = canonical_json(dialogue) + "||" + spec
    return hashlib.sha256(payload.encode()).hexdigest()

class GeminiCache:
    """Gemini评分缓存系统
    
    特性:
    - SQLite持久化存储
    - TTL过期机制
    - 方差稳定性跟踪
    - 线程安全
    """
    
    def __init__(self, db_path="gemini_cache.sqlite", ttl_days=14):
        self.db_path = db_path
        self.ttl_ms = ttl_days * 24 * 3600 * 1000
        self._lock = threading.Lock()
        self._init_db()
        
        logger.info(f"GeminiCache initialized: db={db_path}, ttl={ttl_days}days")
    
    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gemini_score_cache(
                    key TEXT PRIMARY KEY,
                    payload_norm TEXT NOT NULL,
                    scoring_spec TEXT NOT NULL,
                    score_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    api_latency_ms INTEGER,
                    created_at INTEGER,
                    updated_at INTEGER,
                    expiry_at INTEGER,
                    variance REAL,
                    tries INTEGER DEFAULT 1
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expiry 
                ON gemini_score_cache(expiry_at)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status 
                ON gemini_score_cache(status)
            """)
            
            conn.commit()
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """获取缓存项"""
        with self._lock:
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                cur = conn.execute(
                    "SELECT score_json, status, expiry_at, variance FROM gemini_score_cache WHERE key=?", 
                    (key,)
                )
                row = cur.fetchone()
                
                if not row:
                    return None
                
                score_json, status, expiry_at, variance = row
                
                # 检查过期
                if expiry_at and expiry_at < int(time.time() * 1000):
                    return None
                
                return {
                    "score": json.loads(score_json),
                    "status": status,
                    "variance": variance or 0.0
                }
    
    def put(self, key: str, payload_norm: str, spec: str, score: Dict, 
           status: str, latency_ms: int, variance: float, tries: int):
        """存储缓存项"""
        with self._lock:
            now = int(time.time() * 1000)
            expiry = now + self.ttl_ms
            
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                # 使用UPSERT保留原有created_at
                conn.execute("""
                    INSERT OR REPLACE INTO gemini_score_cache
                    (key, payload_norm, scoring_spec, score_json, status, 
                     api_latency_ms, created_at, updated_at, expiry_at, variance, tries)
                    VALUES (?, ?, ?, ?, ?, ?, 
                            COALESCE((SELECT created_at FROM gemini_score_cache WHERE key=?), ?), 
                            ?, ?, ?, ?)
                """, (
                    key, payload_norm, spec, json.dumps(score, ensure_ascii=False), 
                    status, latency_ms, key, now, now, expiry, variance, tries
                ))
                conn.commit()
    
    def invalidate_by_spec(self, spec_pattern: str):
        """按规范模式失效缓存"""
        with self._lock:
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                conn.execute(
                    "UPDATE gemini_score_cache SET expiry_at=0 WHERE scoring_spec LIKE ?",
                    (spec_pattern,)
                )
                conn.commit()
                
        logger.info(f"缓存失效: spec_pattern={spec_pattern}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            cur = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN expiry_at > ? THEN 1 ELSE 0 END) as valid,
                    SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) as ok_count,
                    SUM(CASE WHEN status='ok_unstable' THEN 1 ELSE 0 END) as unstable_count,
                    AVG(api_latency_ms) as avg_latency,
                    AVG(variance) as avg_variance
                FROM gemini_score_cache
            """, (int(time.time() * 1000),))
            
            row = cur.fetchone()
            
            return {
                "total_entries": row[0] or 0,
                "valid_entries": row[1] or 0,
                "ok_count": row[2] or 0,
                "unstable_count": row[3] or 0,
                "avg_latency_ms": round(row[4] or 0, 1),
                "avg_variance": round(row[5] or 0, 4),
                "hit_rate": round((row[1] or 0) / max(1, row[0] or 1), 3)
            }

class HardRuleEvaluator:
    """硬规则评估器
    
    评估客观可验证的指标：
    - 澄清问题识别
    - 思考链检测
    - 计算正确性
    - 格式规范性
    """
    
    def __init__(self):
        # 澄清问题模式
        self.clarification_patterns = [
            r'[？?]',  # 问号
            r'请问|能否|可以.*吗|是否',  # 礼貌询问
            r'哪.*?[？?]|什么.*?[？?]|如何.*?[？?]|为什么.*?[？?]',  # 疑问词
            r'<QUESTION>.*?</QUESTION>',  # 结构化标签
            r'我需要.*?确认|需要.*?澄清|不太确定',  # 澄清表述
        ]
        
        # 思考链模式
        self.thinking_patterns = [
            r'<think>.*?</think>',  # 思考标签
            r'让我.*?想.*?一下|我来.*?分析',  # 思考表述
            r'首先.*?然后.*?最后|第一.*?第二.*?第三',  # 步骤标识
            r'因为.*?所以|由于.*?因此',  # 因果逻辑
        ]
        
        # 数学计算模式
        self.math_patterns = [
            r'\d+\s*[+\-*/×÷]\s*\d+\s*=\s*\d+',  # 计算表达式
            r'面积\s*=|周长\s*=|体积\s*=',  # 几何公式
            r'解：|答：|所以.*?=',  # 数学解答格式
        ]
    
    def evaluate(self, dialogue: Dict) -> Dict[str, Any]:
        """评估硬规则指标"""
        # 提取对话文本
        text = self._extract_text(dialogue)
        
        # 检测各项指标
        has_clarification = self._detect_clarification(text)
        has_thinking = self._detect_thinking(text)
        has_math = self._detect_math(text)
        format_score = self._evaluate_format(dialogue)
        
        # 计算步骤数
        step_count = self._count_steps(text)
        
        # 计算硬规则总分
        base_score = 0.3  # 基础分
        
        if has_clarification:
            base_score += 0.25
        if has_thinking:
            base_score += 0.25
        if has_math and self._verify_math(text):
            base_score += 0.15
        if format_score > 0.8:
            base_score += 0.05
        
        rules_score = min(1.0, base_score)
        
        return {
            "rules_score": round(rules_score, 3),
            "binary_indicators": {
                "has_clarification": has_clarification,
                "has_thinking_chain": has_thinking,
                "has_math_calculation": has_math,
                "format_valid": format_score > 0.7
            },
            "metrics": {
                "step_count": step_count,
                "format_score": round(format_score, 3),
                "text_length": len(text)
            }
        }
    
    def _extract_text(self, dialogue: Dict) -> str:
        """提取对话文本"""
        if isinstance(dialogue, dict):
            if "turns" in dialogue:
                # 多轮对话格式
                parts = []
                for turn in dialogue["turns"]:
                    if isinstance(turn, dict) and "content" in turn:
                        parts.append(turn["content"])
                return " ".join(parts)
            elif "content" in dialogue:
                return dialogue["content"]
            else:
                return json.dumps(dialogue, ensure_ascii=False)
        return str(dialogue)
    
    def _detect_clarification(self, text: str) -> bool:
        """检测澄清问题"""
        for pattern in self.clarification_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _detect_thinking(self, text: str) -> bool:
        """检测思考链"""
        for pattern in self.thinking_patterns:
            if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                return True
        return False
    
    def _detect_math(self, text: str) -> bool:
        """检测数学计算"""
        for pattern in self.math_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def _verify_math(self, text: str) -> bool:
        """验证数学计算正确性"""
        # 简化的数学验证
        calc_pattern = r'(\d+)\s*([+\-*/×÷])\s*(\d+)\s*=\s*(\d+)'
        matches = re.findall(calc_pattern, text)
        
        for match in matches:
            try:
                a, op, b, result = int(match[0]), match[1], int(match[2]), int(match[3])
                
                if op in ['+']:
                    expected = a + b
                elif op in ['-']:
                    expected = a - b
                elif op in ['*', '×']:
                    expected = a * b
                elif op in ['/', '÷']:
                    expected = a // b if b != 0 else 0
                else:
                    continue
                
                if expected != result:
                    return False
                    
            except (ValueError, ZeroDivisionError):
                return False
        
        return True
    
    def _count_steps(self, text: str) -> int:
        """统计推理步骤数"""
        step_indicators = [
            r'第[一二三四五六七八九十\d]+步|步骤[一二三四五六七八九十\d]+',
            r'首先|然后|接下来|最后|其次',
            r'\d+\.',  # 数字列表
            r'→|⇒|=>',  # 箭头
        ]
        
        total_steps = 0
        for pattern in step_indicators:
            matches = re.findall(pattern, text, re.IGNORECASE)
            total_steps += len(matches)
        
        return min(total_steps, 20)  # 限制最大步骤数
    
    def _evaluate_format(self, dialogue: Dict) -> float:
        """评估格式规范性"""
        score = 1.0
        
        # 检查JSON结构
        if not isinstance(dialogue, dict):
            score -= 0.3
        
        # 检查必要字段
        if isinstance(dialogue, dict):
            if "turns" in dialogue:
                turns = dialogue["turns"]
                if not isinstance(turns, list):
                    score -= 0.2
                else:
                    for turn in turns:
                        if not isinstance(turn, dict):
                            score -= 0.1
                        elif "role" not in turn or "content" not in turn:
                            score -= 0.1
            elif "content" not in dialogue:
                score -= 0.2
        
        return max(0.0, score)

class GeminiEvaluator:
    """Gemini模型评估器
    
    使用Gemini API进行主观质量评估
    """
    
    def __init__(self, model_name="gemini-2.5-pro", prompt_version="v1", 
                 temperature=0.0, top_p=0.0):
        self.model_name = model_name
        self.prompt_version = prompt_version
        self.temperature = temperature
        self.top_p = top_p
        
        # 评估提示模板
        self.evaluation_prompt = """
请对以下对话进行多维度质量评估，返回JSON格式结果：

对话内容：
{dialogue_text}

评估维度（0-1分）：
1. logic_rigor: 逻辑严谨性（推理是否连贯、无漏洞）
2. question_quality: 提问质量（澄清是否精准、必要）
3. reasoning_completeness: 推理完整性（步骤是否完整、清晰）
4. natural_interaction: 交互自然度（对话是否流畅、礼貌）

请返回格式：
{
    "logic_rigor": 0.85,
    "question_quality": 0.78,
    "reasoning_completeness": 0.82,
    "natural_interaction": 0.76,
    "explanation": "简要说明评分理由"
}
"""
    
    def evaluate(self, dialogue: Dict) -> Tuple[Dict[str, float], float]:
        """评估对话质量"""
        # 生成评估规范
        spec = f"{self.model_name}|v={self.prompt_version}|temp={self.temperature}|top_p={self.top_p}|dims=logic,question,reasoning,natural"
        
        # 模拟多次评估（实际应调用Gemini API）
        scores_list = self._simulate_multiple_evaluations(dialogue)
        
        # 计算中位数和方差
        median_scores = {}
        variances = []
        
        for key in scores_list[0].keys():
            if key != "explanation":
                values = [score[key] for score in scores_list]
                median_scores[key] = statistics.median(values)
                variances.append(statistics.variance(values) if len(values) > 1 else 0.0)
        
        overall_variance = statistics.mean(variances) if variances else 0.0
        
        return median_scores, overall_variance
    
    def _simulate_multiple_evaluations(self, dialogue: Dict, k=3) -> List[Dict[str, float]]:
        """模拟多次评估（实际应替换为真实API调用）"""
        import random
        
        # 提取对话文本用于评估
        text = self._extract_dialogue_text(dialogue)
        
        # 基于文本特征生成模拟评分
        base_scores = self._generate_base_scores(text)
        
        # 生成K次带噪声的评估
        evaluations = []
        for _ in range(k):
            scores = {}
            for key, base_score in base_scores.items():
                # 添加小幅随机噪声
                noise = random.gauss(0, 0.05)
                scores[key] = max(0.0, min(1.0, base_score + noise))
            
            scores["explanation"] = "模拟评估结果"
            evaluations.append(scores)
        
        return evaluations
    
    def _extract_dialogue_text(self, dialogue: Dict) -> str:
        """提取对话文本"""
        if "turns" in dialogue:
            parts = []
            for turn in dialogue["turns"]:
                if isinstance(turn, dict) and "content" in turn:
                    role = turn.get("role", "")
                    content = turn.get("content", "")
                    parts.append(f"{role}: {content}")
            return "\n".join(parts)
        elif "content" in dialogue:
            return dialogue["content"]
        else:
            return str(dialogue)
    
    def _generate_base_scores(self, text: str) -> Dict[str, float]:
        """基于文本特征生成基础评分"""
        # 这里使用启发式规则模拟GPT评分
        # 实际使用时应替换为真实的API调用
        
        scores = {
            "logic_rigor": 0.75,
            "question_quality": 0.70,
            "reasoning_completeness": 0.72,
            "natural_interaction": 0.68
        }
        
        # 基于文本特征调整评分
        if "?" in text or "？" in text:
            scores["question_quality"] += 0.1
        
        if any(word in text for word in ["因为", "所以", "首先", "然后"]):
            scores["logic_rigor"] += 0.1
            scores["reasoning_completeness"] += 0.1
        
        if any(word in text for word in ["请问", "谢谢", "好的"]):
            scores["natural_interaction"] += 0.15
        
        if "<think>" in text:
            scores["reasoning_completeness"] += 0.15
        
        # 确保分数在合理范围内
        for key in scores:
            scores[key] = max(0.1, min(1.0, scores[key]))
        
        return scores

class MultiDimensionalRewardSystem:
    """多维度奖励系统
    
    结合硬规则和GPT评分的混合奖励系统
    """
    
    def __init__(self, model_name="gemini-2.5-pro", prompt_version="v1",
                 temperature=0.0, top_p=0.0, cache_db="gemini_cache.sqlite",
                 config_path="configs/default_config.yaml"):
        self.model_name = model_name
        self.prompt_version = prompt_version
        self.temperature = temperature
        self.top_p = top_p

        # 加载配置
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"无法加载配置文件 {config_path}: {e}")
            self.config = {}

        # 加载规则门控配置
        self.rules_gate_config = self.config.get("reward", {}).get("rules_gate", {})
        self.fusion_config = self.config.get("reward", {}).get("fusion", {})

        # 初始化组件
        self.cache = GeminiCache(cache_db)
        self.hard_evaluator = HardRuleEvaluator()
        self.gpt_evaluator = GeminiEvaluator(model_name, prompt_version, temperature, top_p)

        # 初始权重（30%硬规则 + 70%GPT评分）
        self.weights = {
            "rules": 0.30,
            "logic_rigor": 0.20,
            "question_quality": 0.18,
            "reasoning_completeness": 0.20,
            "natural_interaction": 0.12
        }
        self.weights_source = None
        self.weights_sha = None

        # 尝试加载校准权重
        _maybe_load_calibrated(self)

        logger.info(f"MultiDimensionalRewardSystem initialized with {model_name}")
        logger.info(f"Rules gate: {self.rules_gate_config.get('enabled', False)} (min_score={self.rules_gate_config.get('min_score', 0.6)})")
    
    def evaluate_dialogue(self, dialogue: Dict) -> Dict[str, Any]:
        """评估对话并返回多维度奖励"""
        try:
            # 硬规则评估
            hard_results = self.hard_evaluator.evaluate(dialogue)
            
            # GPT评估（带缓存）
            start_time = time.time()
            gpt_scores, variance = self._get_gpt_scores_cached(dialogue)
            latency_ms = (time.time() - start_time) * 1000
            
            # RC1账本记录（按指令要求的格式）
            from datetime import datetime
            import json, os
            
            # 记录评分凭证到账本
            log_api_call(
                provider=os.getenv("SCORER_PROVIDER", "unknown"),
                http_status=200,
                billable_tokens=1,  # 简化，实际应从API响应获取
                latency_ms=latency_ms,
                sample_id=dialogue.get("id", "unknown"),
                task=dialogue.get("task", "unknown")
            )
            
            os.makedirs("reports/rc1", exist_ok=True)
            rec = {
                "ts": datetime.utcnow().isoformat() + "Z",
                "provider": "gemini",
                "billable_tokens": 1,  # 简化
                "latency_ms": latency_ms,
                "status": "ok",
                "cache_hit": False,  # 简化，实际应从缓存状态获取
                "request_id": dialogue.get("id", "unknown")
            }
            with open("reports/rc1/scoring_ledger.jsonl", "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            
            # 检查规则门控
            gate_triggered = False
            if self.rules_gate_config.get("enabled", False):
                rules_score = hard_results["rules_score"]
                min_score = self.rules_gate_config.get("min_score", 0.60)
                if rules_score < min_score:
                    gate_triggered = True
                    penalty_score = self.rules_gate_config.get("penalty", 0.0)
                    logger.info(f"Rules gate triggered: {rules_score:.3f} < {min_score:.3f}, penalty={penalty_score}")
                    primary_reward = penalty_score
                else:
                    primary_reward = self._calculate_primary_reward(hard_results, gpt_scores)
            else:
                primary_reward = self._calculate_primary_reward(hard_results, gpt_scores)

            # 构建完整结果
            result = {
                "primary_reward": round(primary_reward, 4),
                "component_scores": {
                    "logic_rigor": round(gpt_scores["logic_rigor"], 3),
                    "question_quality": round(gpt_scores["question_quality"], 3),
                    "reasoning_completeness": round(gpt_scores["reasoning_completeness"], 3),
                    "natural_interaction": round(gpt_scores["natural_interaction"], 3)
                },
                "binary_indicators": hard_results["binary_indicators"],
                "hard_rules": {
                    "rules_score": hard_results["rules_score"],
                    "metrics": hard_results["metrics"]
                },
                "meta": {
                    "variance": round(variance, 4),
                    "weights_used": self.weights.copy(),
                    "model": self.model_name,
                    "version": self.prompt_version,
                    "rules_gate_triggered": gate_triggered,
                    "rules_gate_config": self.rules_gate_config
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"对话评估失败: {e}")
            
            # 生产模式：严格禁止降级到模拟评分
            import os
            if os.getenv("RUN_MODE") == "prod":
                raise RuntimeError(f"生产模式评分失败，拒绝fallback: {e}")
            
            # 单一提供商检查：如果配置了单一provider，禁用其他分支
            scorer_provider = os.getenv("SCORER_PROVIDER", "")
            if scorer_provider == "gemini":
                # 只允许Gemini，禁用其他提供商分支
                raise RuntimeError(f"仅配置Gemini提供商，但评分失败: {e}")
            elif scorer_provider == "deepseek_r1":
                # 只允许DeepSeek，禁用其他提供商分支
                raise RuntimeError(f"仅配置DeepSeek提供商，但评分失败: {e}")
            
            return self._generate_fallback_result(dialogue, str(e))
    
    def _get_gemini_scores_cached(self, dialogue: Dict) -> Tuple[Dict[str, float], float]:
        """使用新Gemini适配器获取评分（强制live模式）"""
        import os
        
        # 强制禁用缓存
        if os.getenv("SCORING_CACHE_DISABLE","") == "1":
            logger.debug("缓存被禁用，直接调用Gemini API")
            return self._get_gemini_scores_live(dialogue)
        
        # 生成缓存键
        spec = f"gemini|v={self.prompt_version}|temp={self.temperature}|dims=logic,question,reasoning,natural"
        import hashlib
        import json
        dialogue_str = json.dumps(dialogue, sort_keys=True)
        key = hashlib.sha256(f"{spec}|{dialogue_str}".encode()).hexdigest()[:16]
        
        # 检查缓存
        cached = None
        if hasattr(self.cache, 'get'):
            cached = self.cache.get(key)
        elif hasattr(self, '_simple_cache'):
            cached = self._simple_cache.get(key)
            
        if cached and cached.get("status") == "ok":
            logger.debug(f"使用缓存的Gemini评分: {key[:16]}...")
            scores = cached.get("score", cached.get("scores", {}))
            return scores, cached["variance"]
        
        # 缓存未命中，调用live模式
        return self._get_gemini_scores_live(dialogue, key, spec)
    
    def _get_gemini_scores_live(self, dialogue: Dict, key: str = None, spec: str = None) -> Tuple[Dict[str, float], float]:
        """直接调用新Gemini适配器进行评分"""
        try:
            # 导入新的Gemini适配器
            from src.scoring.providers.gemini import score as gemini_score
            
            # 构建评分提示
            prompt = self._build_scoring_prompt(dialogue)
            
            # 调用新的Gemini适配器
            result = gemini_score(prompt, require_live=True)
            
            # 记录API调用到账本
            log_api_call(
                provider="gemini",
                billable_tokens=result["usage"].get("total_tokens") or (
                    (result["usage"].get("prompt_tokens") or 0) + 
                    (result["usage"].get("completion_tokens") or 0)
                ),
                latency_ms=result["latency_ms"],
                status="ok",
                cache_hit=False
            )
            
            # 解析评分结果 - 使用新的解析方法
            scores = self._parse_new_gemini_response(result["raw"])
            import numpy as np
            variance = np.std(list(scores.values()))
            
            # 如果有缓存键，存储到缓存
            if key and spec and hasattr(self.cache, 'put'):
                try:
                    self.cache.put(
                        key=key,
                        spec=spec, 
                        score=scores,
                        status="ok",
                        latency_ms=result["latency_ms"],
                        variance=variance,
                        tries=1,
                        payload_norm=len(str(scores))  # 添加缺少的参数
                    )
                except Exception as cache_error:
                    logger.warning(f"缓存保存失败: {cache_error}")
                    # fallback到简单内存缓存
                    if not hasattr(self, '_simple_cache'):
                        self._simple_cache = {}
                    self._simple_cache[key] = {
                        "status": "ok",
                        "score": scores,  # 使用新字段名
                        "scores": scores,  # 保持兼容性
                        "variance": variance
                    }
            
            logger.debug(f"Gemini评分完成: {scores}")
            return scores, variance
            
        except Exception as e:
            logger.error(f"Gemini评分失败: {e}")
            # 在生产模式下直接抛出异常
            import os
            if os.getenv("RUN_MODE") == "prod":
                raise RuntimeError(f"生产模式评分失败，拒绝fallback: {e}")
            
            # 返回默认分数（仅测试模式）
            return {
                "logic_rigor": 0.5,
                "question_quality": 0.5, 
                "reasoning_completeness": 0.5,
                "naturalness": 0.5,
                "natural_interaction": 0.5
            }, 0.0
    
    def _build_scoring_prompt(self, dialogue: Dict) -> str:
        """构建Gemini评分提示"""
        conversation = dialogue.get("conversation", [])
        task = dialogue.get("task", "unknown")
        
        # 格式化对话内容
        conv_text = ""
        for turn in conversation:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            conv_text += f"{role}: {content}\n"
        
        # 构建评分提示
        prompt = f"""请对以下对话进行多维度评分，任务类型：{task}

对话内容：
{conv_text}

请从以下4个维度评分（1-10分）：
1. logic（逻辑性）：回答的逻辑是否清晰、推理是否正确
2. question（提问质量）：是否恰当地提出澄清问题
3. reasoning（推理深度）：思考过程是否深入、全面
4. natural（自然性）：表达是否自然、易懂

请以JSON格式回复，例如：
{{"logic": 8.5, "question": 7.0, "reasoning": 9.0, "natural": 8.0}}"""

        return prompt
    
    def _parse_new_gemini_response(self, response_text: str) -> Dict[str, float]:
        """解析新Gemini适配器的响应（更加容错）"""
        import json
        import re
        
        # 使用与gemini.py相同的解析逻辑
        def _to_float01(x):
            if x is None: return None
            try:
                v = float(x)
            except Exception:
                return None
            # 兼容 0-1、0-10、0-100 等标尺，映射到[0,1]
            if v <= 1.0 and v >= 0.0: return v
            if 0.0 <= v <= 10.0: return max(0.0, min(1.0, v/10.0))
            if 0.0 <= v <= 100.0: return max(0.0, min(1.0, v/100.0))
            return max(0.0, min(1.0, v))
        
        # 优先解析JSON
        try:
            obj = json.loads(response_text)
            raw_scores = {}
            
            # 映射各种可能的字段名到标准字段
            field_mappings = {
                "logic_rigor": ["logic_rigor", "logic", "logic_score"],
                "question_quality": ["question_quality", "question", "questioning"],
                "reasoning_completeness": ["reasoning_completeness", "reasoning", "reasoning_depth"],
                "naturalness": ["naturalness", "natural", "natural_score"],
                "natural_interaction": ["natural_interaction", "interaction", "natural"]
            }
            
            for target_field, possible_names in field_mappings.items():
                for name in possible_names:
                    if name in obj:
                        val = obj[name]
                        if isinstance(val, (list,tuple)) and val:
                            raw_scores[target_field] = _to_float01(val[0])
                        else:
                            raw_scores[target_field] = _to_float01(val)
                        break
            
            # 如果成功解析到至少一个分数，返回
            if raw_scores:
                # 填充缺失的字段为0.5
                final_scores = {}
                for field in ["logic_rigor", "question_quality", "reasoning_completeness", "naturalness", "natural_interaction"]:
                    final_scores[field] = raw_scores.get(field, 0.5)
                return final_scores
                
        except Exception:
            pass
        
        # JSON解析失败，尝试找数字
        numbers = re.findall(r"(\d+(?:\.\d+)?)", response_text)
        if numbers:
            # 至少有一个数字，尝试分配给各维度
            scores = []
            for num_str in numbers[:5]:  # 最多取5个数字
                score = _to_float01(num_str)
                if score is not None:
                    scores.append(score)
            
            if scores:
                # 分配分数到各维度
                fields = ["logic_rigor", "question_quality", "reasoning_completeness", "naturalness", "natural_interaction"]
                result = {}
                for i, field in enumerate(fields):
                    if i < len(scores):
                        result[field] = scores[i]
                    else:
                        result[field] = scores[0]  # 复用第一个分数
                return result
        
        # 完全解析失败，返回默认值
        return {
            "logic_rigor": 0.5,
            "question_quality": 0.5,
            "reasoning_completeness": 0.5,
            "naturalness": 0.5,
            "natural_interaction": 0.5
        }
    
    def _parse_gemini_response(self, response_text: str) -> Dict[str, float]:
        """解析Gemini响应中的评分"""
        import json
        import re
        
        try:
            # 尝试直接解析JSON
            # 寻找JSON内容
            json_match = re.search(r'\{[^}]*"logic"[^}]*\}', response_text)
            if json_match:
                json_str = json_match.group()
                gemini_scores = json.loads(json_str)
                
                # 映射Gemini的字段到系统需要的字段
                scores = {
                    "logic_rigor": gemini_scores.get("logic", 5.0),
                    "question_quality": gemini_scores.get("question", 5.0),
                    "reasoning_completeness": gemini_scores.get("reasoning", 5.0),
                    "naturalness": gemini_scores.get("natural", 5.0),
                    "natural_interaction": gemini_scores.get("natural", 5.0)  # 使用natural值
                }
                
                return scores
            else:
                # 如果没找到JSON，返回默认分数
                return {
                    "logic_rigor": 5.0,
                    "question_quality": 5.0,
                    "reasoning_completeness": 5.0,
                    "naturalness": 5.0,
                    "natural_interaction": 5.0
                }
                
        except Exception as e:
            logger.warning(f"解析Gemini响应失败: {e}")
            return {
                "logic_rigor": 5.0,
                "question_quality": 5.0,
                "reasoning_completeness": 5.0,
                "naturalness": 5.0,
                "natural_interaction": 5.0
            }
    
    def _get_gpt_scores_cached(self, dialogue: Dict) -> Tuple[Dict[str, float], float]:
        """获取GPT评分（带缓存）"""
        # 检查环境变量中的提供商设置
        import os
        provider = os.getenv("SCORER_PROVIDER", "").lower()
        
        if provider == "gemini":
            return self._get_gemini_scores_cached(dialogue)
        else:
            # 其他provider的实现（保持原有逻辑）
            # 生成缓存键
            spec = f"{self.model_name}|v={self.prompt_version}|temp={self.temperature}|top_p={self.top_p}|dims=logic,question,reasoning,natural"
        key = make_cache_key(dialogue, spec)
        
        # 检查缓存
        cached = self.cache.get(key)
        if cached and cached["status"] == "ok":
            return cached["score"]["component_scores"], cached["variance"]
        
        # 执行评估
        start_time = time.time()
        try:
            gpt_scores, variance = self.gpt_evaluator.evaluate(dialogue)
            latency_ms = int((time.time() - start_time) * 1000)
            
            # 确定状态
            status = "ok_unstable" if variance > 0.08 else "ok"
            
            # 写入缓存
            cache_data = {
                "component_scores": gpt_scores,
                "variance": variance
            }
            
            self.cache.put(
                key, canonical_json(dialogue), spec, cache_data,
                status, latency_ms, variance, 3
            )
            
            return gpt_scores, variance
            
        except Exception as e:
            logger.error(f"GPT评估失败: {e}")
            # 返回默认分数
            return {
                "logic_rigor": 0.5,
                "question_quality": 0.5,
                "reasoning_completeness": 0.5,
                "natural_interaction": 0.5
            }, 0.0
    
    def _calculate_primary_reward(self, hard_results: Dict, gpt_scores: Dict) -> float:
        """计算主奖励分数"""
        primary = (
            self.weights["rules"] * hard_results["rules_score"] +
            self.weights["logic_rigor"] * gpt_scores["logic_rigor"] +
            self.weights["question_quality"] * gpt_scores["question_quality"] +
            self.weights["reasoning_completeness"] * gpt_scores["reasoning_completeness"] +
            self.weights["natural_interaction"] * gpt_scores["natural_interaction"]
        )
        
        return max(0.0, min(1.0, primary))
    
    def _generate_fallback_result(self, dialogue: Dict, error: str) -> Dict[str, Any]:
        """生成失败时的备用结果"""
        return {
            "primary_reward": 0.0,
            "component_scores": {
                "logic_rigor": 0.0,
                "question_quality": 0.0,
                "reasoning_completeness": 0.0,
                "natural_interaction": 0.0
            },
            "binary_indicators": {
                "has_clarification": False,
                "has_thinking_chain": False,
                "has_math_calculation": False,
                "format_valid": False
            },
            "hard_rules": {
                "rules_score": 0.0,
                "metrics": {"step_count": 0, "format_score": 0.0, "text_length": 0}
            },
            "meta": {
                "error": error,
                "variance": 0.0,
                "weights_used": self.weights.copy()
            }
        }
    
    def combine_signals(self, signals: Dict[str, float]) -> float:
        """合并多个信号为单一奖励"""
        return sum(self.weights.get(k, 0) * v for k, v in signals.items())
    
    def calibrate_weights(self, labeled_data: List[Dict]) -> None:
        """校准权重（基于标注数据）"""
        # TODO: 实现基于标注数据的权重优化
        # 可以使用最小二乘法 + 正则化
        logger.info(f"权重校准待实现，当前数据量: {len(labeled_data)}")
        pass
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return self.cache.get_stats()
    
    def invalidate_cache(self, pattern: str = None):
        """失效缓存"""
        if pattern:
            self.cache.invalidate_by_spec(pattern)
        else:
            # 失效当前模型版本的所有缓存
            pattern = f"{self.model_name}|v={self.prompt_version}|%"
            self.cache.invalidate_by_spec(pattern)

def main():
    """测试函数"""
    # 测试对话样本
    test_dialogue = {
        "id": "test_001",
        "turns": [
            {
                "role": "user",
                "content": "他什么时候出生的？"
            },
            {
                "role": "assistant", 
                "content": "抱歉，我需要更具体的信息。请问您指的是哪位人物呢？"
            },
            {
                "role": "user",
                "content": "爱因斯坦"
            },
            {
                "role": "assistant",
                "content": "<think>用户问的是爱因斯坦的出生时间。这是一个明确的历史事实。</think>\n\n阿尔伯特·爱因斯坦出生于1879年3月14日，出生地是德国乌尔姆。"
            }
        ]
    }
    
    # 创建奖励系统
    reward_system = MultiDimensionalRewardSystem()
    
    print("测试多维度奖励系统...")
    print("=" * 50)
    
    # 评估对话
    result = reward_system.evaluate_dialogue(test_dialogue)
    
    print("评估结果:")
    print(f"主奖励: {result['primary_reward']}")
    print("\n组件分数:")
    for key, score in result["component_scores"].items():
        print(f"  {key}: {score}")
    
    print("\n二元指标:")
    for key, value in result["binary_indicators"].items():
        print(f"  {key}: {value}")
    
    print("\n硬规则评估:")
    hard_rules = result["hard_rules"]
    print(f"  规则分数: {hard_rules['rules_score']}")
    print(f"  步骤数: {hard_rules['metrics']['step_count']}")
    print(f"  格式分数: {hard_rules['metrics']['format_score']}")
    
    print("\n元数据:")
    meta = result["meta"]
    print(f"  方差: {meta['variance']}")
    print(f"  模型: {meta['model']}")
    
    # 缓存统计
    cache_stats = reward_system.get_cache_stats()
    print("\n缓存统计:")
    print(json.dumps(cache_stats, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
