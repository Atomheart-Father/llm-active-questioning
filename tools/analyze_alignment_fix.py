#!/usr/bin/env python3
"""
临时脚本：分析shard-004a的对齐错误情况
用于#S2-03h-fix任务
"""

import json
from pathlib import Path

def analyze_alignment_errors():
    """分析shard-004a的对齐错误情况"""

    # 读取shard-004a
    shard_file = "data/interim/shards/stage2_v1/shard-004a.jsonl"
    with open(shard_file, 'r', encoding='utf-8') as f:
        samples = [json.loads(line) for line in f]

    print('=== shard-004a 对齐错误分析 ===')
    print(f'总样本数: {len(samples)}')

    error_count = 0
    error_types = {
        'no_questions': 0,
        'length_mismatch': 0,
        'empty_response': 0
    }

    # 检查前10个样本的对齐情况
    print('\\n=== 前10个样本详细分析 ===')
    for i, sample in enumerate(samples[:10]):
        questions = sample.get('clarification_questions', [])
        responses = sample.get('assistant_response', '')

        print(f'\\n样本 {i+1}:')
        print(f'  问题数: {len(questions)}')
        print(f'  问题列表: {questions[:2]}')  # 只显示前2个
        print(f'  响应长度: {len(responses)}')
        print(f'  响应预览: {responses[:100]}...')

        # 检查对齐错误
        has_error = False
        if len(questions) == 0:
            print(f'  ❌ 对齐错误: 没有澄清问题')
            error_types['no_questions'] += 1
            has_error = True
        elif not responses:
            print(f'  ❌ 对齐错误: 响应为空')
            error_types['empty_response'] += 1
            has_error = True
        elif responses.count('；') + 1 != len(questions):
            print(f'  ❌ 对齐错误: 问题数({len(questions)}) != 答案枚举数({responses.count("；") + 1})')
            error_types['length_mismatch'] += 1
            has_error = True
        else:
            print(f'  ✅ 对齐正确')

        if has_error:
            error_count += 1

    # 统计所有样本的错误
    print('\\n=== 全部样本错误统计 ===')
    total_errors = 0
    for i, sample in enumerate(samples):
        questions = sample.get('clarification_questions', [])
        responses = sample.get('assistant_response', '')

        if len(questions) == 0 or not responses or responses.count('；') + 1 != len(questions):
            total_errors += 1

    print(f'总对齐错误数: {total_errors}/{len(samples)}')
    print(f'错误类型统计:')
    print(f'  - 无澄清问题: {error_types["no_questions"]}')
    print(f'  - 长度不匹配: {error_types["length_mismatch"]}')
    print(f'  - 响应为空: {error_types["empty_response"]}')

if __name__ == "__main__":
    analyze_alignment_errors()
