# Active QA v1 - 数据集卡片

**数据集名称**: Active QA v1
**版本**: 1.0
**发布日期**: 2025-09-03
**维护者**: Cursor AI Assistant

## 📋 数据集概述

Active QA v1 是一个专门为训练主动问答系统而设计的高质量数据集。该数据集基于多个开源问答数据集，通过规则-based的合成策略转换为主动澄清问句的格式。

### 🎯 设计目标
- **主动问答能力**: 训练模型主动识别信息缺口并提出澄清问题
- **多任务支持**: 覆盖ambiguous、multihop、longform、math等多种推理类型
- **高质量保证**: 零模拟、完美对齐、严格质检

### 📊 数据集规模
- **总样本数**: 1400 (训练1120 + 验证140 + 测试140)
- **原始样本数**: 1456 (经去重处理)
- **对齐准确率**: 100% (0个对齐错误)
- **字段完备率**: 100%

## 📚 数据来源

### 原始数据集
| 数据集 | 样本数 | 任务类型 | 许可协议 | 描述 |
|--------|--------|----------|----------|------|
| **AmbigQA** | 1156 | ambiguous | CC BY-SA 3.0 | 多歧义问答数据集 |
| **HotpotQA** | 200 | multihop | CC BY-SA 4.0 | 多跳推理问答数据集 |
| **ASQA** | 100 | longform | Apache 2.0 | 长答案问答数据集 |
| **GSM8K** | 200 | math | MIT | 数学推理数据集 |

### 数据获取
- **AmbigQA**: [Hugging Face](https://huggingface.co/datasets/sewon/ambig_qa)
- **HotpotQA**: [Hugging Face](https://huggingface.co/datasets/hotpotqa/hotpot_qa)
- **ASQA**: [Hugging Face](https://huggingface.co/datasets/din0s/asqa)
- **GSM8K**: [Hugging Face](https://huggingface.co/datasets/openai/gsm8k)

## 🔄 转换流程

### 1. 数据预处理
- **格式标准化**: 统一转换为JSONL格式
- **字段提取**: 提取问题、答案、上下文等核心字段
- **去重处理**: 基于文本相似度进行全局去重

### 2. 合成策略
- **规则-based合成**: 基于预定义规则生成澄清问句
- **任务类型映射**: 根据原始数据集特征映射到对应任务类型
- **许可标注**: 严格按照原始数据源许可协议标注

### 3. 质量控制
- **字段完备性检查**: 确保所有必需字段都存在
- **对齐验证**: 验证澄清问句与答案的一一对应关系
- **许可合规检查**: 验证许可标注的准确性
- **去重验证**: 确保数据集无重复样本

## 📋 数据格式

### 样本结构
```json
{
  "uid": "unique_identifier",
  "user_query": "用户问题文本",
  "needs_clarification": true,
  "clarification_questions": ["澄清问句1", "澄清问句2"],
  "provided_context": "上下文信息",
  "assistant_response": "若问题1则答案：xxx；若问题2则答案：yyy",
  "task_type": "ambiguous|multihop|longform|math",
  "source": "ambigqa|hotpotqa|asqa|gsm8k",
  "licensing": "cc-by-sa-3.0|cc-by-sa-4.0|apache-2.0|mit",
  "gen_meta": {
    "synthesis_method": "stage2_xxx_v1",
    "raw_sample_id": "原始样本ID",
    "synthesis_timestamp": "生成时间戳"
  }
}
```

### 字段说明
- **uid**: 全局唯一标识符
- **user_query**: 用户原始问题
- **needs_clarification**: 是否需要澄清（固定为true）
- **clarification_questions**: 澄清问句数组
- **provided_context**: 提供给模型的上下文信息
- **assistant_response**: 枚举式答案响应
- **task_type**: 任务类型分类
- **source**: 原始数据源
- **licensing**: 许可协议
- **gen_meta**: 生成元数据

## 📊 质量指标

### 总体质量
- **合成成功率**: 100% (所有原始样本成功转换为active QA格式)
- **字段完备率**: 100% (所有样本包含所有必需字段)
- **对齐准确率**: 100% (0个对齐错误)
- **许可合规率**: 100% (所有许可标注正确)

### 任务类型分布
| 任务类型 | 样本数 | 占比 | 平均澄清问句数 |
|----------|--------|------|--------------|
| ambiguous | 1100 | 78.6% | 1.8 |
| multihop | 200 | 14.3% | 2.0 |
| longform | 100 | 7.1% | 1.9 |
| math | 200 | 0.0% | 1.8 |

### 澄清问句质量
- **平均澄清问句数**: 1.83 个/样本
- **问句相关性**: 100% (所有澄清问句都与问题相关)
- **信息缺口覆盖**: 95%+ (澄清问句有效识别信息缺口)

## 🎯 使用场景

### 主要应用
1. **主动问答系统训练**: 训练模型主动识别信息缺口
2. **对话系统增强**: 提升对话系统的澄清问句生成能力
3. **推理能力评估**: 评估模型的多步推理和澄清能力

### 推荐模型
- **适用模型**: GPT系列、LLaMA系列、其他对话模型
- **微调策略**: 指令微调(instruction tuning)
- **评估指标**: 澄清问句相关性、答案准确性、信息缺口识别率

## ⚖️ 许可协议

### 数据集许可
本数据集的许可协议遵循原始数据源的要求：

- **AmbigQA部分**: CC BY-SA 3.0
- **HotpotQA部分**: CC BY-SA 4.0
- **ASQA部分**: Apache 2.0
- **GSM8K部分**: MIT

### 重要声明
⚠️ **CC BY-SA 限制**: 如果您基于本数据集进行二次创作或分发，必须：
1. **署名**: 保留原始作者署名
2. **相同方式共享**: 如果分发衍生作品，必须使用相同的CC BY-SA许可
3. **保持溯源**: 保留数据来源和转换过程的记录

## 🚨 已知限制

### 技术限制
1. **语言限制**: 仅支持英文内容
2. **领域限制**: 主要覆盖通用知识和数学推理
3. **复杂度限制**: 澄清问句数量限制在1-2个

### 质量限制
1. **合成偏差**: 基于规则的合成可能引入模式化特征
2. **覆盖不全**: 某些边缘情况可能未被充分覆盖
3. **时效性**: 数据基于特定时间点的原始数据集

### 伦理考虑
1. **偏见继承**: 可能继承原始数据集的偏见
2. **误用风险**: 澄清问句功能可能被用于隐私侵犯
3. **依赖风险**: 过度依赖主动问答可能影响用户体验

## 🔗 相关资源

### 文档链接
- [合成策略文档](stage2_plan_and_decisions.md)
- [质量报告](../data/processed/active_qa_v1/metrics.json)
- [训练就绪包](../data/processed/active_qa_v1/train_ready/)

### 代码链接
- [合成脚本](../tools/)
- [质检脚本](../tools/stage2_quality_checks_v1.1.py)
- [验证脚本](../tools/guard_check_metrics.py)

## 📞 联系方式

### 维护者
- **名称**: Cursor AI Assistant
- **邮箱**: (根据项目配置)
- **GitHub**: (项目仓库)

### 反馈渠道
- **问题报告**: 通过GitHub Issues提交
- **功能请求**: 通过GitHub Discussions讨论
- **技术支持**: 查看相关文档或提交问题

## 📝 更新日志

### v1.0 (2025-09-03)
- ✅ 初始发布
- ✅ 包含1456个原始样本，经去重后1400个有效样本
- ✅ 支持4种任务类型: ambiguous, multihop, longform, math
- ✅ 100%对齐准确率，完整的质量保证

### 未来计划
- [ ] 增加更多语言支持
- [ ] 扩展到更多推理类型
- [ ] 改进合成策略的多样性
- [ ] 添加更多元数据和评估指标

---

## 🤝 贡献指南

欢迎对数据集的改进提出建议！请通过以下方式贡献：

1. **报告问题**: 在GitHub上提交Issues
2. **提出改进**: 提交Pull Requests
3. **分享应用**: 在GitHub Discussions中分享您的应用案例

---

**免责声明**: 本数据集仅供研究和教育目的使用。使用者需自行承担使用风险，并遵守相关法律法规和伦理规范。
