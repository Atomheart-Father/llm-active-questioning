#!/usr/bin/env python3
"""
Stage 2 Global Deduplication and Train/Dev/Test Splits
对已合成的分片进行全局去重，然后按task_type分层切分为train/dev/test
"""

import json
import hashlib
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple
import random

def load_all_shards(base_path: Path) -> List[Dict]:
    """加载所有已合成的分片样本"""
    shards = [
        'shard-000', 'shard-001', 'shard-002', 'shard-003',
        'shard-004', 'shard-004a', 'shard-005'
    ]

    all_samples = []
    for shard_name in shards:
        shard_file = base_path / f"{shard_name}.jsonl"
        if shard_file.exists():
            print(f"📂 加载分片: {shard_name}")
            with open(shard_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():
                        try:
                            sample = json.loads(line.strip())
                            sample['_shard'] = shard_name
                            sample['_line_num'] = line_num
                            all_samples.append(sample)
                        except json.JSONDecodeError as e:
                            print(f"⚠️  跳过 {shard_name} 第{line_num}行: {e}")

    print(f"✅ 加载完成: {len(all_samples)} 个样本")
    return all_samples

def compute_text_hash(text: str) -> str:
    """计算文本的哈希值用于去重"""
    # 简单标准化：去除多余空格，转换为小写
    normalized = ' '.join(text.lower().split())
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()

def deduplicate_samples(samples: List[Dict], threshold: float = 0.9) -> Tuple[List[Dict], Dict]:
    """
    基于文本相似度的去重
    这里使用简单的哈希去重，实际项目中可以集成MinHash等更复杂的算法
    """
    print("🔍 开始全局去重...")

    # 按task_type分组
    samples_by_type = defaultdict(list)
    for sample in samples:
        task_type = sample.get('task_type', 'unknown')
        samples_by_type[task_type].append(sample)

    deduped_samples = []
    duplicates_removed = 0

    # 为每个task_type分别去重
    for task_type, type_samples in samples_by_type.items():
        print(f"  处理 {task_type}: {len(type_samples)} 个样本")

        # 使用简单哈希去重（实际项目中应使用更复杂的相似度算法）
        seen_hashes = set()
        type_deduped = []

        for sample in type_samples:
            # 基于clarification_questions和assistant_response生成哈希
            questions = sample.get('clarification_questions', [])
            response = sample.get('assistant_response', '')

            # 组合关键字段进行哈希
            combined_text = ' '.join(questions) + ' ' + response
            text_hash = compute_text_hash(combined_text)

            if text_hash not in seen_hashes:
                seen_hashes.add(text_hash)
                type_deduped.append(sample)
            else:
                duplicates_removed += 1

        deduped_samples.extend(type_deduped)
        print(f"    {task_type} 去重后: {len(type_deduped)} 个样本")

    dedup_stats = {
        'original_count': len(samples),
        'deduped_count': len(deduped_samples),
        'duplicates_removed': duplicates_removed,
        'deduplication_ratio': duplicates_removed / len(samples) if samples else 0
    }

    print("✅ 去重完成:")
    print(f"  原样本数: {dedup_stats['original_count']}")
    print(f"  去重后样本数: {dedup_stats['deduped_count']}")
    print(".3f")

    return deduped_samples, dedup_stats

def stratified_split(samples: List[Dict], train_ratio: float = 0.8,
                    dev_ratio: float = 0.1, test_ratio: float = 0.1) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    按task_type分层切分数据集
    """
    print("✂️  开始分层切分...")

    # 按task_type分组
    samples_by_type = defaultdict(list)
    for sample in samples:
        task_type = sample.get('task_type', 'unknown')
        samples_by_type[task_type].append(sample)

    train_samples = []
    dev_samples = []
    test_samples = []

    # 为每个task_type分别切分
    for task_type, type_samples in samples_by_type.items():
        print(f"  切分 {task_type}: {len(type_samples)} 个样本")

        # 设置随机种子确保可重现
        random.seed(42)

        # 随机打乱
        shuffled = type_samples.copy()
        random.shuffle(shuffled)

        # 计算切分点
        n_total = len(shuffled)
        n_train = int(n_total * train_ratio)
        n_dev = int(n_total * dev_ratio)
        n_test = n_total - n_train - n_dev

        # 切分
        type_train = shuffled[:n_train]
        type_dev = shuffled[n_train:n_train + n_dev]
        type_test = shuffled[n_train + n_dev:]

        train_samples.extend(type_train)
        dev_samples.extend(type_dev)
        test_samples.extend(type_test)

        print(f"    {task_type} - 训练: {len(type_train)}, 验证: {len(type_dev)}, 测试: {len(type_test)}")

    # 最终随机打乱以避免按task_type排序
    random.seed(42)
    random.shuffle(train_samples)
    random.shuffle(dev_samples)
    random.shuffle(test_samples)

    print("✅ 切分完成:")
    print(f"  训练集: {len(train_samples)} 样本 ({len(train_samples)/len(samples)*100:.1f}%)")
    print(f"  验证集: {len(dev_samples)} 样本 ({len(dev_samples)/len(samples)*100:.1f}%)")
    print(f"  测试集: {len(test_samples)} 样本 ({len(test_samples)/len(samples)*100:.1f}%)")

    return train_samples, dev_samples, test_samples

def save_split_to_file(samples: List[Dict], output_path: Path, split_name: str):
    """保存切分结果到文件"""
    print(f"💾 保存{split_name}集到: {output_path}")

    with open(output_path, 'w', encoding='utf-8') as f:
        for sample in samples:
            # 移除内部使用的字段
            clean_sample = {k: v for k, v in sample.items() if not k.startswith('_')}
            f.write(json.dumps(clean_sample, ensure_ascii=False) + '\n')

    print(f"  ✅ {split_name}集保存完成: {len(samples)} 样本")

def update_metrics_with_splits(metrics_path: Path, train_count: int, dev_count: int, test_count: int, dedup_stats: Dict):
    """更新metrics.json中的splits信息"""
    print("📊 更新metrics.json的splits信息...")

    # 读取现有metrics
    with open(metrics_path, 'r', encoding='utf-8') as f:
        metrics = json.load(f)

    # 添加splits信息
    metrics['splits'] = {
        'train': {
            'count': train_count,
            'percentage': train_count / (train_count + dev_count + test_count) * 100
        },
        'dev': {
            'count': dev_count,
            'percentage': dev_count / (train_count + dev_count + test_count) * 100
        },
        'test': {
            'count': test_count,
            'percentage': test_count / (train_count + dev_count + test_count) * 100
        }
    }

    # 添加去重统计
    metrics['deduplication'] = dedup_stats

    # 保存更新后的metrics
    with open(metrics_path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    print("✅ metrics.json更新完成")

def main():
    """主函数"""
    print("🚀 Stage 2 全局去重 + 分层切分 - 开始执行")
    print("=" * 60)

    # 设置路径
    shards_path = Path("data/interim/shards/stage2_v1")
    output_path = Path("data/processed/active_qa_v1")
    metrics_path = output_path / "metrics.json"

    # 确保输出目录存在
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. 加载所有分片
    print("📂 第一步: 加载所有分片")
    all_samples = load_all_shards(shards_path)

    if not all_samples:
        print("❌ 错误: 未找到任何样本文件")
        return 1

    # 2. 全局去重
    print("\n🔍 第二步: 全局去重")
    deduped_samples, dedup_stats = deduplicate_samples(all_samples, threshold=0.9)

    # 3. 分层切分
    print("\n✂️  第三步: 分层切分")
    train_samples, dev_samples, test_samples = stratified_split(
        deduped_samples,
        train_ratio=0.8,
        dev_ratio=0.1,
        test_ratio=0.1
    )

    # 4. 保存切分结果
    print("\n💾 第四步: 保存切分结果")
    save_split_to_file(train_samples, output_path / "train.jsonl", "训练")
    save_split_to_file(dev_samples, output_path / "dev.jsonl", "验证")
    save_split_to_file(test_samples, output_path / "test.jsonl", "测试")

    # 5. 更新metrics
    print("\n📊 第五步: 更新metrics.json")
    update_metrics_with_splits(
        metrics_path,
        len(train_samples),
        len(dev_samples),
        len(test_samples),
        dedup_stats
    )

    # 输出总结
    print("\n" + "=" * 60)
    print("🎉 全局去重 + 分层切分完成！")
    print("=" * 60)
    print("📈 处理统计:")
    print(f"  原始样本数: {dedup_stats['original_count']}")
    print(f"  去重后样本数: {dedup_stats['deduped_count']}")
    print(".3f")
    print()
    print("📊 切分结果:")
    print(f"  训练集: {len(train_samples)} 样本")
    print(f"  验证集: {len(dev_samples)} 样本")
    print(f"  测试集: {len(test_samples)} 样本")
    print()
    print("📁 输出文件:")
    print(f"  训练集: data/processed/active_qa_v1/train.jsonl")
    print(f"  验证集: data/processed/active_qa_v1/dev.jsonl")
    print(f"  测试集: data/processed/active_qa_v1/test.jsonl")
    print()
    print("💡 建议运行守护校验确认结果: python3 tools/guard_check_metrics.py")

    return 0

if __name__ == "__main__":
    exit(main())
