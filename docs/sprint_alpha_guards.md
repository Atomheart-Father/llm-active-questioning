# Sprint-α 硬闸门系统

## 概述

Sprint-α 实现了三道硬闸门，确保在进入训练/评测前所有条件都已满足：

1. **模型真伪 & 可用性**：验证模型真实性和推理能力
2. **环境合规**：检查环境变量和密钥配置
3. **数据就绪度**：验证数据集质量和规模

## 快速开始

### 1. 环境配置

复制模板创建 `.env` 文件：

```bash
cp .env.template .env
# 编辑 .env 文件，填入实际的API密钥和配置
```

必需的环境变量：
- `GEMINI_API_KEY` - Gemini API密钥
- `DeepSeek_API_KEY` - DeepSeek API密钥
- `HF_TOKEN` - HuggingFace访问令牌
- `MODEL_NAME` - 模型名称（如：`Qwen/Qwen3-4B-Thinking-2507`）

### 2. 运行完整检查

```bash
make all-checks
```

这将依次运行：
- 模型真伪探针
- 环境合规检查
- 数据就绪度检查

### 3. 查看报告

检查完成后，查看生成的报告：

```bash
ls reports/
# model_sanity.md      - 模型检查报告
# env_check.md         - 环境检查报告
# data_overview.md     - 数据检查报告
# provenance.jsonl     - 出处跟踪记录
```

## 单独检查

### 模型真伪探针

```bash
make sanity
# 或
python tools/model_sanity_probe.py
```

**检查内容**：
- 提供方识别（HF/API）
- 连通性和权限验证
- 推理探针测试
- 思考流和控制符支持

### 环境合规检查

```bash
make env-check
# 或
python tools/env_guard.py
```

**检查内容**：
- 必需环境变量存在性
- 密钥格式验证
- 掩码处理（仅显示末4位）

### 数据就绪度检查

```bash
make data-check
# 或
python tools/dataset_gate.py
```

**检查内容**：
- 数据结构合法性
- CoT泄漏检测
- 样本规模阈值（默认≥8）
- 详细统计报告

## 思维链防护

### 生产模式（默认）

```bash
python tools/thought_leakage_guard.py
```

在生产模式下，`<think>` 标签会被自动移除。

### 研究模式

```bash
THOUGHT_IN_HISTORY=true python tools/thought_leakage_guard.py
```

研究模式下保留思考流，用于离线分析。

## 故障排除

### 常见问题

1. **ModuleNotFoundError**
   ```bash
   PYTHONPATH=/path/to/project python tools/model_sanity_probe.py
   ```

2. **环境变量缺失**
   - 检查 `.env` 文件是否存在
   - 确认所有必需变量都已设置
   - 运行 `make env-check` 验证

3. **模型连通性失败**
   - 检查API密钥是否正确
   - 验证网络连通性
   - 确认模型名称格式

4. **数据检查失败**
   - 运行 `python tools/validate_dataset.py data/seed/ALC/seed.jsonl`
   - 检查CoT泄漏：`python tools/scan_for_cot_leakage.py data/seed/`

### 调试模式

启用详细日志：

```bash
DEBUG=1 make sanity
DEBUG=1 python tools/model_sanity_probe.py
```

## 配置选项

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `THOUGHT_IN_HISTORY` | `false` | 是否在历史中保留思考流 |
| `DATASET_MIN_SAMPLES` | `8` | 数据集最小样本数阈值 |
| `DEBUG` | - | 启用调试模式 |

### 数据集配置

当前支持的数据集：
- `data/seed/ALC/seed.jsonl` - 主动澄清学习样本
- `data/seed/AR/seed.jsonl` - 推理增强样本

## 安全说明

- ✅ 所有密钥值都经过掩码处理
- ✅ 报告不包含完整密钥信息
- ✅ 环境变量仅在运行时读取
- ✅ 日志中只显示密钥末4位
- ✅ 支持Fail Closed策略

## 集成说明

### CI/CD 集成

建议在CI流水线中添加：

```yaml
- name: Run Sanity Checks
  run: make all-checks
```

### 开发工作流

```bash
# 开发前检查
make all-checks

# 只检查环境
make env-check

# 调试模式
DEBUG=1 make sanity
```

## 输出文件

### 报告文件

1. **`reports/model_sanity.md`**
   - 模型提供方和版本信息
   - 连通性和权限状态
   - 推理探针结果
   - 设备和性能信息

2. **`reports/env_check.md`**
   - 环境变量存在性检查
   - 掩码后的密钥验证
   - 读取时间戳

3. **`reports/data_overview.md`**
   - 数据集规模统计
   - 领域和来源分布
   - 质量指标汇总

4. **`reports/provenance.jsonl`**
   - JSONL格式的完整检查记录
   - 用于审计和追溯

## 验收标准

✅ **模型真伪检查通过**
- 提供方正确识别
- 连通性和权限验证成功
- 推理探针返回有效响应
- 支持思考流和控制符

✅ **环境合规检查通过**
- 所有必需环境变量存在
- 密钥格式正确
- 报告中密钥已掩码

✅ **数据就绪度检查通过**
- 数据结构完全合法
- 无CoT泄漏
- 样本数满足阈值要求
- 统计报告完整生成

✅ **思维链防护正常**
- 生产模式下自动剥离思考流
- 研究模式可选择保留
- 无泄漏到对话历史

---

**通过所有检查后，才能进入训练和强化学习阶段。**
