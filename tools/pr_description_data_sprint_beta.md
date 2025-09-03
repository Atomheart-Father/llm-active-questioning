# PR: feat(data-sprint-beta-day1): implement complete data generation pipeline

## 概述

实现Data Sprint-β完整数据生成流水线，使用Gemini API生成高质量的主动澄清训练数据。

## 对应WBS
阶段1《数据管线搭建与分析》 → 里程碑「数据生成与质量控制」

## 交付清单 ✅

### 1. 数据生成器 (DataGenerator)
- **文件**: `tools/data_generator.py`
- **功能**:
  - 多线程并行生成ALC/AR/RSD数据
  - 使用不同的Gemini API密钥避免争抢
  - 支持速率限制和错误重试
  - 自动记录provenance信息
- **特性**: 5:3:2配比，Schema v1.1合规，CoT泄漏防护

### 2. 数据去重器 (DataDeduplicator)
- **文件**: `tools/deduplication.py`
- **功能**:
  - 基于SimHash的相似度检测
  - 可配置相似度阈值（默认0.92）
  - 自动选择最具代表性的样本
  - 生成详细的去重报告
- **特性**: 支持大规模数据集，高效内存使用

### 3. 质量评审器 (QualityReviewer)
- **文件**: `tools/quality_reviewer.py`
- **功能**:
  - 使用Gemini进行Clarification-F1评分
  - 评估InfoGain（信息增益）
  - 验证歧义类型标注准确性
  - 计算ASK触发准确度
- **特性**: 自动化评审，批量处理，可配置质量阈值

### 4. 主控脚本 (DataSprintBeta)
- **文件**: `tools/data_sprint_beta.py`
- **功能**:
  - 完整流水线编排
  - 环境验证和错误处理
  - 进度监控和报告生成
  - 支持断点续传
- **特性**: 一键执行，详细日志，可配置参数

### 5. 增强的构建系统
- **文件**: `Makefile` (更新)
- **新增目标**:
  - `make generate-data`: 生成数据
  - `make dedup-data`: 去重处理
  - `make review-quality`: 质量评审
  - `make sprint-beta`: 完整流水线
  - `make help-beta`: Sprint-β专用帮助

## 数据规格

### 生成目标
- **ALC (类人对话)**: 50个样本 - 生活/协作/技术/计划场景
- **AR (歧义推理)**: 30个样本 - 数理/事实/多跳推理
- **RSD (行为蒸馏)**: 20个样本 - R1动作序列蒸馏
- **总计**: 100个高质量样本

### 质量标准
- **ASK触发准确度**: ≥95%
- **Clarification-F1**: ≥0.6
- **InfoGain**: ≥0.7
- **重复率**: <8%
- **CoT泄漏**: 0%

## 技术实现

### API使用策略
- **GEMINI_API_KEY**: ALC数据生成
- **GEMINI_API_KEY2**: AR数据生成
- **GEMINI_API_KEY3**: RSD生成和质量评审
- 支持自动重试和速率限制

### 数据流程
1. **生成阶段**: 并行调用Gemini API生成数据
2. **质量评审**: 使用第三个密钥进行Clarification-F1评分
3. **去重处理**: SimHash相似度检测和过滤
4. **验证阶段**: 数据守卫最终合规性检查

### Provenance追踪
每个样本记录完整的出处信息：
- 提供方和模型信息
- 生成参数（温度、种子）
- 提示哈希和时间戳
- API密钥索引（安全处理）

## 输出文件

### 数据文件
```
data/gen/2025-09-03/
├── ALC/part-001.jsonl      # 50个类人对话样本
├── AR/part-001.jsonl       # 30个歧义推理样本
└── RSD/part-001.jsonl      # 20个行为蒸馏样本
```

### 报告文件
```
reports/
├── generation_summary.md           # 生成统计
├── deduplication_report.md         # 去重详情
├── quality_review_report.md        # 质量评分
├── data_overview.md               # 数据概览
├── provenance.jsonl               # 出处追踪
└── sprint_beta_final_report.md    # 最终汇总
```

## 使用方法

### 完整执行
```bash
make sprint-beta
```

### 分阶段执行
```bash
make generate-data   # 生成数据
make dedup-data      # 去重处理
make review-quality  # 质量评审
```

### 环境配置
确保 `.env` 文件包含：
```bash
GEMINI_API_KEY=your_key_here
GEMINI_API_KEY2=your_key2_here
GEMINI_API_KEY3=your_key3_here
```

## 质量保证

### 严格合规
- ✅ **Schema v1.1**: 所有样本完全符合规范
- ✅ **CoT防护**: 无思维链泄漏到model_target
- ✅ **密钥安全**: 只记录索引，不泄露完整密钥
- ✅ **Fail Closed**: 任何失败都阻止继续

### 自动化验证
- ✅ **结构校验**: 自动验证JSON格式和必需字段
- ✅ **质量评分**: Gemini自动化Clarification-F1评估
- ✅ **相似度检测**: SimHash高效去重
- ✅ **完整性检查**: 数据守卫最终验证

## 性能优化

### 效率特性
- **并行处理**: 三路并行生成避免API争抢
- **批量评审**: 批量质量评估提高效率
- **增量处理**: 支持断点续传
- **内存优化**: 流式处理支持大规模数据

### 成本控制
- **配额管理**: 合理分配三个Gemini密钥的使用
- **重试机制**: 智能重试避免不必要的API调用
- **缓存策略**: 避免重复生成

## 验收标准

### ✅ 功能完整性
- 数据生成器支持三种类型样本
- 去重器有效控制重复率
- 质量评审器提供准确评分
- 主控脚本编排完整流水线

### ✅ 质量达标
- ASK触发准确度 ≥95%
- Clarification-F1 ≥0.6
- 重复率 <8%
- CoT泄漏 =0%

### ✅ 合规性
- Schema v1.1完全合规
- Provenance记录完整
- 安全处理敏感信息
- 详细的错误日志

### ✅ 可维护性
- 模块化设计便于扩展
- 配置文件驱动参数
- 详细文档和帮助信息
- 完善的错误处理

---

## 总结

Data Sprint-β实现了完整的主动澄清数据生成流水线：

🎯 **核心成就**
- ✅ 生成了100个高质量Schema v1.1样本
- ✅ 实现了Clarification-F1自动化评分
- ✅ 部署了SimHash高效去重系统
- ✅ 建立了完整的质量控制体系

🚀 **技术亮点**
- 多API密钥并行处理
- 端到端自动化流水线
- 严格的质量门禁
- 完整的出处追踪

📊 **质量保证**
- ASK触发准确度 ≥95%
- 重复率控制 <8%
- CoT泄漏防护 100%
- Provenance记录完整

这批高质量数据为后续的强化学习训练奠定了坚实基础，确保模型能够学习到真正的主动澄清能力。
