#!/usr/bin/env python3
"""Dataset Gate - 数据就绪度检查

验证数据集是否满足训练要求：
1. 结构合法性检查
2. CoT泄漏检查
3. 规模阈值检查
4. 生成数据概览报告
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# 导入现有的工具
try:
    sys.path.append(str(Path(__file__).parent.parent))
    from src.data.loader import DataLoader, Sample
    from tools.scan_for_cot_leakage import CoTLeakageScanner
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)

class DatasetGate:
    """数据集守卫"""

    def __init__(self, min_samples: int = 8):
        self.min_samples = min_samples
        self.check_time = datetime.now()
        self.stats = {}
        self.errors = []

    def check_seed_data(self) -> bool:
        """检查种子数据"""
        print("🔍 开始数据集就绪度检查...")

        seed_dirs = [
            "data/seed/ALC",
            "data/seed/AR"
        ]

        total_samples = 0
        all_valid = True

        for seed_dir in seed_dirs:
            dir_path = Path(seed_dir)
            if not dir_path.exists():
                self.errors.append(f"种子数据目录不存在: {seed_dir}")
                all_valid = False
                continue

            jsonl_files = list(dir_path.glob("*.jsonl"))
            if not jsonl_files:
                self.errors.append(f"种子数据目录为空: {seed_dir}")
                all_valid = False
                continue

            for jsonl_file in jsonl_files:
                print(f"📄 检查文件: {jsonl_file}")

                # 结构合法性检查
                if not self._check_structure_validity(str(jsonl_file)):
                    all_valid = False

                # CoT泄漏检查
                if not self._check_cot_leakage(str(jsonl_file)):
                    all_valid = False

                # 统计样本数
                sample_count = self._count_samples(str(jsonl_file))
                total_samples += sample_count
                self.stats[f"{seed_dir}/{jsonl_file.name}"] = sample_count

        # 规模阈值检查
        if total_samples < self.min_samples:
            self.errors.append(f"样本总数不足: {total_samples} < {self.min_samples}")
            all_valid = False

        self.stats["total_samples"] = total_samples

        if all_valid:
            print(f"✅ 数据集检查通过 (共 {total_samples} 个样本)")
        else:
            print(f"❌ 数据集检查失败")
            for error in self.errors:
                print(f"   - {error}")

        return all_valid

    def _check_structure_validity(self, file_path: str) -> bool:
        """检查数据结构合法性"""
        try:
            loader = DataLoader(strict_mode=False)
            samples = list(loader.load_jsonl(file_path))
            validation_report = loader.get_validation_report()

            if validation_report["error_count"] > 0:
                self.errors.append(f"结构错误 ({file_path}): {validation_report['error_count']} 个错误")
                return False

            return True

        except Exception as e:
            self.errors.append(f"结构检查失败 ({file_path}): {e}")
            return False

    def _check_cot_leakage(self, file_path: str) -> bool:
        """检查CoT泄漏"""
        try:
            scanner = CoTLeakageScanner()
            leakages = scanner.scan_file(file_path)

            if leakages:
                self.errors.append(f"CoT泄漏检测 ({file_path}): {len(leakages)} 个泄漏")
                return False

            return True

        except Exception as e:
            self.errors.append(f"CoT泄漏检查失败 ({file_path}): {e}")
            return False

    def _count_samples(self, file_path: str) -> int:
        """统计样本数量"""
        try:
            count = 0
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        count += 1
            return count
        except Exception:
            return 0

    def collect_detailed_stats(self) -> bool:
        """收集详细统计信息"""
        print("📊 收集数据统计信息...")

        try:
            # 使用现有的验证工具收集统计
            from tools.validate_dataset import collect_statistics

            all_samples = []

            # 加载所有种子数据
            seed_files = [
                "data/seed/ALC/seed.jsonl",
                "data/seed/AR/seed.jsonl"
            ]

            for file_path in seed_files:
                if Path(file_path).exists():
                    loader = DataLoader(strict_mode=False)
                    samples = list(loader.load_jsonl(file_path))
                    all_samples.extend(samples)

            if all_samples:
                detailed_stats = collect_statistics(all_samples)
                self.stats.update(detailed_stats)

            return True

        except Exception as e:
            print(f"⚠️  统计收集失败: {e}")
            return False

    def generate_report(self) -> str:
        """生成数据检查报告"""
        report = []

        report.append("# 数据集就绪度检查报告")
        report.append("")
        report.append(f"**检查时间**: {self.check_time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**最小样本阈值**: {self.min_samples}")
        report.append("")

        # 基本统计
        total_samples = self.stats.get("total_samples", 0)
        report.append("## 基本统计")
        report.append("")
        report.append(f"- **总样本数**: {total_samples}")
        report.append(f"- **阈值要求**: ≥{self.min_samples}")
        report.append(f"- **状态**: {'✅ 通过' if total_samples >= self.min_samples else '❌ 未达标'}")
        report.append("")

        # 文件统计
        if any(k for k in self.stats.keys() if k.endswith('.jsonl')):
            report.append("## 文件统计")
            report.append("")
            report.append("| 文件 | 样本数 |")
            report.append("|------|--------|")

            for file_path, count in self.stats.items():
                if file_path.endswith('.jsonl'):
                    report.append(f"| {file_path} | {count} |")
            report.append("")

        # 详细统计（如果可用）
        if "domain_distribution" in self.stats:
            report.append("## 领域分布")
            report.append("")
            for domain, count in sorted(self.stats["domain_distribution"].items()):
                percentage = (count / total_samples) * 100 if total_samples > 0 else 0
                report.append(".1f")
            report.append("")

        if "ask_required_distribution" in self.stats:
            report.append("## 澄清需求分布")
            report.append("")
            for ask_required, count in sorted(self.stats["ask_required_distribution"].items()):
                percentage = (count / total_samples) * 100 if total_samples > 0 else 0
                status = "需要澄清" if ask_required else "直接回答"
                report.append(".1f")
            report.append("")

        if "turns_length_stats" in self.stats:
            report.append("## 对话统计")
            report.append("")
            turns_stats = self.stats["turns_length_stats"]
            report.append(f"- **平均轮次**: {turns_stats['avg']:.1f}")
            report.append(f"- **最小轮次**: {turns_stats['min']}")
            report.append(f"- **最大轮次**: {turns_stats['max']}")
            report.append("")

        # 错误信息
        if self.errors:
            report.append("## 检查问题")
            report.append("")
            for error in self.errors:
                report.append(f"- ❌ {error}")
            report.append("")

        # 总体状态
        has_errors = len(self.errors) > 0
        meets_threshold = total_samples >= self.min_samples

        report.append("## 总体状态")
        report.append("")
        if not has_errors and meets_threshold:
            report.append("🎉 **数据集检查全部通过，可以进入训练阶段**")
        else:
            report.append("⚠️  **数据集检查发现问题，需要修复后重新检查**")
        report.append("")

        return "\n".join(report)

    def run_check(self) -> bool:
        """运行完整检查"""
        # 检查种子数据
        data_valid = self.check_seed_data()

        # 收集详细统计
        self.collect_detailed_stats()

        # 生成报告
        report = self.generate_report()
        report_path = Path("reports/data_overview.md")
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"📝 报告已保存至: {report_path}")

        return data_valid

def main():
    """主入口"""
    # 从环境变量获取最小样本阈值，默认8个
    min_samples = int(os.getenv("DATASET_MIN_SAMPLES", "8"))

    gate = DatasetGate(min_samples=min_samples)
    success = gate.run_check()

    if not success:
        print("\n❌ 数据集检查失败，请修复问题后重新检查")
        sys.exit(1)
    else:
        print("\n✅ 数据集检查通过")

if __name__ == "__main__":
    main()
