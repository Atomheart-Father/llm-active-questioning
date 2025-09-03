# Sprint-α 硬闸门检查系统
# 三道硬闸门：模型真伪、环境合规、数据就绪

.PHONY: sanity env-check data-check all-checks clean help

# 默认目标：运行所有检查
all-checks: sanity env-check data-check
	@echo "🎉 所有硬闸门检查通过！可以进入训练阶段"

# 1. 模型真伪探针
sanity:
	@echo "🔬 运行模型真伪探针..."
	@PYTHONPATH=$(shell pwd) python tools/model_sanity_probe.py
	@echo "✅ 模型真伪探针通过"

# 2. 环境合规检查
env-check:
	@echo "🔍 运行环境合规检查..."
	@PYTHONPATH=$(shell pwd) python tools/env_guard.py
	@echo "✅ 环境合规检查通过"

# 3. 数据就绪度检查
data-check:
	@echo "📊 运行数据就绪度检查..."
	@PYTHONPATH=$(shell pwd) python tools/dataset_gate.py
	@echo "✅ 数据就绪度检查通过"

# 思维链泄漏防护演示
thought-guard-demo:
	@echo "🛡️  思维链泄漏防护演示..."
	@PYTHONPATH=$(shell pwd) python tools/thought_leakage_guard.py

# 单独运行各个扫描工具
scan-cot-leakage:
	@echo "🔍 扫描CoT泄漏..."
	@PYTHONPATH=$(shell pwd) python tools/scan_for_cot_leakage.py data/seed/

validate-dataset:
	@echo "📋 验证数据集结构..."
	@PYTHONPATH=$(shell pwd) python tools/validate_dataset.py data/seed/ALC/seed.jsonl
	@PYTHONPATH=$(shell pwd) python tools/validate_dataset.py data/seed/AR/seed.jsonl

# 清理生成的文件
clean:
	@echo "🧹 清理报告文件..."
	@rm -rf reports/
	@echo "✅ 清理完成"

# 查看所有可用目标
help:
	@echo "Sprint-α 硬闸门检查系统"
	@echo "========================"
	@echo ""
	@echo "主要目标:"
	@echo "  all-checks      运行所有三道硬闸门检查"
	@echo "  sanity          模型真伪探针"
	@echo "  env-check       环境合规检查"
	@echo "  data-check      数据就绪度检查"
	@echo ""
	@echo "辅助工具:"
	@echo "  thought-guard-demo    思维链防护演示"
	@echo "  scan-cot-leakage      扫描CoT泄漏"
	@echo "  validate-dataset      验证数据集结构"
	@echo "  clean                 清理报告文件"
	@echo "  help                  显示此帮助信息"
	@echo ""
	@echo "使用示例:"
	@echo "  make all-checks              # 运行完整检查"
	@echo "  make sanity                  # 只检查模型"
	@echo "  make env-check               # 只检查环境"
	@echo "  make data-check              # 只检查数据"
	@echo "  THOUGHT_IN_HISTORY=true make thought-guard-demo  # 研究模式演示"
	@echo ""
	@echo "环境变量配置 (.env文件):"
	@echo "  GEMINI_API_KEY       Gemini API密钥"
	@echo "  GEMINI_API_KEY2      Gemini备用密钥"
	@echo "  GEMINI_API_KEY3      Gemini第三备用密钥"
	@echo "  DeepSeek_API_KEY     DeepSeek API密钥"
	@echo "  HF_TOKEN            HuggingFace访问令牌"
	@echo "  GIT_TOKEN           GitHub访问令牌"
	@echo "  GITHUB_REPO         GitHub仓库标识"
	@echo "  HF_REPO_ID          HuggingFace仓库标识"
	@echo "  MODEL_NAME          模型名称"
	@echo ""
	@echo "可选环境变量:"
	@echo "  THOUGHT_IN_HISTORY  是否在历史中保留思考流 (true/false)"
	@echo "  DATASET_MIN_SAMPLES 数据集最小样本数阈值 (默认8)"

# 默认目标
.DEFAULT_GOAL := help