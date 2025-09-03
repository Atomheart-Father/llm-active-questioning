# 数据 Schema v1.1

## 概述

本schema定义了主动澄清（Active Clarification）任务的数据格式，用于训练模型在回答前主动识别信息缺口并提出澄清问题。

## 核心约束

### 黄金规则（硬约束）
1. **禁止思维链泄漏**: `turns[].model_target` 中**不得**包含长段思维链文本
2. **禁止硬编码规则**: 不允许在数据或代码中写死"遇到X就输出澄清句模板"
3. **禁止模拟数据**: 所有数据必须可追溯，不得使用生成式填充
4. **可复现性**: 所有处理过程可重现，结果确定性

### 行为控制符
- `<ASK> ... </ASK>`: 触发澄清问题
- `<FINAL> ... </FINAL>`: 给出最终回答
- `<think> ... </think>`: 私有思考流（仅训练/评测可见）

## 数据结构

### 完整Schema

```json
{
  "id": "ALC-0019",
  "domain": "planning",
  "source": "synthetic-gemini|curated|r1-distill|human",
  "turns": [
    {
      "role": "user",
      "text": "帮我定周五晚餐，两个人，预算不要太贵。"
    },
    {
      "role": "model_target",
      "text": "<ASK> 你所在城市？预算上限？有无忌口？ </ASK>"
    }
  ],
  "labels": {
    "ambiguity_types": ["location", "budget", "diet"],
    "ask_required": true,
    "good_question_set": ["城市", "预算上限", "忌口"],
    "minimal_clarifications": 2,
    "oracle_answer": null
  },
  "reasoning": {
    "think_stream": "检测缺口：位置/预算/忌口→先问位置与预算→…（仅训练/评测可见，禁止写回历史）",
    "actions": [
      {"t": "AWARE_GAP", "vars": ["location", "budget", "diet"]},
      {"t": "ASK", "q": "请确认城市、预算上限、忌口？"},
      {"t": "STOP_ASK"},
      {"t": "DERIVE", "note": "按预算筛餐厅…"},
      {"t": "FINALIZE"}
    ]
  }
}
```

## 字段说明

### 根级字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 唯一标识符，格式：`{domain}-{seq}` |
| `domain` | string | ✅ | 任务领域：`planning`, `qa`, `reasoning`, `creative` |
| `source` | string | ✅ | 数据来源：`synthetic-gemini`, `curated`, `r1-distill`, `human` |
| `turns` | array | ✅ | 对话轮次 |
| `labels` | object | ✅ | 标注信息 |
| `reasoning` | object | ✅ | 推理过程（训练用） |

### turns 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `role` | string | ✅ | `user` 或 `model_target` |
| `text` | string | ✅ | 对话内容 |

**硬约束**:
- `model_target` 中只允许 `<ASK>` 或 `<FINAL>` 控制符
- **禁止**任何思维链文本出现在 `model_target` 中

### labels 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `ambiguity_types` | array | ✅ | 歧义类型：`["location", "budget", "diet", ...]` |
| `ask_required` | boolean | ✅ | 是否需要澄清 |
| `good_question_set` | array | ✅ | 优质澄清问题集合（1-3条） |
| `minimal_clarifications` | number | ✅ | 最少有效澄清数 |
| `oracle_answer` | string/null | ✅ | 预期最终答案（可选） |

### reasoning 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `think_stream` | string | ✅ | 摘要式思考流（非逐token CoT） |
| `actions` | array | ✅ | 推理动作序列 |

#### actions 枚举值

| 动作类型 | 说明 | 示例 |
|----------|------|------|
| `AWARE_GAP` | 检测到信息缺口 | `{"t": "AWARE_GAP", "vars": ["location", "budget"]}` |
| `ASK` | 发起澄清 | `{"t": "ASK", "q": "请确认城市和预算？"}` |
| `STOP_ASK` | 判定信息足够 | `{"t": "STOP_ASK"}` |
| `DERIVE` | 内部推导 | `{"t": "DERIVE", "note": "根据预算筛选选项"}` |
| `VERIFY` | 内部校验 | `{"t": "VERIFY", "note": "确认选项合理性"}` |
| `FINALIZE` | 产出最终答案 | `{"t": "FINALIZE"}` |

## 质量校验规则

### 必需字段校验
- 缺少 `labels.ask_required` 或 `reasoning.actions` 的样本判为**无效**
- `turns` 至少包含1个user轮次和1个model_target轮次

### 内容约束校验
- `model_target` 中不得出现思维链关键词：
  - 步骤/因为/首先/其次/综上所述
  - Let's think/Chain-of-Thought
  - 多段推理文本
- `good_question_set` 长度控制在1-3条
- `minimal_clarifications` ≥ 0

### 格式校验
- `id` 符合 `{domain}-{seq}` 格式
- `source` 为枚举值之一
- `domain` 为枚举值之一
- `ambiguity_types` 为预定义类型数组

## 正例

### 示例1: 餐厅推荐（需要澄清）
```json
{
  "id": "ALC-0019",
  "domain": "planning",
  "source": "human",
  "turns": [
    {"role": "user", "text": "帮我定周五晚餐，两个人，预算不要太贵。"},
    {"role": "model_target", "text": "<ASK> 你所在城市？预算上限？有无忌口？ </ASK>"}
  ],
  "labels": {
    "ambiguity_types": ["location", "budget", "diet"],
    "ask_required": true,
    "good_question_set": ["所在城市", "预算上限", "饮食禁忌"],
    "minimal_clarifications": 2,
    "oracle_answer": null
  },
  "reasoning": {
    "think_stream": "用户未指定城市、预算上限和饮食偏好，这些都是餐厅推荐的关键信息",
    "actions": [
      {"t": "AWARE_GAP", "vars": ["location", "budget", "diet"]},
      {"t": "ASK", "q": "请确认城市、预算上限和饮食禁忌？"},
      {"t": "STOP_ASK"}
    ]
  }
}
```

### 示例2: 直接回答（无需澄清）
```json
{
  "id": "ALC-0020",
  "domain": "qa",
  "source": "curated",
  "turns": [
    {"role": "user", "text": "北京今天的天气怎么样？"},
    {"role": "model_target", "text": "<FINAL> 北京今天晴天，温度15-25℃，空气质量良好。 </FINAL>"}
  ],
  "labels": {
    "ambiguity_types": [],
    "ask_required": false,
    "good_question_set": [],
    "minimal_clarifications": 0,
    "oracle_answer": "北京今天晴天，温度15-25℃，空气质量良好。"
  },
  "reasoning": {
    "think_stream": "问题信息完整，无需澄清，可直接回答",
    "actions": [
      {"t": "AWARE_GAP", "vars": []},
      {"t": "STOP_ASK"},
      {"t": "FINALIZE"}
    ]
  }
}
```

## 反例

### 反例1: 思维链泄漏到model_target
```json
{
  "turns": [
    {"role": "user", "text": "帮我选餐厅"},
    {"role": "model_target", "text": "首先，用户没有说所在城市，其次预算也不清楚，最后饮食偏好也没提。所以我需要先问这些问题。<ASK> 你在哪个城市？预算多少？有什么忌口？ </ASK>"}
  ]
}
```
❌ **问题**: 思维链文本"首先、其次、最后"出现在`model_target`中

### 反例2: 硬编码规则
```json
{
  "reasoning": {
    "think_stream": "检测到关键词'餐厅'，触发位置+预算+忌口模板",
    "actions": [{"t": "ASK", "q": "模板：位置+预算+忌口"}]
  }
}
```
❌ **问题**: 硬编码规则"检测到关键词'餐厅'就触发模板"

### 反例3: 缺少必需字段
```json
{
  "id": "ALC-0021",
  "domain": "planning",
  "turns": [...],
  "reasoning": {
    "think_stream": "..."
    // 缺少 actions 字段
  }
}
```
❌ **问题**: 缺少必需的 `reasoning.actions` 字段

## 历史写回规则

### 私有思考流处理
- `<think> ... </think>` 仅在训练/评测时可见
- 对话历史**不包含**思考流内容
- 仅保留 `<ASK>` 和 `<FINAL>` 控制符

### 示例转换
**原始输出**:
```
<think>用户没说城市和预算，需要澄清</think>
<ASK>你在哪个城市？预算多少？</ASK>
```

**写回历史**:
```
<ASK>你在哪个城市？预算多少？</ASK>
```

## 实现注意事项

1. **解析器实现**: 参考 `src/runtime/reasoning_parser.py`
2. **校验工具**: 使用 `tools/validate_dataset.py` 进行质量检查
3. **泄漏检测**: 使用 `tools/scan_for_cot_leakage.py` 扫描思维链泄漏
4. **加载器**: `src/data/loader.py` 负责读取和校验v1.1格式数据

## 版本历史

- **v1.0**: 基础澄清问答格式
- **v1.1**: 引入推理动作序列，支持私有思考流，强化质量约束
