# RC1 - LLM主动提问推理模型

> **一个会节制提问、敢自己推理的小模型：主动澄清率↓25%，多源任务成功率↑7–10pp。**

RC1是首个专门针对主动提问和推理优化的4B参数语言模型。通过PPO强化学习，模型学会了在恰当时机向用户澄清问题，同时避免过度提问，显著提升了多步推理任务的成功率。

## 🚀 快速开始

### 使用GGUF模型 (推荐)

```bash
# 下载量化模型
wget https://github.com/Atomheart-Father/llm-active-questioning/releases/download/rc1/rc1_model_q5_0.gguf

# 使用llama.cpp推理
llama-cli -m rc1_model_q5_0.gguf -p "请分析这个数学问题..." -n 512 --temp 0.1
```

### 使用Python

```python
from transformers import AutoTokenizer, AutoModelForCausalLM

# 加载模型
model_path = "./checkpoints/rc1/best"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(model_path)

# 推理
prompt = """请分析以下问题并提供详细解答：

一个水池有两个进水管和一个出水管。第一个进水管每小时注入20升水，第二个进水管每小时注入30升水，出水管每小时排出15升水。如果同时打开所有管道，多长时间能注满容量为800升的水池？"""

inputs = tokenizer(prompt, return_tensors="pt")
outputs = model.generate(
    **inputs, 
    max_length=512, 
    temperature=0.1,
    do_sample=True,
    pad_token_id=tokenizer.eos_token_id
)

response = tokenizer.decode(outputs[0], skip_special_tokens=True)
print(response[len(prompt):])
```

## 📊 性能亮点

| 指标 | 改善幅度 | 说明 |
|------|---------|------|
| **任务成功率** | **+8pp** | HotpotQA/StrategyQA等需要澄清的任务 |
| **过度澄清** | **-28%** | 减少不必要的提问，提升效率 |
| **推理速度** | **86.5 tokens/s** | q5_0量化，4GB内存 |
| **参数效率** | **4B** | 相比7B+模型显著轻量化 |

## 🛠 模型配置

### 量化版本选择

| 版本 | 文件大小 | 内存需求 | 速度 | 推荐场景 |
|------|----------|----------|------|----------|
| **q4_0** | ~2.5GB | 2.5GB | 138.7 tokens/s | 移动设备/边缘计算 |
| **q5_0** ⭐ | ~3.5GB | 4.0GB | 86.5 tokens/s | **生产推荐** |
| **q8_0** | ~5.5GB | 6.5GB | 50.9 tokens/s | 高质量应用 |

### 推理优化

```bash
# Apple Silicon优化
llama-cli -m rc1_model_q5_0.gguf -ngl 32 -p "您的问题"

# CPU优化
llama-cli -m rc1_model_q5_0.gguf -t 8 -p "您的问题"

# 服务器模式
llama-server -m rc1_model_q5_0.gguf --port 8080 --host 0.0.0.0
```

## 💡 核心特性

### 🎯 智能澄清
- **恰当时机**: 只在信息不足时提问
- **高质量问题**: 澄清问题直接相关且有效
- **避免过度**: 通过惩罚机制防止无意义提问

### 🧠 多步推理
- **工具调用**: 支持计算器、搜索等外部工具
- **思维链**: 生成清晰的推理过程
- **错误修正**: 识别并纠正推理错误

### ⚡ 高效训练
- **PPO优化**: 强化学习优化对话策略
- **多维奖励**: 平衡逻辑性、准确性、自然度
- **自适应学习**: α退火和优先采样

## 📖 使用示例

### 例子1: 数学推理（直接解答）
```
用户: 计算 15 × 24 + 36 ÷ 4

RC1: 让我来计算这个表达式：

按照运算顺序（先乘除后加减）：
1. 15 × 24 = 360
2. 36 ÷ 4 = 9  
3. 360 + 9 = 369

因此答案是 369。
```

### 例子2: 模糊问题（合理澄清）
```
用户: 帮我分析一下这个投资方案

RC1: 我需要更多信息来为您提供准确的投资分析：

1. 具体的投资项目类型（股票、基金、房地产等）
2. 投资金额和期限
3. 您的风险承受能力
4. 预期收益目标

请提供这些详细信息，我会为您进行专业分析。
```

### 例子3: 多跳推理
```
用户: 如果小明比小红大3岁，小红比小李小2岁，小李今年15岁，那么小明今年多少岁？

RC1: 让我通过推理来解决这个年龄问题：

已知条件：
- 小李今年15岁
- 小红比小李小2岁  
- 小明比小红大3岁

推理过程：
1. 小红的年龄 = 小李年龄 - 2 = 15 - 2 = 13岁
2. 小明的年龄 = 小红年龄 + 3 = 13 + 3 = 16岁

因此，小明今年16岁。
```

## 🔧 本地部署

### 环境要求
- Python 3.8+
- PyTorch 1.13+
- transformers 4.30+
- 8GB+ RAM (推荐16GB)

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/Atomheart-Father/llm-active-questioning.git
cd llm-active-questioning

# 安装依赖
pip install -r requirements.txt

# 下载模型权重
# 选项1: 从Hugging Face
huggingface-cli download Atomheart-Father/RC1-4B ./checkpoints/rc1/best

# 选项2: 从GitHub Releases
wget https://github.com/Atomheart-Father/llm-active-questioning/releases/download/rc1/rc1_model.tar.gz
tar -xzf rc1_model.tar.gz -C ./checkpoints/rc1/best/
```

### 运行评估

```bash
# 运行基准测试
python scripts/rc1_benchmarks.py

# 运行对话测试
python examples/interactive_chat.py --model checkpoints/rc1/best
```

## 📚 技术文档

- **[模型卡](./reports/rc1/model_card.md)**: 详细的技术规格和性能指标
- **[训练报告](./reports/rc1/rc1_final_report.json)**: 完整的训练过程和结果
- **[基准测试](./reports/rc1/benchmarks/)**: 推理性能和质量评估
- **[API文档](./docs/api.md)**: 编程接口使用指南

## 🤝 贡献指南

我们欢迎社区贡献！参与方式：

1. **Bug报告**: 通过GitHub Issues报告问题
2. **功能建议**: 提出新功能的想法和建议  
3. **代码贡献**: 提交Pull Request改进代码
4. **数据贡献**: 分享高质量的训练数据

### 开发环境

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
python -m pytest tests/

# 代码格式化
black src/ tests/
flake8 src/ tests/
```

## 📄 许可证

- **代码**: Apache-2.0 许可证
- **模型**: 遵循Qwen3-4B-Thinking的许可条款
- **数据**: 基于公开数据集，详见各自许可

## 📞 联系我们

- **GitHub**: [Issues](https://github.com/Atomheart-Father/llm-active-questioning/issues) / [Discussions](https://github.com/Atomheart-Father/llm-active-questioning/discussions)
- **论文**: [arXiv预印本](#) (即将发布)
- **演示**: [在线Demo](#) (开发中)

## 🙏 致谢

感谢以下开源项目和数据集：
- [Qwen Team](https://github.com/QwenLM/Qwen) - 基础模型
- [HotpotQA](https://hotpotqa.github.io/) - 多跳推理数据
- [StrategyQA](https://allenai.org/data/strategyqa) - 策略推理数据  
- [GSM8K](https://github.com/openai/grade-school-math) - 数学推理数据
- [TRL](https://github.com/huggingface/trl) - 强化学习框架

---

*如果RC1对您的项目有帮助，请给我们一个⭐️*
