#!/usr/bin/env python3
"""Environment Guard - 检查环境变量和密钥合规性

验证.env文件中必需的变量是否存在且有效。
不泄露完整密钥，只显示掩码值。
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# 必需的环境变量列表
REQUIRED_ENV_VARS = [
    "GEMINI_API_KEY",
    "GEMINI_API_KEY2",
    "GEMINI_API_KEY3",
    "DeepSeek_API_KEY",
    "HF_TOKEN",
    "GIT_TOKEN",
    "GITHUB_REPO",
    "HF_REPO_ID",
    "MODEL_NAME"
]

class EnvGuard:
    """环境变量守卫"""

    def __init__(self):
        self.check_time = datetime.now()
        self.results = {}

    def check_env_file(self) -> bool:
        """检查.env文件是否存在"""
        env_path = Path(".env")
        if not env_path.exists():
            print(f"❌ .env文件不存在: {env_path.absolute()}")
            return False
        return True

    def load_env_vars(self) -> Dict[str, str]:
        """从.env文件加载环境变量"""
        env_vars = {}
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            key, value = line.split("=", 1)
                            env_vars[key.strip()] = value.strip()
        except Exception as e:
            print(f"❌ 读取.env文件失败: {e}")
            return {}

        return env_vars

    def validate_env_vars(self, env_vars: Dict[str, str]) -> Tuple[bool, List[str]]:
        """验证环境变量"""
        missing_vars = []
        all_valid = True

        for var in REQUIRED_ENV_VARS:
            if var not in env_vars or not env_vars[var]:
                missing_vars.append(var)
                all_valid = False
            else:
                # 记录结果（掩码处理）
                masked_value = self._mask_value(env_vars[var])
                self.results[var] = {
                    "exists": True,
                    "masked_value": masked_value,
                    "length": len(env_vars[var])
                }

        for var in missing_vars:
            self.results[var] = {
                "exists": False,
                "masked_value": None,
                "length": 0
            }

        return all_valid, missing_vars

    def _mask_value(self, value: str) -> str:
        """掩码处理密钥值，只显示末4位"""
        if len(value) <= 4:
            return "*" * len(value)
        return "*" * (len(value) - 4) + value[-4:]

    def generate_report(self) -> str:
        """生成环境检查报告"""
        report = []

        # 标题
        report.append("# 环境变量合规检查报告")
        report.append("")
        report.append(f"**检查时间**: {self.check_time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # 总结
        total_vars = len(REQUIRED_ENV_VARS)
        existing_vars = sum(1 for r in self.results.values() if r["exists"])
        report.append(f"**总变量数**: {total_vars}")
        report.append(f"**存在变量数**: {existing_vars}")
        report.append(f"**缺失变量数**: {total_vars - existing_vars}")
        report.append("")

        # 详细结果
        report.append("## 变量状态详情")
        report.append("")
        report.append("| 变量名 | 状态 | 掩码值 | 长度 |")
        report.append("|--------|------|--------|------|")

        for var in REQUIRED_ENV_VARS:
            result = self.results.get(var, {"exists": False, "masked_value": None, "length": 0})
            status = "✅ 存在" if result["exists"] else "❌ 缺失"
            masked = result["masked_value"] or "N/A"
            length = result["length"]
            report.append(f"| {var} | {status} | {masked} | {length} |")

        report.append("")
        report.append("## 安全说明")
        report.append("")
        report.append("- 所有密钥值已进行掩码处理，仅显示末4位")
        report.append("- 报告不包含任何完整密钥信息")
        report.append("- 环境变量仅在运行时读取，不写入代码或日志")
        report.append("")

        return "\n".join(report)

    def run_check(self) -> bool:
        """运行完整检查"""
        print("🔍 开始环境变量合规检查...")

        # 检查.env文件
        if not self.check_env_file():
            return False

        # 加载环境变量
        env_vars = self.load_env_vars()
        if not env_vars:
            return False

        # 验证变量
        all_valid, missing_vars = self.validate_env_vars(env_vars)

        if missing_vars:
            print("❌ 发现缺失的环境变量:")
            for var in missing_vars:
                print(f"   - {var}")
            return False

        print("✅ 所有必需环境变量都存在")

        # 生成报告
        report = self.generate_report()
        report_path = Path("reports/env_check.md")
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"📝 报告已保存至: {report_path}")

        return True

def main():
    """主入口"""
    guard = EnvGuard()
    success = guard.run_check()

    if not success:
        print("\n❌ 环境检查失败，请检查.env文件")
        sys.exit(1)
    else:
        print("\n✅ 环境检查通过")

if __name__ == "__main__":
    main()
