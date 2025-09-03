# Stage 2: 数据管线重建与主动澄清实验

## 数据源与许可

### 当前使用的真实数据集

#### 1. AmbigQA（歧义问答）
- **Hugging Face ID**: `sewon/ambig_qa` (config: light, split: train)
- **描述**: 歧义问题数据集，包含需要澄清的模糊问题
- **许可**: CC BY-SA 3.0
- **来源URL**: https://huggingface.co/datasets/sewon/ambig_qa
- **后备下载**: https://nlp.cs.washington.edu/ambigqa/ (UW官方页面)
- **字段结构**: `id`, `question`, `annotations` (light配置)
- **当前使用**: 2000条样本，已保存至 `data/raw/ambigqa/20250902/ambigqa_200.jsonl` + `data/raw/ambigqa/20250903/ambigqa_2000.jsonl`

#### 2. GSM8K（数学推理）
- **Hugging Face ID**: `openai/gsm8k`
- **描述**: 数学推理数据集，适合测试澄清能力
- **许可**: MIT
- **来源URL**: https://huggingface.co/datasets/openai/gsm8k
- **字段结构**: `id`, `question`, `answer`, `solution`
- **当前使用**: 200条样本，已保存至 `data/raw/gsm8k/20250902/gsm8k_20250902.jsonl`

#### 3. 扩展数据集清单（预留）

##### HotpotQA（多跳推理）
- **Hugging Face ID**: `hotpotqa/hotpot_qa` (distractor config)
- **许可**: CC-BY-SA-4.0
- **来源**: https://huggingface.co/datasets/hotpotqa/hotpot_qa

##### ASQA（Ambiguous Long-Form QA）
- **Hugging Face ID**: `din0s/asqa`
- **许可**: MIT
- **来源**: https://huggingface.co/datasets/din0s/asqa

##### StrategyQA（隐含多步常识推理）
- **Hugging Face ID**: `voidful/StrategyQA`
- **许可**: CC-BY-4.0
- **来源**: https://huggingface.co/datasets/voidful/StrategyQA

### 数据获取原则

1. **零容忍模拟**: 严格禁止任何形式的模拟、自造或合成数据
2. **来源可追溯**: 所有数据必须有明确的Hugging Face ID或官方URL
3. **许可合规**: 优先使用MIT/Apache等宽松许可的数据集
4. **字段原样**: 下载后字段名和结构保持不变，不进行任何改写
5. **问题上报**: 遇到网络或权限问题必须立即上报，不得变通

### Provenance追踪

所有数据集样本在 `data/processed/active_qa_v1/provenance.csv` 中记录：
- `uid`: 唯一标识符（MD5哈希）
- `source_dataset`: 数据集名称
- `source_id`: 原始样本ID
- `url_or_path`: Hugging Face路径或URL
- `license`: 许可信息
- `created_at`: 创建时间戳
- `dataset_hf_id`: Hugging Face数据集ID（如`sewon/ambig_qa`）
- `source_config`: 数据集配置（如`light`, `full`）
- `split`: 数据分割（如`train`, `validation`）

---

## 合成策略 v1

### 策略概述
基于 AmbigQA 数据集进行主动澄清问句合成，严格遵循"零模拟"原则，仅对原始数据进行字段映射和清洗，不创造任何新内容。

### 缺口识别
从原始 AmbigQA 样本的 `question` + `annotations.qaPairs` 中提取歧义缺口：
- **实体歧义**: 人名、地名、组织名等指代不清
- **时间歧义**: 历史时期、日期范围等模糊表达
- **地点歧义**: 地理位置、场所等空间概念不清
- **范围歧义**: 数量、程度、条件等限定不清

### 澄清问句生成
- **输入**: 原始 `question` + `annotations.qaPairs.question[]`
- **处理**: 直接使用 qaPairs 中的子问题，不创造新问句
- **清洗**: 去重、截断过长问题（最大512字符）、去除噪声
- **输出**: 1–3 个澄清问句，按优先级排序

### 答案枚举生成
- **输入**: `annotations.qaPairs.answer[]`
- **处理**: 仅复述已有答案，不外推新事实
- **格式**: "若A则…；若B则…；若C则…" 的枚举形式
- **约束**: 严格对应每个澄清问句的答案，不添加解释

---

## 多跳推理合成策略 v1（HotpotQA）

### 总体策略
- **目标**: 将多跳推理问题转化为需要澄清的多证据链路问题
- **输入**: HotpotQA的`question`、`context`、`supporting_facts`、`type`
- **零模拟**: 仅基于原始数据进行字段映射和信息提取

### 缺口识别逻辑
1. **多证据分析**: 识别`supporting_facts`中涉及的多个文档
2. **信息链路**: 分析问题所需的推理步骤和中间证据
3. **缺口类型**:
   - 证据文档引用不足
   - 中间推理步骤不明确
   - 答案依赖于特定证据组合

### 澄清问句生成
- **数量**: 1–2个核心澄清问句
- **质量标准**: 直接针对多跳推理的关键证据缺口
- **示例**:
  - 输入问题: "Which magazine was started first Arthur's Magazine or First for Women?"
  - 澄清问句: "What is the publication date of Arthur's Magazine?" + "What is the publication date of First for Women?"

### 答案枚举策略
- **来源**: 基于`supporting_facts`中的关键信息
- **格式**: "若基于[证据A]则[答案1]；若基于[证据B]则[答案2]"
- **约束**: 只使用原始数据中的事实，不进行额外推理

### 上下文提供
- **内容**: 相关的支持事实片段
- **格式**: 结构化证据引用，便于理解推理链路

### 元数据字段
- `task_type`: "multihop"
- `source`: "hotpotqa"
- `licensing`: "CC-BY-SA-4.0"

---

## 长答案合成策略 v1（ASQA）

### 总体策略
- **目标**: 将长答案问答转化为需要澄清的复杂信息整合
- **输入**: ASQA的`ambiguous_question`、`annotations`、`qa_pairs`
- **零模拟**: 仅基于原始数据进行字段映射和信息抽取

### 缺口识别逻辑
1. **长答案分析**: 识别`qa_pairs`中包含的长答案内容
2. **歧义类型**: 分析问题可能存在的不同解释角度
3. **信息密度**: 识别长答案中需要澄清的关键信息点

### 澄清问句生成
- **数量**: 2–3个针对长答案不同方面的澄清问句
- **质量标准**: 覆盖长答案的核心信息维度
- **示例**:
  - 输入问题: "When does the new bunk'd come out?"
  - 澄清问句: "Which season of Bunk'd are you referring to?" + "What type of release are you asking about (TV/premiere)?"

### 答案枚举策略
- **来源**: 基于`qa_pairs`中的不同答案变体
- **格式**: "若[澄清维度A]则[详细答案A]；若[澄清维度B]则[详细答案B]"
- **约束**: 保持原始长答案的完整性和准确性

### 上下文提供
- **内容**: 相关的背景信息和答案变体说明
- **格式**: 结构化信息，便于理解不同答案的区别

### 元数据字段
- `task_type`: "longform"
- `source`: "asqa"
- `licensing`: "MIT"

---

## 扩展数据集预留策略（StrategyQA）

### 总体策略
- **目标**: 将隐含多步常识推理转化为需要澄清的推理链路
- **输入**: StrategyQA的`question`、`answer`、`facts`
- **零模拟**: 基于常识推理链路的字段映射

### 缺口识别逻辑
- **隐含推理**: 识别问题中未明确说明的推理步骤
- **常识链路**: 分析所需的背景知识和推理路径
- **证据需求**: 确定澄清所需的中间推理步骤

### 上下文提供
- **来源**: 直接引用 `annotations` 中的可用信息
- **内容**: 问题相关的背景信息、约束条件等
- **格式**: 结构化文本，便于后续处理

### 元数据记录
- `gen_meta.generator_version`: "stage2_data_synth_v1"
- `gen_meta.generation_timestamp`: ISO 8601 格式时间戳
- `gen_meta.seed`: 固定种子值（如 20240902）
- `gen_meta.source_dataset`: "ambigqa"
- `gen_meta.source_config`: "light"
- `gen_meta.quality_score`: 预留字段（当前设为 null）

### 字段映射表

| 目标字段 | 来源 | 说明 |
|---------|------|------|
| `uid` | 生成 | MD5(源ID + 时间戳) |
| `user_query` | `question` | 原始歧义问题 |
| `needs_clarification` | 固定值 | `true` |
| `clarification_questions` | `qaPairs.question[]` | 清洗后的澄清问句列表 |
| `provided_context` | `annotations` | 相关上下文信息 |
| `assistant_response` | `qaPairs.answer[]` | 枚举式最终答案 |
| `task_type` | 固定值 | `"qa"` |
| `source` | 固定值 | `"ambigqa"` |
| `licensing` | 固定值 | `{"license_type": "cc-by-sa-3.0"}` |
| `gen_meta` | 生成 | 上述元数据字段 |

### 质量保证
- **可追溯性**: 每个输出字段可回溯到原始数据
- **无新增内容**: 不创造任何新事实、解释或问句
- **格式一致性**: 严格遵循 schema.json 定义
- **种子固定**: 使用固定随机种子保证结果可重现

---

## 指标与审计命名规范

### 主指标文件
- **路径**: `data/processed/active_qa_v1/metrics.json`
- **作用**: 累计所有shard的总计指标
- **必含字段**:
  - `total_samples`: 总样本数
  - `near_duplicates.duplicate_ratio`: 近重复率
  - `alignment_stats.{alignment_ok_count, alignment_error_count, alignment_ok_percentage}`: 对齐统计

### 分片指标文件
- **命名模式**: `data/processed/active_qa_v1/metrics_shard_{XXX}.json`
- **示例**: `metrics_shard_000.json`, `metrics_shard_001.json`, `metrics_shard_002.json`
- **作用**: 各分片的独立质量指标

### 审计文件
- **命名模式**: `data/processed/active_qa_v1/audit/sampling_review_{XXX}.md`
- **编号文件**: 仅对应具体分片（如 `sampling_review_000.md`, `sampling_review_001.md`, `sampling_review_002.md`）
- **汇总文件**: 使用非编号命名（如 `sampling_review_ambigqa_cumulative.md`）
- **作用**: 各分片的抽样审计报告或跨分片的汇总审计
- **重要说明**: 汇总文件避免使用编号命名，以免与分片编号冲突（如003应预留给HotpotQA分片）

---

## 自动质检规则 v1

TODO: 待补充

---

## 抽样审计流程 v1

TODO: 待补充

---

## ASQA 字段映射与许可

### 数据集许可
- **许可类型**: Apache-2.0
- **来源**: [Hugging Face din0s/asqa](https://huggingface.co/datasets/din0s/asqa)
- **使用约束**: 商业使用友好，修改和分发自由

### 原始字段结构
ASQA数据集包含以下关键字段：
- `sample_id`: 样本唯一标识符
- `ambiguous_question`: 模糊问题文本
- `annotations`: 包含`knowledge`、`long_answer`、`qa_pairs`等
- `wikipages`: 相关维基页面信息
- `qa_pairs`: 问题-答案对列表，包含上下文和答案

### 字段映射表

| ASQA字段 | 目标schema字段 | 映射规则 |
|---------|---------------|---------|
| `ambiguous_question` | `user_query` | 直接复制 |
| `long_answer` | `provided_context` | 作为上下文信息 |
| `qa_pairs[].question` | `clarification_questions` | 提取1-2个关键澄清问句 |
| `qa_pairs[].short_answers` | `assistant_response` | 枚举式整合答案 |
| 自动生成 | `uid` | 基于`sample_id`生成 |
| 自动生成 | `task_type` | 设置为`"longform"` |
| 自动生成 | `licensing` | 设置为`"apache-2.0"` |
| 自动生成 | `source` | 设置为`"asqa"` |

### 回应约束（不引入新事实）
1. **仅枚举**: 只使用`qa_pairs`中的`short_answers`，不生成新内容
2. **格式统一**: "若问题A则答案1；若问题B则答案2"的枚举格式
3. **信息完整性**: 保持原始答案的准确性和完整性
4. **可追溯性**: 所有答案都能追溯到原始`qa_pairs`数据

### 澄清问句生成策略
1. **基于ambiguity**: 从`ambiguous_question`识别歧义点
2. **限制数量**: 每个样本最多2个澄清问句
3. **质量优先**: 确保问句直接针对答案差异
4. **零生成**: 不创造新的问题内容，仅重组现有信息

### 合成策略预检
- ✅ 许可兼容：Apache-2.0与现有数据集兼容
- ✅ 字段结构清晰：映射关系明确，无歧义
- ✅ 零模拟保证：所有内容均可追溯到原始数据
- ✅ 质量可控：通过枚举格式确保一致性

---

## 长答案合成策略 v1（ASQA）

### 总体策略
- **目标**: 将长答案问题转化为需要澄清的答案枚举
- **输入**: ASQA的`ambiguous_question`、`qa_pairs`、`long_answer`
- **零模拟**: 仅基于原始数据进行字段映射和答案枚举

### 缺口识别逻辑
1. **歧义识别**: 从`ambiguous_question`识别多重解释可能
2. **答案多样性**: 分析`qa_pairs`中的不同答案选项
3. **信息密度**: 识别`long_answer`中的关键信息点

### 澄清问句生成
- **数量**: 1-2个核心澄清问句
- **质量标准**: 直接针对答案差异的关键问题
- **示例**:
  - 输入问题: "What type of radiation is used in x rays?"
  - 澄清问句: "What general type of radiation is used in x rays?" + "What are the two types of radiation used to produce x rays?"

### 答案枚举策略
- **格式**: "若问题A则答案1；若问题B则答案2"的枚举形式
- **内容**: 严格使用`qa_pairs.short_answers`，不添加新信息
- **完整性**: 确保覆盖所有主要答案选项

---

## 高强度样本扩产配方（Stage 2.1）

### 总体策略

基于当前质量评估（branch一致性42.6%为主要短板），制定高强度样本扩产策略，优先解决数据质量瓶颈，提高模型学习效果。

### 高强度样本定义

**选择器阈值**（满足≥3项判定为高强度）：
- ✅ **Clarification问≥2**: 澄清问数量≥2个
- ✅ **关键词计数≥8**: 澄清问包含关键词数量≥8个
- ✅ **跨句证据跨度≥2**: 证据引用跨度≥2个句子
- ✅ **枚举分支≥3**: 回答分支数量≥3个

**中等强度**: 满足2项条件
**低强度**: ≤1项条件

### 分桶采样策略

**训练集分布**:
- **高强度**: 50%（重点扩产区）
- **中强度**: 35%（保持平衡）
- **低强度**: 15%（控制比例）

**验证/测试集**:
- **等比例分层**: 确保各强度样本在验证/测试集中都有代表性
- **评测隔离**: 测试集中**严格禁止**任何合成样本，只使用`source ∈ {public,human}`

### Prompt套餐设计

#### 1. AmbigQA（歧义澄清场景）

**系统Prompt**:
```
你是歧义澄清专家。用户的问题可能有多种解释，你需要：
1. 识别歧义维度（实体/时间/地点/范围等）
2. 提出最少但互斥的澄清问句
3. 确保每个澄清问句都有明确的答案分支

输出格式：先列出歧义类型，再给出2-3个澄清问句，每个问句限制≤20字。
```

**用户Prompt模板**:
```
歧义问题：{question}

上下文：{annotations}

请生成澄清问句，确保：
- 覆盖所有主要歧义维度
- 问句互斥（答案不重叠）
- 每个问句都有明确的答案分支
```

**质量标准**:
- 澄清问覆盖率：≥95%
- Branch一致性：≥90%
- 冗余率：≤10%

#### 2. HotpotQA（多跳推理场景）

**系统Prompt**:
```
你是多跳推理专家。用户的问题需要多个证据链路，你需要：
1. 识别缺失的桥接证据
2. 提出针对桥接实体的澄清问句
3. 确保问句直接指向推理链路的关键节点

输出格式：基于supporting_facts分析，提出1-2个核心桥接问句。
```

**用户Prompt模板**:
```
多跳问题：{question}
支持事实：{supporting_facts}
问题类型：{type}

请生成澄清问句，重点关注：
- 缺失的中间实体
- 不明确的推理步骤
- 需要额外证据的推理链路
```

**质量标准**:
- 推理完整性：≥85%
- 证据相关性：≥90%
- Branch一致性：≥95%

#### 3. GSM8K（数学推理场景）

**系统Prompt**:
```
你是数学推理专家。用户的问题涉及数值计算，你需要：
1. 识别隐含的单位/取整/边界条件
2. 提出澄清数值假设的问句
3. 确保覆盖所有可能的数值解释

输出格式：基于问题分析，提出1-2个数值相关的澄清问句。
```

**用户Prompt模板**:
```
数学问题：{question}
推理步骤：{solution}

请生成澄清问句，重点关注：
- 隐含的单位假设
- 取整规则的不明确性
- 边界条件的模糊性
```

**质量标准**:
- 数值准确性：≥95%
- 推理完整性：≥90%
- Branch一致性：≥95%

### 扩产执行计划

#### Phase 1: 质量修复（Week 1-2）
- **目标**: 修复当前数据集的branch一致性问题
- **方法**: 重新生成不一致的643个样本
- **产出**: branch一致性提升至≥80%

#### Phase 2: 高强度扩产（Week 3-4）
- **目标**: 基于选择器扩产高强度样本
- **方法**:
  - AmbigQA: 扩产2000个高强度样本
  - HotpotQA: 扩产1000个高强度样本
  - GSM8K: 扩产800个高强度样本
- **产出**: 高强度样本比例达到50%

#### Phase 3: 均衡优化（Week 5-6）
- **目标**: 优化整体分布和质量平衡
- **方法**: 根据训练效果调整分桶比例
- **产出**: 最终训练集质量指标全部≥85%

### 质量守护机制

#### 1. 数据卡标注
每个样本必须包含：
- `source`: `{public|gemini|human}` - 严格区分来源
- `license`: 许可信息
- `created_at`: 生成时间戳
- `quality_score`: 自动计算的质量评分

#### 2. 去重与溯源
- **UID哈希**: 基于内容和时间戳生成唯一标识
- **语义去重**: 使用MinHash检测相似样本
- **溯源记录**: provenance.csv记录所有来源信息

#### 3. 评测集保护
- **合成隔离**: 测试集**绝对不包含**任何合成样本
- **来源限制**: 只使用`source ∈ {public,human}`的样本
- **比例控制**: 确保各难度级别都有代表性

### 监控与评估

#### 持续监控指标
- **Branch一致性**: 目标≥90%
- **澄清覆盖率**: 目标≥95%
- **冗余率**: 目标≤10%
- **长度控制**: P50≤50字符，P90≤100字符

#### 训练效果关联
- **收敛速度**: 高强度样本应加速模型收敛
- **泛化能力**: 多分支样本应提高推理能力
- **澄清质量**: 高质量澄清问应减少无效交互

### 风险控制

#### 1. 扩产安全
- **零模拟原则**: 严格禁止任何形式的合成数据生成
- **许可合规**: 所有扩产必须基于现有许可的数据
- **溯源完整**: 每个新样本都有完整的来源记录

#### 2. 质量保障
- **自动化检查**: CI集成质量验证
- **人工审核**: 高强度样本抽样审核
- **回滚机制**: 质量下降时可快速回滚

#### 3. 资源管理
- **渐进扩产**: 分阶段进行，避免一次性扩大量
- **优先级排序**: 优先扩产高影响力的样本类型
- **成本控制**: 评估扩产的计算和存储成本

---

## 总结

这个高强度样本扩产配方针对当前数据质量的主要短板（branch一致性42.6%），通过精确的选择器、优质的prompt套餐和严格的质量守护，旨在将数据质量提升至工业级标准，为后续的强化学习训练奠定坚实基础。
