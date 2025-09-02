# Active QA v1 - 训练就绪包

**版本**: v1.0
**生成时间**: 2025-09-03
**总样本数**: 1400 (训练: 1120, 验证: 140, 测试: 140)

## 📦 包内容

本训练就绪包包含以下文件：

### 数据集文件
- `train.jsonl` - 训练数据集 (1120 样本)
- `dev.jsonl` - 验证数据集 (140 样本)
- `test.jsonl` - 测试数据集 (140 样本)

### 配置和元数据
- `schema.json` - 数据格式规范
- `metrics.json` - 质量统计和元数据
- `provenance.csv` - 数据来源追踪

## 📊 数据集统计

### 总体统计
- **总样本数**: 1400
- **去重后**: 从1456个原始样本去重得到
- **对齐准确率**: 100% (0个对齐错误)
- **字段完备率**: 100%

### 任务类型分布
- **ambiguous**: 1100 样本 (78.6%)
- **multihop**: 200 样本 (14.3%)
- **longform**: 100 样本 (7.1%)

### 数据来源
- **AmbigQA**: 1156 样本 (cc-by-sa-3.0)
- **HotpotQA**: 200 样本 (cc-by-sa-4.0)
- **ASQA**: 100 样本 (apache-2.0)
- **GSM8K**: 200 样本 (mit)

## 🔧 数据格式

每个样本的JSON格式如下：

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
    "synthesis_timestamp": "生成时间戳",
    // ... 其他元数据
  }
}
```

## 🚀 使用方法

### 基本加载
```python
import json

# 加载训练数据
train_data = []
with open('train.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            train_data.append(json.loads(line.strip()))

print(f"加载了 {len(train_data)} 个训练样本")
```

### 按任务类型过滤
```python
# 按任务类型分组
from collections import defaultdict

by_task_type = defaultdict(list)
for sample in train_data:
    task_type = sample['task_type']
    by_task_type[task_type].append(sample)

print("任务类型分布:")
for task_type, samples in by_task_type.items():
    print(f"  {task_type}: {len(samples)} 样本")
```

## 🎯 质量保证

- ✅ **零模拟**: 所有数据均基于真实数据集合成，无模拟内容
- ✅ **完美对齐**: 所有澄清问句与答案一一对应
- ✅ **许可合规**: 严格按照原始数据源许可标注
- ✅ **去重处理**: 基于文本相似度去重，移除重复样本
- ✅ **分层切分**: 按任务类型比例切分，确保分布均衡

## 📈 训练建议

1. **批量大小**: 建议从16-32开始，根据GPU内存调整
2. **学习率**: 从1e-5到5e-5开始，根据模型大小调整
3. **验证策略**: 每个epoch后在dev集上评估
4. **早停机制**: 基于dev集性能设置patience=3-5

## 🔗 相关文档

- [数据卡](../docs/dataset_card_active_qa_v1.md) - 详细的数据集介绍
- [合成策略](../../docs/stage2_plan_and_decisions.md) - 合成方法和技术细节
- [质量报告](../../data/processed/active_qa_v1/metrics.json) - 完整质量统计

## 📞 技术支持

如有问题，请联系数据团队或查阅相关文档。

---
**生成者**: Cursor AI Assistant
**最后更新**: 2025-09-03
