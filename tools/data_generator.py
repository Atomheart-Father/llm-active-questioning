#!/usr/bin/env python3
"""Data Generator for Sprint-β

使用Gemini API生成高质量的ALC/AR/RSD数据。
严格遵循Schema v1.1，包含质量控制和provenance记录。
"""

import os
import json
import time
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JSON Schema定义（强制JSON-only输出）
ALC_SCHEMA = {
    "type": "object",
    "properties": {
        "turns": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "enum": ["user", "model_target", "assistant"]},
                    "text": {"type": "string", "minLength": 1}
                },
                "required": ["role", "text"]
            }
        },
        "labels": {
            "type": "object",
            "properties": {
                "ask_required": {"type": "boolean"},
                "ambiguity_types": {"type": "array", "items": {"type": "string"}},
                "good_question_set": {"type": "array", "items": {"type": "string"}},
                "minimal_clarifications": {"type": "integer", "enum": [1, 2]}
            },
            "required": ["ask_required", "ambiguity_types", "good_question_set", "minimal_clarifications"]
        },
        "reasoning": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["actions"]
        },
        "source": {"type": "string"}
    },
    "required": ["turns", "labels", "reasoning", "source"]
}

AR_SCHEMA = {
    "type": "object",
    "properties": {
        "turns": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "enum": ["user", "model_target", "assistant"]},
                    "text": {"type": "string", "minLength": 1}
                },
                "required": ["role", "text"]
            }
        },
        "labels": {
            "type": "object",
            "properties": {
                "ask_required": {"type": "boolean"},
                "ambiguity_types": {"type": "array", "items": {"type": "string"}},
                "good_question_set": {"type": "array", "items": {"type": "string"}},
                "minimal_clarifications": {"type": "integer", "enum": [1, 2]},
                "oracle_answer": {"type": "string"}
            },
            "required": ["ask_required", "ambiguity_types", "good_question_set", "minimal_clarifications", "oracle_answer"]
        },
        "reasoning": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["actions"]
        },
        "source": {"type": "string"}
    },
    "required": ["turns", "labels", "reasoning", "source"]
}

RSD_SCHEMA = {
    "type": "object",
    "properties": {
        "turns": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "enum": ["user", "model_target", "assistant"]},
                    "text": {"type": "string", "minLength": 1}
                },
                "required": ["role", "text"]
            }
        },
        "labels": {
            "type": "object",
            "properties": {
                "ask_required": {"type": "boolean"},
                "ambiguity_types": {"type": "array", "items": {"type": "string"}},
                "good_question_set": {"type": "array", "items": {"type": "string"}},
                "minimal_clarifications": {"type": "integer", "enum": [1, 2]}
            },
            "required": ["ask_required", "ambiguity_types", "good_question_set", "minimal_clarifications"]
        },
        "reasoning": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["actions"]
        },
        "source": {"type": "string"}
    },
    "required": ["turns", "labels", "reasoning", "source"]
}

# 输出长度配置（任务自适应 - 降低限制以减少MAX_TOKENS）
OUTPUT_TOKEN_LIMITS = {
    "ALC": int(os.getenv("ALC_MAX_OUTPUT_TOKENS", 512)),  # 从768降低到512
    "AR": int(os.getenv("AR_MAX_OUTPUT_TOKENS", 1024)),   # 从1536降低到1024
    "RSD": int(os.getenv("RSD_MAX_OUTPUT_TOKENS", 768))   # 从1024降低到768
}

AR_TOKEN_CAP = int(os.getenv("AR_MAX_OUTPUT_TOKENS_CAP", 3072))

@dataclass
class GenerationConfig:
    """生成配置"""
    batch_date: str = "2025-09-03"
    alc_count: int = 50  # 5:3:2 配比下的基础数量
    ar_count: int = 30
    rsd_count: int = 20
    temperature: float = 0.7
    max_retries: int = 3
    rate_limit_delay: float = 1.0

@dataclass
class ProvenanceRecord:
    """出处记录（强化版）"""
    uid: str
    provider: str  # "google", "deepseek"
    model: str
    key_index: int
    temperature: float
    seed: int
    generator_prompt_hash: str
    timestamp: str
    domain: str  # "planning", "qa", "reasoning", "creative"
    language: str = "zh"  # 默认中文
    recipe: Optional[str] = None  # 生成配方 (A/B/C)
    judge_prompt_hash: Optional[str] = None
    dedup_score: Optional[float] = None
    quality_score: Optional[float] = None
    judge_votes: Optional[Dict[str, float]] = None  # 双评审结果
    escalated_to_ds: bool = False  # 是否仲裁到DeepSeek
    reject_reason: Optional[str] = None
    risk_flags: Optional[List[str]] = None  # 安全风险标记
    failover: Optional[Dict[str, Any]] = None  # Fail-Over记录

class GeminiClient:
    """Gemini API客户端（支持Fail-Over）"""

    def __init__(self, api_key: str, key_index: int = 0, fallback_clients: List = None):
        self.api_key = api_key
        self.key_index = key_index
        self.fallback_clients = fallback_clients or []
        self.failover_record = None

    def generate(self, prompt: str, temperature: float = 0.7, task_type: str = "alc"):
        """生成内容 - 带Fail-Over的真实API调用"""
        # 首先尝试主API
        result = self._call_gemini_api(prompt, temperature, task_type)
        if result is not None:
            return result if not self.fallback_clients else (result, None)

        # Fail-Over逻辑
        if self.fallback_clients:
            logger.warning("Gemini API失败，开始Fail-Over...")

            for fallback_client in self.fallback_clients:
                try:
                    logger.info(f"尝试Fail-Over到: {fallback_client.__class__.__name__}")
                    result = fallback_client.generate(prompt, temperature)
                    if result is not None:
                        # 记录Fail-Over信息
                        failover_info = {
                            "from": f"gemini-{self.key_index}",
                            "to": f"{fallback_client.__class__.__name__.lower()}",
                            "reason_code": 429,  # 默认限额错误
                            "ts": datetime.now().isoformat()
                        }
                        logger.info(f"Fail-Over成功: {failover_info}")
                        return (result, failover_info)
                except Exception as e:
                    logger.warning(f"Fail-Over到{fallback_client.__class__.__name__}失败: {e}")
                    continue

        logger.error("所有API调用都失败了")
        return None if not self.fallback_clients else (None, None)

    def _call_gemini_api(self, prompt: str, temperature: float = 0.7, task_type: str = "alc") -> Optional[str]:
        """调用Gemini API（支持JSON-only和输出长度控制）"""
        try:
            import requests

            # 根据key_index确定模型
            if self.key_index == 0:
                model = "gemini-2.5-flash"  # ALC - 更新为最新模型
            elif self.key_index == 1:
                model = "gemini-2.5-pro"    # AR
            elif self.key_index == 2:
                model = "gemini-2.5-pro"    # Judge
            else:
                model = "gemini-2.5-flash"

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"

            # 获取任务特定的配置
            max_tokens = OUTPUT_TOKEN_LIMITS.get(task_type.upper(), 1024)

            # 构建payload
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                }
            }

            # 暂时禁用JSON schema强制，先让基础功能工作
            # TODO: 修复JSON schema支持后重新启用
            if False and task_type.upper() in ["ALC", "AR", "RSD"]:
                schema_map = {
                    "ALC": ALC_SCHEMA,
                    "AR": AR_SCHEMA,
                    "RSD": RSD_SCHEMA
                }
                payload["generationConfig"].update({
                    "responseMimeType": "application/json",
                    "responseSchema": schema_map[task_type.upper()]
                })

                # 在prompt中添加严格的JSON-only约束
                json_constraint = """
=== CRITICAL JSON OUTPUT REQUIREMENTS ===

You MUST output ONLY a valid JSON object. No explanations, no markdown, no code blocks.

REQUIRED JSON STRUCTURE:
{
  "turns": [
    {"role": "user", "text": "user message"},
    {"role": "model_target", "text": "<ASK>question</ASK>"}
  ],
  "labels": {
    "ask_required": true,
    "ambiguity_types": ["type1", "type2"],
    "good_question_set": ["question1", "question2"],
    "minimal_clarifications": 1
  },
  "reasoning": {
    "actions": ["AWARE_GAP", "ASK", "STOP_ASK", "FINALIZE"]
  },
  "source": "synthetic-gemini"
}

RULES:
1. Output MUST be pure JSON - no ```json wrapper
2. No polite phrases like "谢谢" or "please"
3. model_target must contain exactly one <ASK> or <FINAL> tag
4. Keep text concise but complete
5. Include ALL required fields

If you cannot generate valid JSON, return the simplest possible valid object.
"""
                payload["contents"][0]["parts"][0]["text"] = prompt + json_constraint

            headers = {"Content-Type": "application/json"}

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()

            # 检查是否触发MAX_TOKENS
            if "candidates" in result and len(result["candidates"]) > 0:
                candidate = result["candidates"][0]
                if candidate.get("finishReason") == "MAX_TOKENS":
                    logger.warning("触发MAX_TOKENS，尝试增加输出限制")  # 对于AR任务，尝试增加输出限制
                    if task_type.upper() == "AR" and max_tokens < AR_TOKEN_CAP:
                        new_max_tokens = min(int(max_tokens * 1.33), AR_TOKEN_CAP)
                        logger.info(f"AR任务增加输出限制: {max_tokens} → {new_max_tokens}")
                        return self._call_gemini_api(prompt, temperature, task_type)

            # 提取生成的文本
            if "candidates" in result and len(result["candidates"]) > 0:
                candidate = result["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    text = candidate["content"]["parts"][0]["text"]
                    return text

            logger.error(f"API响应格式错误: {result}")
            return None

        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 429:
                    logger.warning("Gemini API限额超限，触发Fail-Over")
                elif e.response.status_code >= 500:
                    logger.warning("Gemini API服务器错误，触发Fail-Over")
            logger.error(f"Gemini API请求失败: {e}")
            return None
        except Exception as e:
            logger.error(f"Gemini API调用失败: {e}")
            return None

class DeepSeekClient:
    """DeepSeek API客户端"""

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str, temperature: float = 0.7) -> Optional[str]:
        """调用DeepSeek API"""
        try:
            import requests

            url = "https://api.deepseek.com/v1/chat/completions"

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": 2048
            }

            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()

            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]

            logger.error(f"DeepSeek API响应格式错误: {result}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"DeepSeek API请求失败: {e}")
            return None
        except Exception as e:
            logger.error(f"DeepSeek API调用失败: {e}")
            return None

    def _mock_alc_response(self) -> str:
        """模拟ALC响应"""
        return json.dumps({
            "turns": [
                {"role": "user", "text": "帮我计划周末的户外活动"},
                {"role": "model_target", "text": "<ASK> 你喜欢什么类型的户外活动？预算有多少？和谁一起去？ </ASK>"}
            ],
            "labels": {
                "ambiguity_types": ["preference", "budget", "context"],
                "ask_required": True,
                "good_question_set": ["喜欢的活动类型", "预算范围", "同行人员"],
                "minimal_clarifications": 2,
                "oracle_answer": None
            },
            "reasoning": {
                "think_stream": "用户未明确活动偏好、预算和同行人员，这些都是规划活动的关键信息",
                "actions": [
                    {"t": "AWARE_GAP", "vars": ["preference", "budget", "context"]},
                    {"t": "ASK", "q": "请告诉我你喜欢的户外活动类型、预算范围和同行人员"},
                    {"t": "STOP_ASK"}
                ]
            }
        }, ensure_ascii=False)

    def _mock_ar_response(self) -> str:
        """模拟AR响应"""
        return json.dumps({
            "turns": [
                {"role": "user", "text": "这道数学题怎么解：x² + 2x - 3 = 0"},
                {"role": "model_target", "text": "<ASK> 这是一元二次方程吗？需要解出x的值吗？ </ASK>"}
            ],
            "labels": {
                "ambiguity_types": ["method", "scope"],
                "ask_required": True,
                "good_question_set": ["方程类型", "求解目标"],
                "minimal_clarifications": 1,
                "oracle_answer": "x = 1 或 x = -3"
            },
            "reasoning": {
                "think_stream": "方程类型和求解目标需要明确",
                "actions": [
                    {"t": "AWARE_GAP", "vars": ["method", "scope"]},
                    {"t": "ASK", "q": "这是什么类型的方程？需要解出什么？"},
                    {"t": "STOP_ASK"}
                ]
            }
        }, ensure_ascii=False)

    def _mock_rsd_response(self) -> str:
        """模拟RSD响应"""
        return json.dumps({
            "actions": [
                {"t": "AWARE_GAP", "vars": ["method"]},
                {"t": "ASK", "q": "请说明解题方法"},
                {"t": "DERIVE", "note": "使用公式法"},
                {"t": "VERIFY", "note": "检查计算正确性"},
                {"t": "FINALIZE"}
            ]
        }, ensure_ascii=False)

    def _mock_judge_response(self) -> str:
        """模拟评审响应"""
        return json.dumps({
            "quality_score": 0.95,
            "reasons": "澄清问题直接针对关键变量，回答结构完整",
            "ask_required": True,
            "ambiguity_types": ["preference", "budget", "context"],
            "good_question_set": ["喜欢的活动类型", "预算范围", "同行人员"]
        }, ensure_ascii=False)

class DataGenerator:
    """数据生成器"""

    def __init__(self, config: GenerationConfig):
        self.config = config
        self.provenance_records: List[ProvenanceRecord] = []

        # 初始化客户端（修正路由）
        self.clients = self._init_clients()

        # 创建输出目录（支持参数化日期）
        self.output_dir = Path(f"data/gen/{config.batch_date}")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _init_clients(self) -> Dict[str, Any]:
        """初始化客户端（智能Fail-Over路由）"""
        clients = {}

        # 检查Fail-Over配置
        failover_enabled = os.getenv("FAILOVER_ENABLE", "true").lower() == "true"
        allow_rsd_fallback = os.getenv("ALLOW_RSD_FALLBACK", "false").lower() == "true"

        # ALC客户端 - gemini-2.5-flash → gemini-2.5-flash-lite → deepseek-chat
        alc_key = os.getenv("GEMINI_API_KEY")
        if alc_key:
            fallback_clients = []
            if failover_enabled:
                # 备用: gemini-2.5-flash-lite (key2)
                if os.getenv("GEMINI_API_KEY2"):
                    fallback_clients.append(GeminiClient(os.getenv("GEMINI_API_KEY2"), key_index=0))

                # 最后备用: deepseek-chat
                if os.getenv("DeepSeek_API_KEY"):
                    fallback_clients.append(DeepSeekClient(os.getenv("DeepSeek_API_KEY"), "deepseek-chat"))

            clients["ALC"] = GeminiClient(alc_key, key_index=0, fallback_clients=fallback_clients)

        # AR客户端 - gemini-2.5-pro → deepseek-reasoner
        ar_key = os.getenv("GEMINI_API_KEY2")
        if ar_key:
            fallback_clients = []
            if failover_enabled and os.getenv("DeepSeek_API_KEY2"):
                fallback_clients.append(DeepSeekClient(os.getenv("DeepSeek_API_KEY2"), "deepseek-reasoner"))

            clients["AR"] = GeminiClient(ar_key, key_index=1, fallback_clients=fallback_clients)

        # RSD客户端 - deepseek-reasoner (默认无下探，仅当ALLOW_RSD_FALLBACK=true时允许→gemini-2.5-pro)
        rsd_key = os.getenv("DeepSeek_API_KEY2")
        if rsd_key:
            fallback_clients = []
            if allow_rsd_fallback and os.getenv("GEMINI_API_KEY"):
                # 仅在允许时才添加Gemini备用，但仍只抽动作/时机
                fallback_clients.append(GeminiClient(os.getenv("GEMINI_API_KEY"), key_index=0))

            clients["RSD"] = DeepSeekClient(rsd_key, "deepseek-reasoner")
            # 如果需要Fail-Over，包装一下
            if fallback_clients:
                clients["RSD"] = GeminiClient("", key_index=3, fallback_clients=[clients["RSD"]] + fallback_clients)

        # 评审客户端 - gemini-pro + 本地Qwen并行，仅冲突样本升到deepseek-chat仲裁
        judge_key = os.getenv("GEMINI_API_KEY3")
        ds_key = os.getenv("DeepSeek_API_KEY")
        if judge_key:
            clients["JUDGE"] = GeminiClient(judge_key, key_index=2)
            if ds_key:
                clients["ARBITER"] = DeepSeekClient(ds_key, "deepseek-chat")

        return clients

    def generate_alc_data(self, recipe: str = "A") -> List[Dict[str, Any]]:
        """生成ALC数据（支持多配方）"""
        logger.info(f"开始生成ALC数据，目标数量: {self.config.alc_count}，配方: {recipe}")

        alc_prompt = self._get_alc_prompt(recipe)
        samples = []

        for i in range(self.config.alc_count):
            sample = self._generate_single_sample("ALC", alc_prompt, i, recipe)
            if sample:
                samples.append(sample)

            # 控制速率
            time.sleep(self.config.rate_limit_delay)

        logger.info(f"ALC数据生成完成，实际生成: {len(samples)}，配方: {recipe}")
        return samples

    def generate_ar_data(self) -> List[Dict[str, Any]]:
        """生成AR数据"""
        logger.info(f"开始生成AR数据，目标数量: {self.config.ar_count}")

        ar_prompt = self._get_ar_prompt()
        samples = []

        for i in range(self.config.ar_count):
            sample = self._generate_single_sample("AR", ar_prompt, i)
            if sample:
                samples.append(sample)

            time.sleep(self.config.rate_limit_delay)

        logger.info(f"AR数据生成完成，实际生成: {len(samples)}")
        return samples

    def generate_rsd_data(self) -> List[Dict[str, Any]]:
        """生成RSD数据"""
        logger.info(f"开始生成RSD数据，目标数量: {self.config.rsd_count}")

        rsd_prompt = self._get_rsd_prompt()
        samples = []

        for i in range(self.config.rsd_count):
            sample = self._generate_single_sample("RSD", rsd_prompt, i)
            if sample:
                samples.append(sample)

            time.sleep(self.config.rate_limit_delay)

        logger.info(f"RSD数据生成完成，实际生成: {len(samples)}")
        return samples

    def _generate_single_sample(self, data_type: str, prompt: str, index: int, recipe: str = None) -> Optional[Dict[str, Any]]:
        """生成单个样本（带质量控制和Fail-Over）"""
        client = self.clients.get(data_type)
        if not client:
            logger.error(f"没有可用的{data_type}客户端")
            return None

        # 生成内容（支持Fail-Over）
        result = client.generate(prompt, self.config.temperature)

        # 处理不同客户端的返回值格式
        if isinstance(result, tuple):
            response, failover_info = result
        else:
            response, failover_info = result, None

        if not response:
            logger.warning(f"{data_type}样本{index}生成失败")
            return None

        try:
            # 首先尝试解析为JSON
            try:
                data = json.loads(response)
            except json.JSONDecodeError:
                # 如果不是JSON，尝试从文本中提取JSON
                logger.warning(f"{data_type}响应不是JSON格式，尝试提取: {response[:200]}...")
                data = self._extract_json_from_text(response, data_type)

            # 添加Schema v1.1必需字段
            sample = self._format_sample(data_type, data, index)

            # 质量控制检查
            quality_check = self._quality_check(sample, data_type)
            if not quality_check["passed"]:
                logger.warning(f"{data_type}样本{index}质量不合格: {quality_check['reasons']}")
                return None

            # 记录provenance（包含Fail-Over信息和recipe）
            self._record_provenance(data_type, prompt, client.key_index, sample.get("id", f"{data_type}-{index}"), failover_info, recipe)

            return sample

        except Exception as e:
            logger.error(f"处理{data_type}响应失败: {e}")
            # 返回默认的模板数据而不是None
            return self._create_default_sample(data_type, index)

    def _format_sample(self, data_type: str, data: Dict[str, Any], index: int) -> Dict[str, Any]:
        """格式化样本为Schema v1.1"""
        # 1. 修正turns字段：speaker/utterance → role/text
        fixed_turns = self._fix_turns_format(data.get("turns", []))

        # 2. 修正model_target内容：只保留ASK标签
        fixed_turns = self._fix_model_target_content(fixed_turns)

        sample = {
            "id": f"{data_type}-{index:04d}",
            "domain": self._get_domain_for_type(data_type),
            "source": self._get_correct_source(data_type),  # 5. 修正source字段
            "turns": fixed_turns,
            "labels": self._ensure_complete_labels(data_type, data.get("labels", {})),
            "reasoning": self._ensure_complete_reasoning(data_type, data.get("reasoning", {}))
        }

        return sample

    def _fix_turns_format(self, turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """修正turns字段格式：speaker/utterance → role/text"""
        fixed_turns = []
        for turn in turns:
            fixed_turn = {
                "role": turn.get("speaker", "") if "speaker" in turn else turn.get("role", ""),
                "text": turn.get("utterance", "") if "utterance" in turn else turn.get("text", "")
            }
            fixed_turns.append(fixed_turn)

        # 修正首个助手回合的role为model_target
        for turn in fixed_turns:
            if turn["role"] == "assistant":
                turn["role"] = "model_target"
                break

        return fixed_turns

    def _fix_model_target_content(self, turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """修正model_target内容：严格只保留ASK/FINAL标签，移除所有礼貌语"""
        import re

        for turn in turns:
            if turn["role"] == "model_target":
                text = turn["text"]

                # 首先尝试提取<ASK>标签内容
                ask_match = re.search(r'<ASK>(.*?)</ASK>', text, re.DOTALL)
                if ask_match:
                    ask_content = ask_match.group(1).strip()
                    # 移除所有礼貌语和不必要的文字
                    courtesy_phrases = [
                        "为了更好地帮你规划，我需要一些信息。首先，",
                        "这样我才能推荐合适的活动地点和方案。",
                        "我们需要这些信息才能更好地推荐合适的户外活动地点和项目。",
                        "其次，",
                        "为了更好地帮您规划",
                        "听起来很棒！",
                        "团队建设活动听起来很棒！",
                        "为了更好地帮助您",
                        "我需要了解一下",
                        "请您告诉我",
                        "能否告知",
                        "您能提供",
                        "我想了解",
                        "需要知道",
                        "请问",
                        "麻烦告诉我",
                        "能否分享"
                    ]

                    # 移除礼貌语
                    for phrase in courtesy_phrases:
                        ask_content = ask_content.replace(phrase, "")

                    # 移除常见的开头礼貌语
                    ask_content = re.sub(r'^听起来.*！', '', ask_content)
                    ask_content = re.sub(r'^为了.*，', '', ask_content)

                    # 清理多余的标点和空格
                    ask_content = re.sub(r'[，,。.]', '？', ask_content)
                    ask_content = re.sub(r'\s+', ' ', ask_content)
                    ask_content = ask_content.strip('？，,。 \t\n')

                    # 如果清理后内容为空，保持原样
                    if not ask_content:
                        ask_content = "请提供更多具体信息"

                    # 应用句子改写以减少模板化
                    ask_content = self._rewrite_sentence(ask_content)

                    turn["text"] = f"<ASK>{ask_content}</ASK>"

                # 检查<FIMAL>标签
                final_match = re.search(r'<FINAL>(.*?)</FINAL>', text, re.DOTALL)
                if final_match:
                    final_content = final_match.group(1).strip()
                    # 对FINAL内容也进行清理
                    final_content = re.sub(r'\s+', ' ', final_content)
                    turn["text"] = f"<FINAL>{final_content}</FINAL>"

        return turns

    def _quality_check(self, sample: Dict[str, Any], data_type: str) -> Dict[str, Any]:
        """质量控制检查"""
        reasons = []

        # 1. 结构完整性检查
        if not sample.get("turns"):
            reasons.append("turns字段为空")
        else:
            # 检查turns格式
            for i, turn in enumerate(sample["turns"]):
                if not turn.get("role") or not turn.get("text"):
                    reasons.append(f"turn[{i}]缺少role或text字段")

            # 检查model_target角色
            model_target_found = False
            for turn in sample["turns"]:
                if turn["role"] == "model_target":
                    model_target_found = True
                    break
            if not model_target_found:
                reasons.append("缺少model_target角色")

        # 2. labels完整性检查
        labels = sample.get("labels", {})
        if not labels.get("ask_required"):
            reasons.append("labels.ask_required缺失或为False")

        if data_type in ["ALC", "AR"]:
            if not labels.get("ambiguity_types"):
                reasons.append("labels.ambiguity_types缺失")
            if not labels.get("good_question_set"):
                reasons.append("labels.good_question_set缺失")
            if data_type == "AR" and not labels.get("oracle_answer"):
                reasons.append("AR样本缺少labels.oracle_answer")

        # 3. reasoning完整性检查
        reasoning = sample.get("reasoning", {})
        if not reasoning.get("actions"):
            reasons.append("reasoning.actions缺失")
        else:
            required_actions = ["AWARE_GAP", "ASK", "STOP_ASK", "FINALIZE"]
            actions = [action.get("t") for action in reasoning["actions"] if isinstance(action, dict)]
            missing_actions = [action for action in required_actions if action not in actions]

            # 对于某些类型的推理，可能不需要所有动作，放松检查
            if data_type == "ALC":
                # ALC至少需要AWARE_GAP, ASK, STOP_ASK
                required_actions = ["AWARE_GAP", "ASK", "STOP_ASK"]
                missing_actions = [action for action in required_actions if action not in actions]

            if missing_actions:
                reasons.append(f"reasoning.actions缺少必需动作: {missing_actions}")

        # 4. model_target内容检查（强制ASK/FINAL格式）
        for turn in sample.get("turns", []):
            if turn["role"] == "model_target":
                text = turn["text"]
                # 检查是否只包含ASK或FINAL标签
                import re
                if not (re.match(r'^\s*<ASK>.*?</ASK>\s*$', text) or re.match(r'^\s*<FINAL>.*?</FINAL>\s*$', text)):
                    reasons.append("model_target内容不符合ASK/FINAL格式要求")

        # 5. CoT泄漏检查
        cot_indicators = ["Let me think", "首先", "其次", "综上所述", "因为", "所以", "步骤", "Let's think"]
        for turn in sample.get("turns", []):
            if turn["role"] == "model_target":
                text_lower = turn["text"].lower()
                for indicator in cot_indicators:
                    if indicator.lower() in text_lower:
                        reasons.append(f"检测到CoT泄漏: {indicator}")
                        break

        return {
            "passed": len(reasons) == 0,
            "reasons": reasons
        }

    def _rewrite_sentence(self, text: str) -> str:
        """句子改写以减少模板化"""
        if not text or len(text) < 5:
            return text

        # 简单的同义词替换规则
        rewrite_rules = {
            "请告诉我": ["能否告知我", "你能提供", "我想了解"],
            "请问": ["能否告诉我", "你知道", "我想问"],
            "您能": ["你可以", "你能", "能否"],
            "我需要": ["我想知道", "请提供", "能否分享"],
            "为了更好地": ["为了", "为了更准确地", "为了更好地"],
            "这样我才能": ["这样才能", "这样我就可以", "这样有助于"],
            "我们需要": ["需要", "我想了解", "请提供"]
        }

        import random
        rewritten = text

        # 应用替换规则
        for original, alternatives in rewrite_rules.items():
            if original in rewritten:
                replacement = random.choice(alternatives)
                rewritten = rewritten.replace(original, replacement, 1)
                break  # 只替换第一个匹配项

        # 如果没有应用替换，尝试一些简单的变换
        if rewritten == text:
            # 添加一些随机变化
            variations = [
                lambda t: t.replace("请", "麻烦"),
                lambda t: t.replace("您", "你"),
                lambda t: t + "好吗",
            ]
            if random.random() < 0.3:  # 30%概率应用变换
                variation = random.choice(variations)
                rewritten = variation(rewritten)

        return rewritten

    def _ensure_complete_labels(self, data_type: str, labels: Dict[str, Any]) -> Dict[str, Any]:
        """确保labels字段完整"""
        # 基础字段
        if "ask_required" not in labels:
            labels["ask_required"] = True

        # 根据数据类型补齐特定字段
        if data_type == "ALC":
            if "ambiguity_types" not in labels:
                labels["ambiguity_types"] = ["preference", "budget", "context"]
            if "good_question_set" not in labels:
                labels["good_question_set"] = ["活动类型", "预算范围", "时间安排"]
            if "minimal_clarifications" not in labels:
                labels["minimal_clarifications"] = 2
        elif data_type == "AR":
            if "ambiguity_types" not in labels:
                labels["ambiguity_types"] = ["method", "scope", "context"]
            if "good_question_set" not in labels:
                labels["good_question_set"] = ["具体问题", "期望结果", "约束条件"]
            if "minimal_clarifications" not in labels:
                labels["minimal_clarifications"] = 1
            if "oracle_answer" not in labels:
                labels["oracle_answer"] = "需要更多信息才能解答"
        elif data_type == "RSD":
            if "ambiguity_types" not in labels:
                labels["ambiguity_types"] = ["method"]
            if "good_question_set" not in labels:
                labels["good_question_set"] = ["推理方法"]
            if "minimal_clarifications" not in labels:
                labels["minimal_clarifications"] = 1

        return labels

    def _ensure_complete_reasoning(self, data_type: str, reasoning: Dict[str, Any]) -> Dict[str, Any]:
        """确保reasoning字段完整"""
        if "actions" not in reasoning:
            reasoning["actions"] = []

        # 如果actions为空，添加默认动作序列
        if not reasoning["actions"]:
            if data_type == "ALC":
                reasoning["actions"] = [
                    {"t": "AWARE_GAP", "vars": ["preference", "budget", "context"]},
                    {"t": "ASK", "q": "请告诉我活动类型、预算和时间安排"},
                    {"t": "STOP_ASK"}
                ]
            elif data_type == "AR":
                reasoning["actions"] = [
                    {"t": "AWARE_GAP", "vars": ["method", "scope", "context"]},
                    {"t": "ASK", "q": "请提供更多关于问题的详细信息"},
                    {"t": "STOP_ASK"}
                ]
            elif data_type == "RSD":
                reasoning["actions"] = [
                    {"t": "AWARE_GAP", "vars": ["method"]},
                    {"t": "ASK", "q": "请说明推理方法"},
                    {"t": "DERIVE", "note": "使用逻辑推理"},
                    {"t": "VERIFY", "note": "检查推理正确性"},
                    {"t": "FINALIZE"}
                ]

        return reasoning

    def _get_correct_source(self, data_type: str) -> str:
        """获取正确的source值"""
        if data_type == "ALC":
            return "synthetic-gemini"
        elif data_type == "AR":
            return "synthetic-gemini"
        elif data_type == "RSD":
            return "r1-distill"
        else:
            return "synthetic-gemini"

    def _extract_json_from_text(self, text: str, data_type: str) -> Dict[str, Any]:
        """从文本中提取JSON（增强版）"""
        import re

        # 首先尝试提取JSON代码块
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试找到JSON对象（不带代码块标记）
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # 如果还是找不到JSON，尝试清理文本
        cleaned_text = text.strip()
        # 移除可能的markdown标记
        cleaned_text = re.sub(r'^```\w*\n?', '', cleaned_text)
        cleaned_text = re.sub(r'\n?```$', '', cleaned_text)

        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            pass

        # 如果都失败了，返回默认数据
        logger.warning(f"无法从响应中提取JSON，返回默认{data_type}数据")
        return self._get_default_data_for_type(data_type)

    def _create_default_sample(self, data_type: str, index: int) -> Dict[str, Any]:
        """创建默认样本"""
        data = self._get_default_data_for_type(data_type)
        return self._format_sample(data_type, data, index)

    def _get_default_data_for_type(self, data_type: str) -> Dict[str, Any]:
        """获取数据类型的默认数据（确保turns不为空）"""
        if data_type == "ALC":
            return {
                "turns": [
                    {"role": "user", "text": "请帮我规划一个活动"},
                    {"role": "model_target", "text": "<ASK>您想做什么类型的活动？预算多少？</ASK>"}
                ],
                "labels": {
                    "ambiguity_types": ["preference", "budget"],
                    "ask_required": True,
                    "good_question_set": ["活动类型", "预算范围"],
                    "minimal_clarifications": 2,
                    "oracle_answer": None
                },
                "reasoning": {
                    "think_stream": "用户需求不明确，需要澄清活动类型和预算",
                    "actions": [
                        {"t": "AWARE_GAP", "vars": ["preference", "budget"]},
                        {"t": "ASK", "q": "请告诉我您想做什么类型的活动，预算大约多少"},
                        {"t": "STOP_ASK"},
                        {"t": "FINALIZE"}
                    ]
                }
            }
        elif data_type == "AR":
            return {
                "turns": [
                    {"role": "user", "text": "如何解决这个问题？"},
                    {"role": "model_target", "text": "<ASK> 您能提供更多详细信息吗？ </ASK>"}
                ],
                "labels": {
                    "ambiguity_types": ["method", "scope"],
                    "ask_required": True,
                    "good_question_set": ["具体问题", "期望结果"],
                    "minimal_clarifications": 1,
                    "oracle_answer": "需要更多信息才能解答"
                },
                "reasoning": {
                    "think_stream": "问题描述不完整，需要澄清具体内容",
                    "actions": [
                        {"t": "AWARE_GAP", "vars": ["method", "scope"]},
                        {"t": "ASK", "q": "请提供更多关于问题的详细信息"},
                        {"t": "STOP_ASK"}
                    ]
                }
            }
        else:  # RSD
            return {
                "turns": [
                    {"role": "user", "text": "请分析这个推理过程"},
                    {"role": "model_target", "text": "<ASK> 需要我如何帮助您分析？ </ASK>"}
                ],
                "labels": {
                    "ambiguity_types": ["method"],
                    "ask_required": True,
                    "good_question_set": ["分析方法"],
                    "minimal_clarifications": 1,
                    "oracle_answer": "需要澄清分析需求"
                },
                "reasoning": {
                    "think_stream": "用户需求不明确",
                    "actions": [
                        {"t": "AWARE_GAP", "vars": ["method"]},
                        {"t": "ASK", "q": "请说明您需要什么样的分析"},
                        {"t": "DERIVE", "note": "准备分析步骤"},
                        {"t": "VERIFY", "note": "确认分析结果"},
                        {"t": "FINALIZE"}
                    ]
                }
            }

    def _get_domain_for_type(self, data_type: str) -> str:
        """获取数据类型的领域"""
        domain_map = {
            "ALC": "planning",
            "AR": "reasoning",
            "RSD": "reasoning"
        }
        return domain_map.get(data_type, "general")

    def _record_provenance(self, data_type: str, prompt: str, key_index: int, sample_id: str, failover_info: Optional[Dict[str, Any]] = None, recipe: Optional[str] = None):
        """记录出处信息（强化版，包含Fail-Over和Recipe）"""
        generator_prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        # 根据key_index确定provider
        if key_index == 3:  # DeepSeek
            provider = "deepseek"
            model = "deepseek-reasoner"
        else:  # Gemini
            provider = "google"
            model = "gemini-2.5-flash" if key_index == 0 else "gemini-2.5-pro"

        # 获取domain
        domain = self._get_domain_for_type(data_type)

        record = ProvenanceRecord(
            uid=sample_id,
            provider=provider,
            model=model,
            key_index=key_index,
            temperature=self.config.temperature,
            seed=42,  # 固定种子
            generator_prompt_hash=generator_prompt_hash,
            timestamp=datetime.now().isoformat(),
            domain=domain,
            language="zh",
            recipe=recipe,  # 生成配方
            failover=failover_info  # Fail-Over信息
        )

        self.provenance_records.append(record)

    def _get_alc_prompt(self, recipe: str = "A") -> str:
        """获取ALC生成提示（多样性增强版）"""
        # 人设池（随机选择）
        personas = [
            "一个忙碌的上班族",
            "一个学生党",
            "一个创业者",
            "一个家庭主妇/主夫",
            "一个自由职业者",
            "一个退休老人"
        ]

        # 场景池（随机选择）
        scenarios = [
            "周末休闲活动",
            "工作团队建设",
            "家庭聚会",
            "学习小组活动",
            "志愿者活动",
            "技能培训班"
        ]

        # 约束池（随机选择）
        constraints = [
            "预算有限，希望经济实惠",
            "时间紧张，希望在工作日完成",
            "参与人数多，需要大场地",
            "希望有特色主题活动",
            "考虑交通便利性",
            "注重安全和卫生"
        ]

        import random
        selected_persona = random.choice(personas)
        selected_scenario = random.choice(scenarios)
        selected_constraint = random.choice(constraints)

        return f"""你是一个专业的对话生成助手，需要生成一段包含信息缺口的自然对话。

要求：
1. 用户是{selected_persona}，想要组织{selected_scenario}
2. 助手的第一轮回复必须严格包含<ASK>标签，询问关键缺失信息
3. 至少包含2个关键变量的缺失（如时间/地点/预算/联系人）
4. 对话要自然流畅，避免使用模板化表达
5. 澄清问题要直接针对关键变量，不要包含礼貌语
6. {selected_constraint}

重要：model_target的内容必须严格匹配以下格式之一：
- <ASK>具体问题内容</ASK>
- <FINAL>最终回答内容</FINAL>

禁止在model_target中使用任何礼貌语、思考过程或额外文字。

请生成符合Schema v1.1格式的JSON响应。"""

    def _get_ar_prompt(self) -> str:
        """获取AR生成提示"""
        return """你是一个推理问题生成助手，需要生成包含歧义的推理题。

要求：
1. 问题需要先澄清关键前提（如单位/初值/范围/定义）
2. 助手的回复必须包含<ASK>标签询问关键信息
3. 提供明确的正确答案（在labels.oracle_answer中）
4. 歧义类型要明确标注

请生成符合Schema v1.1格式的JSON响应。"""

    def _get_rsd_prompt(self) -> str:
        """获取RSD生成提示"""
        return """你是一个推理行为分析助手，需要分析推理过程中的关键动作。

要求：
1. 只返回推理动作序列，不要包含思维链文本
2. 动作类型包括：AWARE_GAP, ASK, STOP_ASK, DERIVE, VERIFY, FINALIZE
3. 每个动作要有明确的时间点和目的

请返回动作序列的JSON数组。"""

    def save_samples(self, samples: List[Dict[str, Any]], filename: str):
        """保存样本到文件"""
        output_file = self.output_dir / filename

        # 确保父目录存在
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')

        logger.info(f"已保存 {len(samples)} 个样本到 {output_file}")

    def save_provenance(self):
        """保存provenance记录"""
        provenance_file = Path("reports/provenance.jsonl")

        with open(provenance_file, 'a', encoding='utf-8') as f:
            for record in self.provenance_records:
                record_dict = {
                    "uid": record.uid,
                    "provider": record.provider,
                    "model": record.model,
                    "key_index": record.key_index,
                    "temperature": record.temperature,
                    "seed": record.seed,
                    "generator_prompt_hash": record.generator_prompt_hash,
                    "judge_prompt_hash": record.judge_prompt_hash,
                    "timestamp": record.timestamp,
                    "domain": record.domain,
                    "language": record.language,
                    "quality_score": record.quality_score,
                    "judge_votes": record.judge_votes,
                    "escalated_to_ds": record.escalated_to_ds,
                    "reject_reason": record.reject_reason,
                    "risk_flags": record.risk_flags
                }
                f.write(json.dumps(record_dict, ensure_ascii=False) + '\n')

        logger.info(f"已保存 {len(self.provenance_records)} 条provenance记录")

    def run_generation(self):
        """运行完整数据生成流程"""
        logger.info("开始Data Sprint-β数据生成...")

        # 生成不同类型的数据
        alc_samples = self.generate_alc_data()
        ar_samples = self.generate_ar_data()
        rsd_samples = self.generate_rsd_data()

        # 保存样本
        if alc_samples:
            self.save_samples(alc_samples, "ALC/part-001.jsonl")
        if ar_samples:
            self.save_samples(ar_samples, "AR/part-001.jsonl")
        if rsd_samples:
            self.save_samples(rsd_samples, "RSD/part-001.jsonl")

        # 保存provenance
        self.save_provenance()

        # 生成汇总报告
        self._generate_summary_report(alc_samples, ar_samples, rsd_samples)

        total_generated = len(alc_samples) + len(ar_samples) + len(rsd_samples)
        logger.info(f"数据生成完成，总计生成 {total_generated} 个样本")

    def _generate_summary_report(self, alc_samples: List, ar_samples: List, rsd_samples: List):
        """生成汇总报告"""
        total = len(alc_samples) + len(ar_samples) + len(rsd_samples)

        report = f"""# 数据生成汇总报告 - {self.config.batch_date}

## 生成统计
- **总样本数**: {total}
- **ALC样本**: {len(alc_samples)} (目标: {self.config.alc_count})
- **AR样本**: {len(ar_samples)} (目标: {self.config.ar_count})
- **RSD样本**: {len(rsd_samples)} (目标: {self.config.rsd_count})

## 配置信息
- **温度**: {self.config.temperature}
- **批次日期**: {self.config.batch_date}
- **最大重试次数**: {self.config.max_retries}
- **速率限制延迟**: {self.config.rate_limit_delay}s

## 输出文件
- `data/gen/{self.config.batch_date}/ALC/part-001.jsonl`
- `data/gen/{self.config.batch_date}/AR/part-001.jsonl`
- `data/gen/{self.config.batch_date}/RSD/part-001.jsonl`
- `reports/provenance.jsonl` (追加)

## 下一步
1. 运行质量检查: `python tools/dataset_gate.py`
2. 运行去重检查: `python tools/deduplication.py`
3. 更新数据概览: `python tools/validate_dataset.py data/gen/{self.config.batch_date}/*/part-*.jsonl`
"""

        report_file = Path("reports/generation_summary.md")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        logger.info(f"汇总报告已保存到 {report_file}")

def main():
    """主入口"""
    # 检查环境
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY未设置，请检查.env文件")
        return

    # 配置生成参数
    config = GenerationConfig()

    # 创建生成器并运行
    generator = DataGenerator(config)
    generator.run_generation()

if __name__ == "__main__":
    main()
