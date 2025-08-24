#!/usr/bin/env python3
import json
import os
import re
from collections import Counter
from typing import Dict, List, Any
import math

def distinct_n(texts: List[str], n: int) -> float:
    """计算distinct-n指标 - 按字符分割中文文本"""
    ngrams = []
    for text in texts:
        # 按字符分割中文文本，而不是按空格分割
        chars = list(text)
        for i in range(len(chars) - n + 1):
            ngrams.append(tuple(chars[i:i+n]))
    
    if not ngrams:
        return 0.0
    
    unique_ngrams = len(set(ngrams))
    total_ngrams = len(ngrams)
    
    return unique_ngrams / total_ngrams if total_ngrams > 0 else 0.0

def type_token_ratio(texts: List[str]) -> float:
    """计算Type-Token Ratio (TTR) - 按字符分割中文文本"""
    all_chars = []
    for text in texts:
        all_chars.extend(list(text))
    
    if not all_chars:
        return 0.0
    
    unique_chars = len(set(all_chars))
    total_chars = len(all_chars)
    
    return unique_chars / total_chars if total_chars > 0 else 0.0

def analyze_templates(template_dir: str) -> Dict[str, Any]:
    """分析模板多样性"""
    results = {}
    
    print(f"🔍 扫描目录: {template_dir}")
    
    for filename in os.listdir(template_dir):
        if filename.endswith('.json'):
            category = filename[:-5]  # 去掉.json后缀
            filepath = os.path.join(template_dir, filename)
            
            print(f"📁 处理文件: {filename}")
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    templates = json.load(f)
                
                print(f"  - 加载成功，类型: {type(templates)}, 数量: {len(templates)}")
                
                if not isinstance(templates, list):
                    print(f"  ❌ 文件 {filename} 不是列表格式")
                    continue
                
                if not templates:
                    print(f"  ❌ 文件 {filename} 为空")
                    continue
                
                # 检查第一个元素
                first_item = templates[0]
                print(f"  - 第一个元素类型: {type(first_item)}")
                
                if not isinstance(first_item, dict):
                    print(f"  ❌ 第一个元素不是字典格式")
                    continue
                
                if 'template' not in first_item:
                    print(f"  ❌ 第一个元素没有template键")
                    continue
                
                # 提取模板文本
                template_texts = []
                for t in templates:
                    if isinstance(t, dict) and 'template' in t:
                        template_texts.append(t['template'])
                    else:
                        print(f"  ⚠️ 跳过无效项: {type(t)}")
                
                print(f"  - 有效模板数: {len(template_texts)}")
                
                if not template_texts:
                    print(f"  ❌ 没有有效模板")
                    continue
                
                # 计算多样性指标
                distinct_1 = distinct_n(template_texts, 1)
                distinct_2 = distinct_n(template_texts, 2)
                ttr = type_token_ratio(template_texts)
                
                # 统计角色和语体
                roles = set()
                styles = set()
                for t in templates:
                    if isinstance(t, dict):
                        if 'role' in t:
                            roles.add(t['role'])
                        if 'style' in t:
                            styles.add(t['style'])
                
                results[category] = {
                    'count': len(templates),
                    'distinct_1': distinct_1,
                    'distinct_2': distinct_2,
                    'ttr': ttr,
                    'roles': list(roles),
                    'role_count': len(roles),
                    'styles': list(styles),
                    'style_count': len(styles)
                }
                
                print(f"  ✅ 分析完成: {category}")
                
            except Exception as e:
                print(f"  ❌ 处理文件 {filename} 时出错: {e}")
                continue
    
    return results

def main():
    """主函数"""
    template_dir = "templates/pack_v2"
    
    if not os.path.exists(template_dir):
        print(f"❌ 模板目录不存在: {template_dir}")
        return
    
    print("🔍 分析模板多样性...")
    
    # 分析模板
    results = analyze_templates(template_dir)
    
    if not results:
        print("❌ 没有成功分析任何模板文件")
        return
    
    # 计算总体指标
    total_templates = sum(data['count'] for data in results.values())
    avg_distinct_2 = sum(data['distinct_2'] for data in results.values()) / len(results)
    total_roles = len(set().union(*[set(data['roles']) for data in results.values()]))
    total_styles = len(set().union(*[set(data['styles']) for data in results.values()]))
    
    print(f"\n📊 总体统计:")
    print(f"  - 总模板数: {total_templates}")
    print(f"  - 平均distinct-2: {avg_distinct_2:.3f}")
    print(f"  - 总角色数: {total_roles}")
    print(f"  - 总语体数: {total_styles}")
    
    # 验收检查
    print(f"\n✅ 验收检查:")
    print(f"  - distinct-2≥0.60: {avg_distinct_2:.3f} {'✅' if avg_distinct_2 >= 0.60 else '❌'}")
    print(f"  - 角色≥4: {total_roles} {'✅' if total_roles >= 4 else '❌'}")
    print(f"  - 语体≥3: {total_styles} {'✅' if total_styles >= 3 else '❌'}")
    
    # 保存报告
    report = {
        'summary': {
            'total_templates': total_templates,
            'avg_distinct_2': avg_distinct_2,
            'total_roles': total_roles,
            'total_styles': total_styles,
            'pass_thresholds': {
                'distinct_2': avg_distinct_2 >= 0.60,
                'roles': total_roles >= 4,
                'styles': total_styles >= 3
            }
        },
        'categories': results
    }
    
    os.makedirs('reports', exist_ok=True)
    with open('reports/diversity_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📝 多样性报告已保存到: reports/diversity_report.json")
    
    # 检查是否通过所有门槛
    all_passed = all(report['summary']['pass_thresholds'].values())
    if all_passed:
        print("🎉 所有多样性门槛检查通过！")
    else:
        print("❌ 部分多样性门槛检查未通过，请检查模板设计。")

if __name__ == "__main__":
    main()
