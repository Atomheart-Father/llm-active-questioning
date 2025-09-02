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
- **示例**: `sampling_review_000.md`, `sampling_review_001.md`, `sampling_review_002.md`
- **作用**: 各分片的抽样审计报告

---

## 自动质检规则 v1

TODO: 待补充

---

## 抽样审计流程 v1

TODO: 待补充
