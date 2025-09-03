# 数据生成汇总报告 - 2025-09-03

## 生成统计
- **总样本数**: 5
- **ALC样本**: 5 (目标: 5)
- **AR样本**: 0 (目标: 3)
- **RSD样本**: 0 (目标: 2)

## 配置信息
- **温度**: 0.7
- **批次日期**: 2025-09-03
- **最大重试次数**: 3
- **速率限制延迟**: 1.0s

## 输出文件
- `data/gen/2025-09-03/ALC/part-001.jsonl`
- `data/gen/2025-09-03/AR/part-001.jsonl`
- `data/gen/2025-09-03/RSD/part-001.jsonl`
- `reports/provenance.jsonl` (追加)

## 下一步
1. 运行质量检查: `python tools/dataset_gate.py`
2. 运行去重检查: `python tools/deduplication.py`
3. 更新数据概览: `python tools/validate_dataset.py data/gen/2025-09-03/*/part-*.jsonl`
