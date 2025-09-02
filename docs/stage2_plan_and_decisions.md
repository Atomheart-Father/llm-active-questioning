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
- **当前使用**: 200条样本，已保存至 `data/raw/ambigqa/20250902/ambigqa_200.jsonl`

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

TODO: 待补充

---

## 自动质检规则 v1

TODO: 待补充

---

## 抽样审计流程 v1

TODO: 待补充
