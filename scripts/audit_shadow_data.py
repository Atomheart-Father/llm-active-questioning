#!/usr/bin/env python3
"""
影子数据审计脚本：真伪 & 多样性 & 去模板化检测
"""

import argparse
import json
import re
import sys
import hashlib
import random
from pathlib import Path
from collections import Counter

def load_samples(jsonl_file):
    """加载JSONL样本"""
    samples = []
    with open(jsonl_file, "r", encoding="utf-8") as f:
        for line in f:
            samples.append(json.loads(line.strip()))
    return samples

def audit_authenticity(samples):
    """真伪溯源审计"""
    print("🔍 真伪溯源审计...")
    
    allowed_datasets = {"hotpot_qa", "tasksource/bigbench", "gsm8k"}
    by_task = {}
    fingerprints_by_task = {}
    
    for sample in samples:
        # 检查source
        if sample.get("source") != "hf":
            return False, f"样本source不为hf: {sample.get('id')}"
        
        # 检查hf_dataset
        hf_dataset = sample.get("hf_dataset")
        if hf_dataset not in allowed_datasets:
            return False, f"非允许数据集: {hf_dataset}"
        
        # 检查question和task
        if not sample.get("question") or sample.get("task") == "unknown":
            return False, f"question为空或task为unknown: {sample.get('id')}"
        
        # 统计任务分布
        task = sample.get("task")
        by_task[task] = by_task.get(task, 0) + 1
        
        # 收集指纹
        fingerprint = sample.get("hf_fingerprint")
        if fingerprint:
            if task not in fingerprints_by_task:
                fingerprints_by_task[task] = set()
            fingerprints_by_task[task].add(fingerprint)
    
    # 检查任务分布：每个任务应在[70, 90]范围内
    total = len(samples)
    for task, count in by_task.items():
        if not (70 <= count <= 90):
            return False, f"任务{task}分布异常: {count}/{total} (应在[70,90])"
    
    # 检查指纹数量：每个任务≤3个指纹
    for task, fingerprints in fingerprints_by_task.items():
        if len(fingerprints) > 3:
            return False, f"任务{task}指纹过多: {len(fingerprints)} > 3"
    
    print(f"  ✅ 任务分布: {by_task}")
    print(f"  ✅ 指纹统计: {[(k, len(v)) for k, v in fingerprints_by_task.items()]}")
    
    return True, by_task

def mask_question(question):
    """生成掩码问题：小写+数字替换为#"""
    masked = question.lower()
    masked = re.sub(r'\d+', '#', masked)
    return masked

def audit_detemplatization(samples):
    """去模板化/反改数字凑数检测"""
    print("🔍 去模板化审计...")
    
    questions = [sample.get("question", "") for sample in samples]
    
    # 1. 掩码唯一率
    masks = [mask_question(q) for q in questions]
    unique_masks = set(masks)
    mask_uniqueness = len(unique_masks) / len(masks)
    
    # 最频繁掩码占比
    mask_counts = Counter(masks)
    most_common_mask_ratio = mask_counts.most_common(1)[0][1] / len(masks) if mask_counts else 0
    
    print(f"  📊 掩码唯一率: {mask_uniqueness:.3f} (需≥0.60)")
    print(f"  📊 最频繁掩码占比: {most_common_mask_ratio:.3f} (需≤0.10)")
    
    if mask_uniqueness < 0.60:
        return False, f"掩码唯一率过低: {mask_uniqueness:.3f} < 0.60"
    
    if most_common_mask_ratio > 0.10:
        return False, f"最频繁掩码占比过高: {most_common_mask_ratio:.3f} > 0.10"
    
    # 2. 相似度抽检：5-gram Jaccard
    def get_5grams(text):
        text = text.lower()
        return set(text[i:i+5] for i in range(len(text)-4))
    
    def jaccard_similarity(set1, set2):
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0
        return len(set1 & set2) / len(set1 | set2)
    
    # 随机抽2000对
    n_pairs = min(2000, len(questions) * (len(questions) - 1) // 2)
    high_sim_pairs = 0
    
    random.seed(42)
    pairs = [(i, j) for i in range(len(questions)) for j in range(i+1, len(questions))]
    sampled_pairs = random.sample(pairs, n_pairs)
    
    for i, j in sampled_pairs:
        grams1 = get_5grams(questions[i])
        grams2 = get_5grams(questions[j])
        sim = jaccard_similarity(grams1, grams2)
        if sim >= 0.9:
            high_sim_pairs += 1
    
    high_sim_ratio = high_sim_pairs / n_pairs
    print(f"  📊 高相似度对比例: {high_sim_ratio:.3f} (需≤0.01)")
    
    if high_sim_ratio > 0.01:
        return False, f"高相似度对过多: {high_sim_ratio:.3f} > 0.01"
    
    # 3. 长度分布
    lengths = [len(q) for q in questions]
    mean_length = sum(lengths) / len(lengths)
    std_length = (sum((l - mean_length) ** 2 for l in lengths) / len(lengths)) ** 0.5
    
    print(f"  📊 题干长度: 均值={mean_length:.1f}, 标准差={std_length:.1f}")
    
    if not (30 <= mean_length <= 300):
        return False, f"题干长度均值异常: {mean_length:.1f} 不在[30,300]"
    
    if std_length < 15:
        return False, f"题干长度标准差过小: {std_length:.1f} < 15"
    
    # 4. 重复前缀检查
    prefixes = [q[:12] for q in questions if len(q) >= 12]
    if prefixes:
        prefix_counts = Counter(prefixes)
        most_common_prefix_ratio = prefix_counts.most_common(1)[0][1] / len(prefixes)
        print(f"  📊 最常见前缀占比: {most_common_prefix_ratio:.3f} (需≤0.20)")
        
        if most_common_prefix_ratio > 0.20:
            return False, f"重复前缀过多: {most_common_prefix_ratio:.3f} > 0.20"
    
    return True, {
        "mask_uniqueness": mask_uniqueness,
        "most_common_mask_ratio": most_common_mask_ratio,
        "high_sim_ratio": high_sim_ratio,
        "mean_length": mean_length,
        "std_length": std_length,
        "most_common_prefix_ratio": most_common_prefix_ratio if prefixes else 0
    }

def audit_duplicates(samples):
    """重复/空样本检查"""
    print("🔍 重复样本审计...")
    
    # 规范化文本
    def normalize_text(text):
        if not text:
            return ""
        # 去空格，全角半角统一
        text = re.sub(r'\s+', ' ', text.strip())
        text = text.replace('　', ' ')  # 全角空格
        # 全角转半角数字和字母
        full_to_half = str.maketrans(
            '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
            '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        )
        return text.translate(full_to_half)
    
    normalized_questions = []
    empty_answers = 0
    
    for sample in samples:
        question = normalize_text(sample.get("question", ""))
        answer = sample.get("answer", "")
        
        normalized_questions.append(question)
        
        # 检查空答案（StrategyQA特殊处理）
        if not answer:
            empty_answers += 1
        elif sample.get("task") == "strategyqa" and answer not in ["yes", "no"]:
            empty_answers += 1
    
    # 计算重复率
    question_counts = Counter(normalized_questions)
    duplicates = sum(count - 1 for count in question_counts.values() if count > 1)
    duplicate_ratio = duplicates / len(samples)
    
    print(f"  📊 完全重复率: {duplicate_ratio:.3f} (需≤0.01)")
    print(f"  📊 空答案数: {empty_answers} (需=0)")
    
    if duplicate_ratio > 0.01:
        return False, f"重复率过高: {duplicate_ratio:.3f} > 0.01"
    
    if empty_answers > 0:
        return False, f"存在空答案: {empty_answers}个"
    
    return True, {
        "duplicate_ratio": duplicate_ratio,
        "empty_answers": empty_answers
    }

def main():
    parser = argparse.ArgumentParser(description="影子数据审计")
    parser.add_argument("input_file", help="输入JSONL文件")
    parser.add_argument("--report", required=True, help="审计报告JSON")
    
    args = parser.parse_args()
    
    print(f"🩺 影子数据审计: {args.input_file}")
    
    # 加载样本
    try:
        samples = load_samples(args.input_file)
        print(f"📊 加载样本: {len(samples)}条")
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        return 1
    
    audit_results = {
        "total_samples": len(samples),
        "timestamp": Path(args.input_file).stat().st_mtime,
        "passed": True,
        "failures": []
    }
    
    # 真伪溯源审计
    passed, result = audit_authenticity(samples)
    if not passed:
        audit_results["passed"] = False
        audit_results["failures"].append(f"真伪溯源: {result}")
        print(f"❌ {result}")
    else:
        audit_results["by_task"] = result
    
    # 去模板化审计
    passed, result = audit_detemplatization(samples)
    if not passed:
        audit_results["passed"] = False
        audit_results["failures"].append(f"去模板化: {result}")
        print(f"❌ {result}")
    else:
        audit_results["detemplatization"] = result
    
    # 重复样本审计
    passed, result = audit_duplicates(samples)
    if not passed:
        audit_results["passed"] = False
        audit_results["failures"].append(f"重复检测: {result}")
        print(f"❌ {result}")
    else:
        audit_results["duplicates"] = result
    
    # 保存报告
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(audit_results, f, ensure_ascii=False, indent=2)
    
    if audit_results["passed"]:
        print("✅ 所有审计通过")
        return 0
    else:
        print(f"❌ 审计失败: {len(audit_results['failures'])}项")
        for failure in audit_results["failures"]:
            print(f"  - {failure}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
