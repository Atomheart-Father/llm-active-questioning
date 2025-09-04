# LLM主动提问与推理增强系统

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 通过增强LLM主动提问能力来提升推理能力并创造新的人机交互范式

## 🎯 项目概述

本项目致力于解决LLM在面对模糊或不完整信息时的推理局限性，通过训练模型主动向用户提问澄清，实现更智能、更人性化的AI交互体验。

### 核心理念
- **主动澄清**: 当信息不足时，AI主动提问而非猜测
- **多轮推理**: 通过分步骤对话收集信息并推理
- **人机协作**: 创造新的交互范式，提升任务完成质量

## ✨ 主要功能

### 🤖 智能交互系统
- **主动提问机制**: 自动识别信息缺失并生成澄清问题
- **多轮对话管理**: 完整的对话状态跟踪和管理
- **用户行为适应**: 处理合作、非合作、打断等多种用户行为

### 📊 数据处理与生成
- **多数据集支持**: HotpotQA、AmbigQA、GSM8K等数据集集成
- **可选对话生成**: 使用Gemini API将单轮QA转换为多轮对话（Sidecar工具，不进入训练主回路）
- **轨迹数据收集**: 为强化学习训练提供高质量数据

### 🧠 模型训练框架
- **强化学习支持**: PPO训练框架，支持策略优化
- **奖励系统设计**: 综合准确性、用户满意度和效率的奖励机制
- **模型评估**: 多维度性能评估和监控

## 🏗️ 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   用户输入      │───▶│  问题分析模块    │───▶│  策略决策模块    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   轨迹收集      │◀───│  多轮对话引擎    │◀───│  交互模式选择    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │
        ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│  强化学习训练    │    │   回答生成      │
└─────────────────┘    └─────────────────┘
```

## 🚀 快速开始

### 环境要求
- Python 3.9+
- PyTorch 2.0+
- Transformers 4.36+
- Apple Silicon MPS支持 (推荐)

### 一键安装（推荐）
```bash
# 运行自动初始化脚本
./scripts/setup_project.sh
```

### 手动安装
```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate     # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 安装项目
pip install -e .
```

### 基础使用

#### 1. 运行单轮提问测试
```bash
python stage1_optimized.py
```

#### 2. 运行多轮交互系统
```bash
python multi_turn_system.py
```

#### 3. 生成训练数据
```bash
python dataset_expansion.py
```

#### 4. 测试Gemini API集成 (可选工具)
```bash
# 注意：Gemini集成已移至integrations/gemini/目录
# 仅用于独立测试，不参与训练/评测主回路
python integrations/gemini/gemini_integration.py
```

#### 5. 使用Notebook进行数据生成和分析 (推荐)
```bash
# 启动Jupyter Notebook
jupyter notebook

# 或使用VS Code打开notebook文件
# 推荐按以下顺序运行：
# 1. notebooks/00_env_and_router_check.ipynb - 环境和路由检查
# 2. notebooks/10_sprint_beta_microbatch.ipynb - 生成微批数据
# 3. notebooks/20_quality_reports_and_review.ipynb - 质量分析和报告
```

**Notebook优势：**
- ✅ **可中断恢复**: 运行到一半可保存状态，下次继续
- ✅ **逐步调试**: 每个cell独立运行，方便调试
- ✅ **可视化输出**: 直接查看生成结果和质量指标
- ✅ **安全可重现**: 所有参数和配置都记录在notebook中

### Notebook使用指南

#### 1. 环境检查 (`00_env_and_router_check.ipynb`)
- **功能**: 加载环境变量，检查Provider可用性，验证路由配置
- **输出**: `artifacts_review/00_env_probe.md` (安全，无敏感信息)
- **运行时间**: < 30秒

#### 2. 微批生成 (`10_sprint_beta_microbatch.ipynb`)
- **功能**: 使用streaming client生成指定数量的样本，支持Fail-Over
- **参数配置**:
  ```python
  DATA_DATE = "2025-09-04"
  TARGET_ALC = 4    # ALC样本数量
  TARGET_AR = 3     # AR样本数量
  TARGET_RSD = 3    # RSD样本数量
  ```
- **输出**: `runs/<date>/<task>/partial.jsonl` → `data/gen/<date>/<task>/part-*.jsonl`
- **特性**: 断点续跑、增量保存、自适应token限制

#### 3. 质量分析 (`20_quality_reports_and_review.ipynb`)
- **功能**: 分析生成数据质量，生成评审报告
- **输入**: `data/gen/<date>/<task>/part-*.jsonl` 文件
- **输出**: `artifacts_review/` 目录
  - `generation_summary.md` - 生成统计
  - `quality_review_report.md` - 详细质量指标
  - `samples/` - 5个抽检样本文件
- **指标计算**: Schema合规率、ASK触发率、控制符合规等

### 配置说明

主要配置文件：`configs/default_config.yaml`

```yaml
# 模型配置
model:
  name: "Qwen/Qwen3-4B-Thinking-2507"  # 基础模型
  max_length: 2048
  device: "auto"
  
# 训练配置  
training:
  batch_size: 8
  learning_rate: 1.41e-5
  max_epochs: 10
```

## 📊 实验结果

### 第一阶段：基础主动提问验证
- **应提问场景识别率**: 100%
- **提问生成成功率**: 66.7%
- **总体行为正确率**: 初步验证通过

### 第二阶段：多轮交互系统
- **多轮对话成功率**: 100% (合作模式)
- **平均对话轮次**: 3-5轮
- **系统稳定性**: 15个测试场景全部通过
- **数据生成能力**: 支持大规模训练数据生成

## 🔧 核心模块

### 交互引擎 (`multi_turn_system.py`)
```python
# 运行多轮对话
system = MultiTurnInteractionSystem()
system.initialize_components()

result = system.run_conversation(
    "他什么时候出生的？",
    InteractionMode.ACTIVE_QUESTIONING
)
```

### 数据生成 (`dataset_expansion.py`)
```python
# 扩展数据集
expander = DatasetExpander()
training_data = expander.build_comprehensive_training_dataset()
```

### API集成 (可选工具 - `integrations/gemini/gemini_integration.py`)
```python
# 注意：Gemini集成已隔离，不参与训练/评测主回路
# 仅用于独立测试和Shadow评测

from integrations.gemini.gemini_integration import GeminiDataGenerator

# 生成澄清对话 (仅用于独立测试)
generator = GeminiDataGenerator()
dialogue = generator.generate_clarifying_dialogue("模糊问题")
```

## 📈 性能指标

| 指标 | 值 | 说明 |
|------|-----|------|
| 模型加载时间 | ~8秒 | Qwen3-4B-Thinking + MPS |
| 单轮推理速度 | ~2秒 | 包含思考过程 |
| 多轮对话平均时长 | 30-60秒 | 3-5轮交互 |
| 内存占用 | ~8GB | 模型 + 系统开销 |

## 🔬 技术特色

### 1. 先进的思考机制
- 基于Qwen3-4B-Thinking模型的内在推理能力
- `<think>`标签捕获模型思考过程
- 支持复杂推理链的可视化

### 2. 智能提问策略
```python
def detect_clarification_need(self, response: str) -> Tuple[bool, str]:
    """智能检测是否需要澄清"""
    # 多维度检测逻辑
    # 1. 问号检测
    # 2. 关键词模式匹配  
    # 3. 上下文完整性分析
```

### 3. 用户行为模拟
- **合作模式**: 用户积极提供澄清信息
- **非合作模式**: 用户拒绝或忽略澄清请求
- **打断模式**: 用户改变话题或提出新问题

## 📚 数据集支持

- **HotpotQA**: 多跳推理问答，需要从多个文档收集信息
- **AmbigQA**: 歧义问题处理，训练澄清提问能力
- **GSM8K**: 数学推理，验证逻辑思维能力
- **自定义数据**: 支持添加特定领域的训练数据

## 🛠️ 开发指南

### 项目结构
```
project/
├── src/                          # 核心源码
│   ├── utils/                    # 工具模块
│   ├── data_preparation/         # 数据处理
│   ├── training/                 # 训练模块
│   ├── simulation/               # 用户模拟
│   └── evaluation/               # 评估系统
├── configs/                      # 配置文件
├── scripts/                      # 执行脚本
├── docs/                         # 文档
└── tests/                        # 测试用例
```

### 添加新的交互模式
1. 在`InteractionMode`枚举中添加新模式
2. 实现对应的prompt生成逻辑
3. 添加状态管理和转换规则
4. 编写测试用例验证功能

### 集成新的数据源
1. 在`dataset_expansion.py`中添加数据加载逻辑
2. 实现数据格式转换函数
3. 配置采样和预处理参数
4. 测试数据质量和生成效果

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

### 开发流程
1. Fork本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开Pull Request

### 代码规范
- 遵循PEP 8 Python代码风格
- 添加详细的docstring文档
- 编写相应的测试用例
- 使用类型提示

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)

## 🙏 致谢

感谢以下开源项目和研究工作：
- [Qwen](https://github.com/QwenLM/Qwen) - 基础语言模型
- [Transformers](https://huggingface.co/transformers/) - 模型推理框架
- [TRL](https://github.com/huggingface/trl) - 强化学习训练库
- [HotpotQA](https://hotpotqa.github.io/) - 多跳问答数据集

## 📞 联系我们

- 项目主页: [GitHub Repository](https://github.com/your-org/llm-active-questioning)
- 问题反馈: [GitHub Issues](https://github.com/your-org/llm-active-questioning/issues)
- 邮箱: bozhongxiao@gmail.com

---

**让AI学会提问，让交互更智能！** 🤖✨