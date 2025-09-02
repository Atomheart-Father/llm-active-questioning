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

## 自动质检规则 v1

TODO: 待补充

---

## 抽样审计流程 v1

TODO: 待补充
