#!/usr/bin/env python3
"""Scan for Chain-of-Thought Leakage in Dataset

扫描数据集中是否存在思维链泄漏到对话历史的现象。
检查model_target字段中是否包含明显的CoT痕迹。
"""

import json
import sys
import re
from pathlib import Path
from typing import List, Dict, Any

# CoT泄漏检测模式
COT_INDICATORS = [
    # 中文推理关键词
    "首先", "其次", "然后", "最后", "接下来",
    "因为", "所以", "因此", "由于", "根据",
    "分析", "考虑", "思考", "推理", "判断",
    "步骤", "过程", "阶段", "环节", "方法",
    "综上所述", "总的来说", "也就是说", "换句话说",
    "让我想想", "我需要", "应该", "可以",

    # 英文推理关键词
    "first", "second", "then", "finally", "next",
    "because", "so", "therefore", "since", "according to",
    "analyze", "consider", "think", "reason", "judge",
    "step", "process", "stage", "phase", "method",
    "in conclusion", "overall", "in other words",
    "let me think", "I need", "should", "can",

    # 特定CoT模式
    "Let's think", "Chain-of-Thought", "CoT",
    "Step by step", "Break it down",
    "推理过程", "思考过程", "分析过程", "决策过程",
    "让我来分析", "我来思考", "需要考虑",
]

# 允许在<think>标签内的关键词（不计为泄漏）
ALLOWED_IN_THINK = [
    "首先", "其次", "然后", "最后", "因为", "所以", "因此",
    "分析", "考虑", "思考", "推理", "步骤", "过程",
    "Let's think", "let me think", "I need to think",
]

class CoTLeakageScanner:
    """思维链泄漏扫描器"""

    def __init__(self):
        self.leakages = []
        self.total_scanned = 0

    def scan_file(self, file_path: str) -> List[Dict[str, Any]]:
        """扫描单个文件"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        leakages = []

        with open(path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    leakage = self._scan_sample(data, line_num, file_path)
                    if leakage:
                        leakages.extend(leakage)
                except json.JSONDecodeError:
                    continue  # 跳过无效JSON行

        self.leakages.extend(leakages)
        self.total_scanned += 1
        return leakages

    def scan_directory(self, dir_path: str) -> List[Dict[str, Any]]:
        """扫描目录下的所有JSONL文件"""
        path = Path(dir_path)
        if not path.exists():
            raise FileNotFoundError(f"目录不存在: {dir_path}")

        all_leakages = []

        # 递归查找所有.jsonl文件
        for jsonl_file in path.rglob("*.jsonl"):
            try:
                leakages = self.scan_file(str(jsonl_file))
                all_leakages.extend(leakages)
            except Exception as e:
                print(f"⚠️  扫描文件失败 {jsonl_file}: {e}", file=sys.stderr)

        return all_leakages

    def _scan_sample(self, data: Dict[str, Any], line_num: int, file_path: str) -> List[Dict[str, Any]]:
        """扫描单个样本"""
        leakages = []
        sample_id = data.get("id", f"line_{line_num}")

        # 扫描turns中的model_target
        turns = data.get("turns", [])
        for turn_idx, turn in enumerate(turns):
            if turn.get("role") == "model_target":
                text = turn.get("text", "")
                leakage_info = self._detect_leakage(text, sample_id, turn_idx, file_path, line_num)
                if leakage_info:
                    leakages.append(leakage_info)

        return leakages

    def _detect_leakage(self, text: str, sample_id: str, turn_idx: int,
                        file_path: str, line_num: int) -> Dict[str, Any]:
        """检测文本中的思维链泄漏"""
        if not text:
            return None

        text_lower = text.lower()

        # 提取think内容（如果有）
        think_content = ""
        if "<think>" in text and "</think>" in text:
            think_match = re.search(r'<think>(.*?)</think>', text, re.DOTALL | re.IGNORECASE)
            if think_match:
                think_content = think_match.group(1).lower()

        # 检查每个CoT指标
        for indicator in COT_INDICATORS:
            indicator_lower = indicator.lower()

            # 如果指标出现在文本中
            if indicator_lower in text_lower:
                # 如果在think标签内，且是允许的关键词，则跳过
                if (indicator in ALLOWED_IN_THINK and
                    indicator_lower in think_content):
                    continue

                # 检查是否在think标签外出现
                if "<think>" in text and "</think>" in text:
                    # 有think标签，检查泄漏内容是否在标签外
                    think_start = text.lower().find("<think>")
                    think_end = text.lower().find("</think>") + len("</think>")

                    # 在标签前的内容
                    before_think = text[:think_start]
                    # 在标签后的内容
                    after_think = text[think_end:]

                    if (indicator_lower in before_think.lower() or
                        indicator_lower in after_think.lower()):
                        return {
                            "sample_id": sample_id,
                            "file_path": file_path,
                            "line_num": line_num,
                            "turn_idx": turn_idx,
                            "indicator": indicator,
                            "context": text[:100] + "..." if len(text) > 100 else text,
                            "severity": "high"
                        }
                else:
                    # 没有think标签，直接算泄漏
                    return {
                        "sample_id": sample_id,
                        "file_path": file_path,
                        "line_num": line_num,
                        "turn_idx": turn_idx,
                        "indicator": indicator,
                        "context": text[:100] + "..." if len(text) > 100 else text,
                        "severity": "high"
                    }

        return None

    def get_summary_report(self) -> Dict[str, Any]:
        """获取汇总报告"""
        high_severity = [l for l in self.leakages if l["severity"] == "high"]

        # 按文件分组统计
        file_stats = {}
        for leakage in self.leakages:
            file_path = leakage["file_path"]
            if file_path not in file_stats:
                file_stats[file_path] = 0
            file_stats[file_path] += 1

        # 按指标分组统计
        indicator_stats = {}
        for leakage in self.leakages:
            indicator = leakage["indicator"]
            if indicator not in indicator_stats:
                indicator_stats[indicator] = 0
            indicator_stats[indicator] += 1

        return {
            "total_scanned_files": self.total_scanned,
            "total_leakages": len(self.leakages),
            "high_severity_leakages": len(high_severity),
            "file_stats": file_stats,
            "indicator_stats": indicator_stats,
            "leakages": self.leakages[:20]  # 只返回前20个详细信息
        }

def main():
    if len(sys.argv) != 2:
        print("用法: python tools/scan_for_cot_leakage.py <文件或目录路径>")
        print("示例:")
        print("  python tools/scan_for_cot_leakage.py data/seed/ALC/seed.jsonl")
        print("  python tools/scan_for_cot_leakage.py data/seed/")
        sys.exit(1)

    target_path = sys.argv[1]
    path = Path(target_path)

    scanner = CoTLeakageScanner()

    try:
        if path.is_file():
            leakages = scanner.scan_file(target_path)
        elif path.is_dir():
            leakages = scanner.scan_directory(target_path)
        else:
            print(f"❌ 路径不存在: {target_path}")
            sys.exit(1)

        report = scanner.get_summary_report()

        # 输出报告
        print("🔍 CoT泄漏扫描报告")
        print(f"📁 扫描文件数: {report['total_scanned_files']}")
        print(f"🚨 总泄漏数: {report['total_leakages']}")
        print(f"⚠️  高严重度泄漏: {report['high_severity_leakages']}")
        print()

        if report["file_stats"]:
            print("📊 按文件统计:")
            for file_path, count in sorted(report["file_stats"].items()):
                print(f"  {file_path}: {count} 个泄漏")
            print()

        if report["indicator_stats"]:
            print("🔍 常见泄漏指标:")
            for indicator, count in sorted(report["indicator_stats"].items(),
                                          key=lambda x: x[1], reverse=True)[:10]:
                print(f"  '{indicator}': {count} 次")
            print()

        if report["leakages"]:
            print("📋 泄漏详情 (前5个):")
            for i, leakage in enumerate(report["leakages"][:5], 1):
                print(f"  {i}. {leakage['sample_id']} ({leakage['file_path']}:{leakage['line_num']})")
                print(f"     泄漏指标: '{leakage['indicator']}'")
                print(f"     上下文: {leakage['context']}")
                print()

        # 根据泄漏情况设置退出码
        if report["high_severity_leakages"] > 0:
            print("❌ 发现高严重度CoT泄漏，建议修复后重新提交")
            sys.exit(1)
        else:
            print("✅ 未发现CoT泄漏")

    except Exception as e:
        print(f"❌ 扫描失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
