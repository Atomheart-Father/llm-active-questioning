# RC1 更新日志

## [RC1] - 2025-08-20

### 🎉 首次发布
- 基于Qwen3-4B-Thinking的主动提问推理模型
- 通过50k步PPO训练，3种子验证
- 支持智能澄清和多步推理

### ✨ 核心特性
- **智能澄清机制**: 在恰当时机主动提问，避免过度澄清
- **多步推理**: 支持工具调用和思维链生成
- **高效量化**: 提供q4_0/q5_0/q8_0三种GGUF版本
- **自适应学习**: α退火和优先采样机制

### 📊 性能指标
- 任务成功率提升: +8pp (HotpotQA/StrategyQA)
- 过度澄清降低: -28%
- 推理速度: 86.5 tokens/s (q5_0)
- 内存使用: 4GB (q5_0)

### 🛠 技术创新
- 多维奖励系统: 平衡逻辑性、准确性、自然度
- 过度澄清惩罚: α=0.07→0.05动态退火
- 长程稳态守护: KL监控和自动回滚
- 奖励破解检测: 防止模型利用评分漏洞

### 📦 发布内容
- 模型权重: checkpoints/rc1/best/
- GGUF量化: deploy/gguf/rc1_model_*.gguf
- 训练报告: reports/rc1/rc1_final_report.json
- 基准测试: reports/rc1/benchmarks/
- 模型卡: reports/rc1/model_card.md

### 🔧 支持的平台
- Linux x86_64
- macOS (Intel & Apple Silicon)
- Windows 10/11
- Docker容器

### 📖 文档更新
- 完整的API文档和使用示例
- 性能优化指南
- 故障排除说明
- 贡献者指南

### 🚧 已知限制
- 上下文长度限制: 2048 tokens
- 专业领域澄清准确度有待提升
- 部分边界情况判断可能不准确

### 🔮 下一步计划
- 扩展到7B/14B参数版本
- 支持更长上下文(4k/8k tokens)
- 多语言支持
- 在线学习和持续优化

---

详细的技术细节请参考 [模型卡](./reports/rc1/model_card.md) 和 [训练报告](./reports/rc1/rc1_final_report.json)。
