#!/usr/bin/env python3
"""Quality Reviewer for Generated Data

使用Gemini评审生成的样本质量，计算Clarification-F1和InfoGain分数。
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from tools.data_generator import GeminiClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class QualityScore:
    """质量评分"""
    clarification_f1: float
    info_gain: float
    overall_score: float
    reasons: str
    ask_required: bool
    ambiguity_types: List[str]
    good_question_set: List[str]

class QualityReviewer:
    """质量评审器"""

    def __init__(self):
        self.client = self._init_client()

    def _init_client(self) -> Optional[GeminiClient]:
        """初始化评审客户端"""
        api_key = os.getenv("GEMINI_API_KEY3")  # 使用第三个key进行评审
        if api_key:
            return GeminiClient(api_key, key_index=2)
        return None

    def review_sample(self, sample: Dict[str, Any]) -> Optional[QualityScore]:
        """评审单个样本"""
        if not self.client:
            logger.error("评审客户端未初始化")
            return None

        # 构建评审提示
        prompt = self._build_review_prompt(sample)

        # 调用Gemini进行评审
        response = self.client.generate(prompt, temperature=0.1)  # 低温度保证一致性

        if not response:
            return None

        try:
            # 解析评审结果
            review_data = json.loads(response)
            return self._parse_review_result(review_data)
        except json.JSONDecodeError:
            logger.error(f"解析评审响应失败: {response}")
            return None

    def _build_review_prompt(self, sample: Dict[str, Any]) -> str:
        """构建评审提示"""
        turns_text = ""
        for turn in sample.get("turns", []):
            role = turn.get("role", "")
            text = turn.get("text", "")
            turns_text += f"{role}: {text}\n"

        return f"""你是一个专业的数据质量评审员，请评审以下样本的质量：

对话内容：
{turns_text}

当前标签：
{sample.get("labels", {})}

请从以下维度进行评审：

1. **Clarification-F1**: 澄清问题的准确性和完整性
   - 问题是否直接针对关键信息缺口？
   - 是否覆盖了所有主要歧义点？
   - 问题表述是否清晰准确？

2. **InfoGain**: 信息增益评估
   - 澄清后是否能显著减少答案空间？
   - 问题是否有足够的区分度？
   - 是否避免了冗余或无关问题？

3. **ASK触发准确度**: 是否需要澄清
   - 这个查询是否真的需要澄清？
   - 澄清是否是最佳响应策略？

请返回JSON格式的评审结果：
{{
  "clarification_f1": 0.0-1.0,
  "info_gain": 0.0-1.0,
  "overall_score": 0.0-1.0,
  "reasons": "详细评审理由",
  "ask_required": true/false,
  "ambiguity_types": ["type1", "type2"],
  "good_question_set": ["问题1", "问题2"]
}}"""

    def _parse_review_result(self, review_data: Dict[str, Any]) -> QualityScore:
        """解析评审结果"""
        return QualityScore(
            clarification_f1=review_data.get("clarification_f1", 0.0),
            info_gain=review_data.get("info_gain", 0.0),
            overall_score=review_data.get("overall_score", 0.0),
            reasons=review_data.get("reasons", ""),
            ask_required=review_data.get("ask_required", False),
            ambiguity_types=review_data.get("ambiguity_types", []),
            good_question_set=review_data.get("good_question_set", [])
        )

    def review_batch(self, samples: List[Dict[str, Any]], batch_size: int = 10) -> List[Tuple[Dict[str, Any], Optional[QualityScore]]]:
        """批量评审样本"""
        results = []

        for i in range(0, len(samples), batch_size):
            batch = samples[i:i+batch_size]
            logger.info(f"评审批次 {i//batch_size + 1}: 处理 {len(batch)} 个样本")

            for sample in batch:
                score = self.review_sample(sample)
                results.append((sample, score))

                # 避免API限速
                import time
                time.sleep(0.5)

        return results

class QualityFilter:
    """质量过滤器"""

    def __init__(self, min_score: float = 0.7, min_f1: float = 0.6):
        self.min_score = min_score
        self.min_f1 = min_f1

    def filter_samples(self, reviewed_samples: List[Tuple[Dict[str, Any], Optional[QualityScore]]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """过滤样本"""
        passed = []
        failed = []

        for sample, score in reviewed_samples:
            if score and score.overall_score >= self.min_score and score.clarification_f1 >= self.min_f1:
                # 更新样本标签
                if "labels" not in sample:
                    sample["labels"] = {}
                sample["labels"]["quality_score"] = score.overall_score
                sample["labels"]["review_reasons"] = score.reasons
                passed.append(sample)
            else:
                failed.append(sample)

        return passed, failed

class QualityPipeline:
    """质量处理流水线"""

    def __init__(self):
        self.reviewer = QualityReviewer()
        self.filter = QualityFilter()

    def process_directory(self, input_dir: str, output_dir: str = None) -> Dict[str, Any]:
        """处理目录中的样本"""
        input_path = Path(input_dir)
        samples = []

        # 加载所有样本
        for jsonl_file in input_path.rglob("*.jsonl"):
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            samples.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

        logger.info(f"加载了 {len(samples)} 个样本进行质量评审")

        # 批量评审
        reviewed_results = self.reviewer.review_batch(samples)

        # 过滤样本
        passed_samples, failed_samples = self.filter.filter_samples(reviewed_results)

        # 保存结果
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # 保存合格样本
            passed_file = output_path / "quality_passed.jsonl"
            with open(passed_file, 'w', encoding='utf-8') as f:
                for sample in passed_samples:
                    f.write(json.dumps(sample, ensure_ascii=False) + '\n')

            # 保存不合格样本
            failed_file = output_path / "quality_failed.jsonl"
            with open(failed_file, 'w', encoding='utf-8') as f:
                for sample in failed_samples:
                    f.write(json.dumps(sample, ensure_ascii=False) + '\n')

        # 生成统计报告
        stats = self._generate_stats(reviewed_results, passed_samples, failed_samples)
        report = self._generate_report(stats)

        return {
            "stats": stats,
            "report": report,
            "passed_samples": passed_samples,
            "failed_samples": failed_samples
        }

    def _generate_stats(self, reviewed_results: List, passed_samples: List, failed_samples: List) -> Dict[str, Any]:
        """生成统计信息"""
        total_reviewed = len(reviewed_results)
        total_passed = len(passed_samples)
        total_failed = len(failed_samples)

        pass_rate = (total_passed / total_reviewed) * 100 if total_reviewed > 0 else 0

        # 计算平均分数
        scores = [score for _, score in reviewed_results if score]
        avg_score = sum(s.overall_score for s in scores) / len(scores) if scores else 0
        avg_f1 = sum(s.clarification_f1 for s in scores) / len(scores) if scores else 0
        avg_info_gain = sum(s.info_gain for s in scores) / len(scores) if scores else 0

        return {
            "total_reviewed": total_reviewed,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "pass_rate": pass_rate,
            "avg_overall_score": avg_score,
            "avg_clarification_f1": avg_f1,
            "avg_info_gain": avg_info_gain
        }

    def _generate_report(self, stats: Dict[str, Any]) -> str:
        """生成质量报告"""
        report = f"""# 数据质量评审报告

## 评审统计
- **评审样本数**: {stats["total_reviewed"]}
- **合格样本数**: {stats["total_passed"]}
- **不合格样本数**: {stats["total_failed"]}
- **合格率**: {stats["pass_rate"]:.2f}%

## 质量指标
- **平均总体得分**: {stats["avg_overall_score"]:.3f}
- **平均Clarification-F1**: {stats["avg_clarification_f1"]:.3f}
- **平均InfoGain**: {stats["avg_info_gain"]:.3f}

## 评审标准
- **最低总体得分**: {self.filter.min_score}
- **最低Clarification-F1**: {self.filter.min_f1}

## 评审维度

### Clarification-F1 (澄清准确性)
- 评估澄清问题的准确性和完整性
- 检查是否直接针对关键信息缺口
- 验证问题覆盖范围是否完整

### InfoGain (信息增益)
- 评估澄清后的信息增益程度
- 检查问题是否有足够的区分度
- 验证是否避免了冗余问题

### ASK触发准确度
- 判断是否真的需要澄清
- 评估澄清是否是最佳响应策略
- 检查歧义类型的正确标注

## 建议

根据评审结果：
- 合格率 {stats["pass_rate"]:.1f}% {'良好' if stats["pass_rate"] >= 80 else '需要改进'}
- 平均得分 {stats["avg_overall_score"]:.2f} {'达标' if stats["avg_overall_score"] >= 0.7 else '偏低'}

如合格率低于80%，建议：
1. 检查生成提示的质量
2. 调整澄清问题的生成策略
3. 改进歧义类型的识别
"""

        return report

def main():
    """主入口"""
    import sys

    if len(sys.argv) < 2:
        print("用法: python tools/quality_reviewer.py <输入目录> [输出目录]")
        print("示例:")
        print("  python tools/quality_reviewer.py data/gen/2025-09-03/")
        print("  python tools/quality_reviewer.py data/gen/2025-09-03/ data/gen/2025-09-03/reviewed/")
        sys.exit(1)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    # 检查评审客户端
    if not os.getenv("GEMINI_API_KEY3"):
        logger.error("GEMINI_API_KEY3未设置，无法进行质量评审")
        sys.exit(1)

    pipeline = QualityPipeline()
    result = pipeline.process_directory(input_dir, output_dir)

    # 保存报告
    report_file = Path("reports/quality_review_report.md")
    report_file.parent.mkdir(parents=True, exist_ok=True)

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(result["report"])

    print("\n质量评审完成！")
    print(f"评审样本: {result['stats']['total_reviewed']}")
    print(f"合格样本: {result['stats']['total_passed']}")
    print(f"合格率: {result['stats']['pass_rate']:.2f}%")
    print(f"平均得分: {result['stats']['avg_overall_score']:.3f}")
    print(f"报告已保存: {report_file}")

    if output_dir:
        print(f"结果已保存到: {output_dir}")

if __name__ == "__main__":
    main()
