# Data Sprint 系统
# Sprint-α: 硬闸门检查 | Sprint-β: 数据生成流水线

.PHONY: sanity env-check data-check all-checks clean help
.PHONY: generate-data dedup-data review-quality sprint-beta help-beta

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

# Sprint-β 数据生成流水线
generate-data:
	@echo "🚀 生成训练数据..."
	@PYTHONPATH=$(shell pwd) python tools/data_generator.py

dedup-data:
	@echo "🔄 数据去重处理..."
	@PYTHONPATH=$(shell pwd) python tools/deduplication.py data/gen/2025-09-03/

review-quality:
	@echo "📊 质量评审..."
	@PYTHONPATH=$(shell pwd) python tools/quality_reviewer.py data/gen/2025-09-03/

sprint-beta:
	@echo "🚀 执行Data Sprint-β完整流水线..."
	@PYTHONPATH=$(shell pwd) python tools/data_sprint_beta.py

# 查看所有可用目标
help:
	@echo "Data Sprint 系统"
	@echo "================="
	@echo ""
	@echo "🎯 Sprint-α 硬闸门检查:"
	@echo "  all-checks      运行所有三道硬闸门检查"
	@echo "  sanity          模型真伪探针"
	@echo "  env-check       环境合规检查"
	@echo "  data-check      数据就绪度检查"
	@echo ""
	@echo "🚀 Sprint-β 数据生成:"
	@echo "  generate-data   生成ALC/AR/RSD训练数据"
	@echo "  dedup-data      数据去重处理"
	@echo "  review-quality  质量评审"
	@echo "  sprint-beta     执行完整Sprint-β流水线"
	@echo ""
	@echo "🔧 辅助工具:"
	@echo "  thought-guard-demo    思维链防护演示"
	@echo "  scan-cot-leakage      扫描CoT泄漏"
	@echo "  validate-dataset      验证数据集结构"
	@echo "  clean                 清理报告文件"
	@echo "  help                  显示此帮助信息"
	@echo ""
	@echo "📋 使用示例:"
	@echo "  # Sprint-α 检查"
	@echo "  make all-checks              # 运行完整检查"
	@echo "  make sanity                  # 只检查模型"
	@echo "  make env-check               # 只检查环境"
	@echo "  make data-check              # 只检查数据"
	@echo "  "
	@echo "  # Sprint-β 生成"
	@echo "  make sprint-beta             # 执行完整流水线"
	@echo "  make generate-data           # 只生成数据"
	@echo "  make dedup-data              # 只去重"
	@echo "  make review-quality          # 只评审质量"
	@echo "  "
	@echo "  # 高级选项"
	@echo "  THOUGHT_IN_HISTORY=true make thought-guard-demo"
	@echo ""
	@echo "🔐 环境变量配置 (.env文件):"
	@echo "  # Gemini API (必需)"
	@echo "  GEMINI_API_KEY       Gemini API密钥 (ALC生成)"
	@echo "  GEMINI_API_KEY2      Gemini备用密钥 (AR生成)"
	@echo "  GEMINI_API_KEY3      Gemini第三备用密钥 (RSD生成+评审)"
	@echo "  "
	@echo "  # 其他API (可选)"
	@echo "  DeepSeek_API_KEY     DeepSeek API密钥"
	@echo "  HF_TOKEN            HuggingFace访问令牌"
	@echo "  GIT_TOKEN           GitHub访问令牌"
	@echo "  "
	@echo "  # 系统配置"
	@echo "  GITHUB_REPO         GitHub仓库标识"
	@echo "  HF_REPO_ID          HuggingFace仓库标识"
	@echo "  MODEL_NAME          模型名称"
	@echo "  "
	@echo "  # 可选参数"
	@echo "  THOUGHT_IN_HISTORY  是否在历史中保留思考流 (默认false)"
	@echo "  DATASET_MIN_SAMPLES 数据集最小样本数阈值 (默认8)"
	@echo "  DEDUPLICATION_THRESHOLD 去重相似度阈值 (默认0.92)"

help-beta:
	@echo "🚀 Data Sprint-β 数据生成指南"
	@echo "=============================="
	@echo ""
	@echo "目标: 生成高质量的主动澄清训练数据"
	@echo "配比: ALC:AR:RSD = 5:3:2 (类人对话:歧义推理:行为蒸馏)"
	@echo ""
	@echo "📊 数据规格:"
	@echo "  ALC (类人对话): 50个 - 生活/协作/技术/计划场景"
	@echo "  AR (歧义推理): 30个 - 数理/事实/多跳推理"
	@echo "  RSD (行为蒸馏): 20个 - R1动作序列蒸馏"
	@echo "  总计: 100个高质量样本"
	@echo ""
	@echo "🎯 质量标准:"
	@echo "  ASK触发准确度: ≥95%"
	@echo "  Clarification-F1: ≥0.6"
	@echo "  重复率: <8%"
	@echo "  CoT泄漏: 0%"
	@echo ""
	@echo "🔄 执行流程:"
	@echo "  1. make sprint-beta    # 一键执行完整流水线"
	@echo "  2. 检查 reports/ 目录下的各种报告"
	@echo "  3. 验证 data/gen/2025-09-03/ 下的生成数据"
	@echo ""
	@echo "📁 输出文件:"
	@echo "  data/gen/2025-09-03/ALC/part-001.jsonl"
	@echo "  data/gen/2025-09-03/AR/part-001.jsonl"
	@echo "  data/gen/2025-09-03/RSD/part-001.jsonl"
	@echo "  reports/sprint_beta_final_report.md"
	@echo ""
	@echo "⚠️  注意事项:"
	@echo "  - 确保.env文件中配置了GEMINI_API_KEY等"
	@echo "  - 生成过程需要网络连接和API配额"
	@echo "  - 中断后可重新运行，不会重复生成"
	@echo "  - 如遇API限速会自动重试"

# 默认目标
.DEFAULT_GOAL := help