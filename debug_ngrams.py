#!/usr/bin/env python3
import json
from collections import Counter

def analyze_ngrams():
    """分析模板的2-gram分布"""
    
    # 读取模板文件
    with open('templates/pack_v2/math.json', 'r', encoding='utf-8') as f:
        math_templates = json.load(f)
    
    print("=== 数学模板2-gram分析 ===")
    
    all_ngrams = []
    for i, template in enumerate(math_templates):
        text = template['template']
        print(f"\n模板 {i+1}: {text}")
        print(f"文本长度: {len(text)}")
        
        # 检查是否有隐藏字符
        print(f"文本repr: {repr(text)}")
        
        # 按字符分割中文文本
        chars = list(text)
        print(f"字符分割结果: {chars}")
        print(f"字符数: {len(chars)}")
        
        # 提取2-grams
        ngrams = []
        for j in range(len(chars) - 1):
            ngram = (chars[j], chars[j+1])
            ngrams.append(ngram)
            all_ngrams.append(ngram)
        
        print(f"2-grams: {ngrams}")
    
    # 统计所有2-grams
    print(f"\n=== 2-gram统计 ===")
    print(f"总2-gram数量: {len(all_ngrams)}")
    
    if all_ngrams:
        ngram_counts = Counter(all_ngrams)
        print(f"唯一2-gram数量: {len(ngram_counts)}")
        print(f"distinct-2: {len(ngram_counts) / len(all_ngrams):.3f}")
        
        print(f"\n=== 重复的2-grams ===")
        for ngram, count in ngram_counts.most_common():
            if count > 1:
                print(f"'{''.join(ngram)}': {count}次")
    else:
        print("没有生成任何2-grams！")

if __name__ == "__main__":
    analyze_ngrams()
