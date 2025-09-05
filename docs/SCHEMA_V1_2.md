# Schema v1.2 规范文档

## 概述

Schema v1.2 在 v1.1 基础上增加了三个核心增强模块：
- **ATAC (Active Task Ambiguity Clarification)**: 澄清枚举与分支映射
- **ToC (Tree of Clarification)**: 轻量澄清树结构
- **FT-Pref (Fine-tuning Preferences)**: 偏好成对学习

## 核心数据结构

### 基础字段 (继承自 v1.1)

```json
{
  "turns": [
    {"role": "user", "text": "用户查询"},
    {"role": "model_target", "text": "<ASK>澄清问题</ASK>"}
  ],
  "labels": {
    "ask_required": true,
    "ambiguity_types": ["person", "time"],
    "good_question_set": ["问题1", "问题2"],
    "minimal_clarifications": 2
  },
  "reasoning": {
    "actions": ["AWARE_GAP", "ASK", "STOP_ASK"]
  },
  "source": "synthetic-gemini"
}
```

## 新增字段详解

### 1. ATAC 增强字段

#### ambiguity_types (歧义类型枚举)
- **类型**: `string[]`
- **枚举值**: `["person", "time", "location", "preference", "budget", "method", "scope", "context", "quantity", "quality"]`
- **约束**: 最多5个，最少0个
- **用途**: 标准化歧义分类，便于批量分析

#### ask_options (澄清选项)
- **类型**: `string[]`
- **约束**: 每个选项1-100字符，最多5个
- **用途**: 提供澄清问题的多个选项分支

#### branch_map (分支映射)
- **类型**: `object[]`
- **结构**:
  ```json
  [
    {"option": "预算500元以内", "final_id": "F1"},
    {"option": "预算1000元以内", "final_id": "F2"}
  ]
  ```
- **用途**: 将澄清选项映射到最终答案ID

### 2. ToC 增强字段

#### clarify_tree (澄清树)
- **类型**: `object`
- **结构**:
  ```json
  {
    "depth": 2,
    "nodes": [
      {
        "id": "Q1",
        "children": ["Q1A", "Q1B"]
      }
    ]
  }
  ```
- **约束**: 深度≤3，分支数合理
- **用途**: 表示多轮澄清的树状结构

#### evidence_ids (证据指针)
- **类型**: `string[]`
- **格式**: `"dataset:id#sentence"` (如 `"hotpot:d123#sent5"`)
- **用途**: 指向支撑澄清的证据来源

### 3. FT-Pref 增强字段

#### preference (偏好数据)
- **类型**: `object`
- **结构**:
  ```json
  {
    "direct_answer": {"score": 0.41},
    "clarify_then_answer": {"score": 0.72},
    "label": "clarify"
  }
  ```
- **用途**: 支持DPO/IPO训练的偏好学习

### 4. 紧凑推理增强

#### compact_rationale (紧凑理据)
- **类型**: `object`
- **结构**:
  ```json
  {
    "connectors": ["if", "then", "therefore"],
    "steps": 3
  }
  ```
- **用途**: 量化推理的紧凑程度，避免冗长思维链

## 质量控制规则

### 1. 格式严格性
- **JSON-only**: 必须是单个有效的JSON对象
- **单控制符**: `<ASK>` 或 `<FINAL>` 二选一，不可同时出现
- **无礼貌语**: 禁止"谢谢"、"请"等礼貌用语
- **无CoT泄漏**: 禁止思维链文本泄漏到输出

### 2. 内容一致性
- **Branch Consistency**: `branch_map`必须与可能的`<FINAL>`分支一一映射
- **Evidence Coverage**: `evidence_ids`必须指向有效证据
- **Preference Validity**: `preference.label`必须与最高分选项一致

### 3. 结构约束
- **Tree Depth**: `clarify_tree.depth` ≤ 3
- **Options Count**: `ask_options` ≤ 5个
- **Ambiguity Types**: `ambiguity_types` ≤ 5个，来自预定义枚举

## 任务类型适配

### ALC (Active Learning Clarification)
- **必需字段**: `ambiguity_types`, `ask_options`, `branch_map`
- **质量指标**: Coverage@ASK ≥ 95%, Branch-Consistency ≥ 90%
- **多样性**: Distinct-2 ≥ 0.85 (ASK句式)

### AR (Active Reasoning)
- **必需字段**: `clarify_tree`, `evidence_ids`, `oracle_answer`
- **质量指标**: Disambig-F1 ≥ 0.7, Evidence命中率 ≥ 95%
- **紧凑性**: CompactnessScore 在合理区间

### RSD (Reasoning Step Demonstration)
- **新增字段**: `prediction.next_observation` (结构化短槽)
- **推理增强**: `reasoning.actions[t+1]` 预测
- **约束**: 不输出自然语言思维链

## 向后兼容性

Schema v1.2 完全向后兼容 v1.1：
- 所有 v1.1 字段保持不变
- 新增字段均为可选
- 现有验证逻辑继续有效
- 渐进式迁移支持

## 实现指南

### 验证器更新
```python
def validate_schema_v1_2(sample: Dict) -> Tuple[bool, List[str]]:
    # 基础v1.1验证
    valid, errors = validate_schema_v1_1(sample)

    # 新增字段验证
    errors.extend(validate_atac_fields(sample))
    errors.extend(validate_toc_fields(sample))
    errors.extend(validate_pref_fields(sample))

    return len(errors) == 0, errors
```

### 生成器适配
- ATAC-ALC: 增加枚举澄清逻辑
- ToC-AR: 实现树状澄清结构
- RSD: 添加预测性推理
- FT-Pref: 并行生成偏好对

## 迁移路径

1. **Phase 1**: 现有v1.1数据保持兼容
2. **Phase 2**: 新生成数据采用v1.2格式
3. **Phase 3**: 工具链全面支持v1.2特性
4. **Phase 4**: 弃用v1.1，统一使用v1.2

## 附录

### 歧义类型枚举表
- `person`: 人员相关歧义
- `time`: 时间相关歧义
- `location`: 地点相关歧义
- `preference`: 偏好相关歧义
- `budget`: 预算相关歧义
- `method`: 方法相关歧义
- `scope`: 范围相关歧义
- `context`: 上下文相关歧义
- `quantity`: 数量相关歧义
- `quality`: 质量相关歧义

### 推理连接词枚举
- `if`, `then`, `because`, `therefore`
- `compare`, `contrast`
- `and`, `or`, `but`
