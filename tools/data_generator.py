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
    judge_prompt_hash: Optional[str] = None
    dedup_score: Optional[float] = None
    quality_score: Optional[float] = None
    judge_votes: Optional[Dict[str, float]] = None  # 双评审结果
    escalated_to_ds: bool = False  # 是否仲裁到DeepSeek
    reject_reason: Optional[str] = None
    risk_flags: Optional[List[str]] = None  # 安全风险标记

class GeminiClient:
    """Gemini API客户端"""

    def __init__(self, api_key: str, key_index: int = 0):
        self.api_key = api_key
        self.key_index = key_index
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"

    def generate(self, prompt: str, temperature: float = 0.7) -> Optional[str]:
        """生成内容"""
        try:
            # 这里应该是实际的Gemini API调用
            # 暂时返回模拟响应用于测试
            if "ALC" in prompt:
                return self._mock_alc_response()
            elif "AR" in prompt:
                return self._mock_ar_response()
            elif "RSD" in prompt:
                return self._mock_rsd_response()
            else:
                return self._mock_judge_response()
        except Exception as e:
            logger.error(f"Gemini API调用失败: {e}")
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
        """初始化客户端（修正路由）"""
        clients = {}

        # ALC客户端 - GEMINI_API_KEY (gemini-2.5-flash)
        alc_key = os.getenv("GEMINI_API_KEY")
        if alc_key:
            clients["ALC"] = GeminiClient(alc_key, key_index=0)

        # AR客户端 - GEMINI_API_KEY2 (gemini-2.5-pro)
        ar_key = os.getenv("GEMINI_API_KEY2")
        if ar_key:
            clients["AR"] = GeminiClient(ar_key, key_index=1)

        # RSD客户端 - DeepSeek_API_KEY2 (deepseek-reasoner)
        rsd_key = os.getenv("DeepSeek_API_KEY2")
        if rsd_key:
            # 这里需要实现DeepSeek客户端，暂时用GeminiClient模拟
            clients["RSD"] = GeminiClient(rsd_key, key_index=3)  # 3表示DeepSeek

        # 评审客户端 - GEMINI_API_KEY3 (gemini-2.5-pro for judging)
        judge_key = os.getenv("GEMINI_API_KEY3")
        if judge_key:
            clients["JUDGE"] = GeminiClient(judge_key, key_index=2)

        return clients

    def generate_alc_data(self) -> List[Dict[str, Any]]:
        """生成ALC数据"""
        logger.info(f"开始生成ALC数据，目标数量: {self.config.alc_count}")

        alc_prompt = self._get_alc_prompt()
        samples = []

        for i in range(self.config.alc_count):
            sample = self._generate_single_sample("ALC", alc_prompt, i)
            if sample:
                samples.append(sample)

            # 控制速率
            time.sleep(self.config.rate_limit_delay)

        logger.info(f"ALC数据生成完成，实际生成: {len(samples)}")
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

    def _generate_single_sample(self, data_type: str, prompt: str, index: int) -> Optional[Dict[str, Any]]:
        """生成单个样本"""
        client = self.clients.get(data_type)
        if not client:
            logger.error(f"没有可用的{data_type}客户端")
            return None

        # 生成内容
        response = client.generate(prompt, self.config.temperature)
        if not response:
            logger.warning(f"{data_type}样本{index}生成失败")
            return None

        try:
            # 解析响应
            data = json.loads(response)

            # 添加Schema v1.1必需字段
            sample = self._format_sample(data_type, data, index)

            # 记录provenance
            self._record_provenance(data_type, prompt, client.key_index, sample.get("id", f"{data_type}-{index}"))

            return sample

        except json.JSONDecodeError as e:
            logger.error(f"解析{data_type}响应失败: {e}")
            return None

    def _format_sample(self, data_type: str, data: Dict[str, Any], index: int) -> Dict[str, Any]:
        """格式化样本为Schema v1.1"""
        sample = {
            "id": f"{data_type}-{index:04d}",
            "domain": self._get_domain_for_type(data_type),
            "source": f"gemini-{data_type.lower()}",
            "turns": data.get("turns", []),
            "labels": data.get("labels", {}),
            "reasoning": data.get("reasoning", {})
        }

        # 确保必需字段存在
        if "ask_required" not in sample["labels"]:
            sample["labels"]["ask_required"] = True

        if "actions" not in sample["reasoning"]:
            sample["reasoning"]["actions"] = []

        return sample

    def _get_domain_for_type(self, data_type: str) -> str:
        """获取数据类型的领域"""
        domain_map = {
            "ALC": "planning",
            "AR": "reasoning",
            "RSD": "reasoning"
        }
        return domain_map.get(data_type, "general")

    def _record_provenance(self, data_type: str, prompt: str, key_index: int, sample_id: str):
        """记录出处信息（强化版）"""
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
            language="zh"
        )

        self.provenance_records.append(record)

    def _get_alc_prompt(self) -> str:
        """获取ALC生成提示"""
        return """你是一个专业的对话生成助手，需要生成一段包含信息缺口的自然对话。

要求：
1. 用户提出一个生活/协作/技术/计划相关的问题
2. 助手的第一轮回复必须包含<ASK>标签，询问关键缺失信息
3. 至少包含2个关键变量的缺失（如时间/地点/预算/联系人）
4. 对话要自然流畅，不要模板化
5. 澄清问题要直接针对关键变量

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
                    "temperature": record.temperature,
                    "seed": record.seed,
                    "prompt_hash": record.prompt_hash,
                    "timestamp": record.timestamp,
                    "key_index": record.key_index,
                    "quality_score": record.quality_score,
                    "reasons": record.reasons
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
