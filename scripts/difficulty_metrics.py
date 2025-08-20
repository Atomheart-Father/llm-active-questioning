#!/usr/bin/env python3
"""
数据难度指标提取器
逐样本计算：长度、轮次、工具链、实体数、数值操作、连接词密度、线索重叠等
"""

import json
import re
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import Counter
import hashlib

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DifficultyAnalyzer:
    def __init__(self):
        # 逻辑连接词词典（中英文）
        self.connectors = {
            'and', 'but', 'or', 'so', 'because', 'since', 'although', 'however',
            'therefore', 'thus', 'moreover', 'furthermore', 'meanwhile', 'while',
            'if', 'then', 'else', 'unless', 'when', 'where', 'why', 'how',
            '和', '但是', '或者', '所以', '因为', '由于', '虽然', '然而', 
            '因此', '从而', '而且', '同时', '如果', '那么', '否则', '除非',
            '当', '在', '为什么', '怎样', '然后', '接着', '另外'
        }
        
        # 数值操作词汇
        self.numeric_ops = {
            '+', '-', '*', '/', '%', '>', '<', '=', '≥', '≤', '≠',
            'plus', 'minus', 'times', 'divide', 'multiply', 'equal', 'greater', 'less',
            'compare', 'calculate', 'sum', 'difference', 'product', 'quotient',
            '加', '减', '乘', '除', '等于', '大于', '小于', '比较', '计算', '总和', '差', '积'
        }
        
        # 指代词
        self.pronouns = {
            'it', 'they', 'them', 'this', 'that', 'these', 'those', 'he', 'she',
            'him', 'her', 'his', 'hers', 'its', 'their', 'theirs',
            '它', '他', '她', '其', '这', '那', '这些', '那些', '他们', '她们'
        }
        
        # 模糊性标记词汇
        self.ambiguity_markers = {
            'multiple', 'several', 'various', 'different', 'unclear', 'ambiguous',
            'maybe', 'perhaps', 'possibly', 'might', 'could', 'uncertain',
            '多个', '几个', '不同', '模糊', '可能', '也许', '或许', '不确定'
        }

    def estimate_tokens(self, text: str) -> int:
        """估算token数（简化版）"""
        # 简单估算：英文按词数*1.3，中文按字符数*0.7
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        return int(english_words * 1.3 + chinese_chars * 0.7)

    def count_turns(self, dialogue: List[Dict]) -> int:
        """计算对话轮次"""
        return len([turn for turn in dialogue if turn.get('role') in ['user', 'assistant']])

    def count_tool_hops(self, dialogue: List[Dict]) -> int:
        """统计工具调用次数"""
        tool_count = 0
        for turn in dialogue:
            content = str(turn.get('content', ''))
            # 查找工具调用模式
            tool_count += len(re.findall(r'tool_call|wiki|calc|search|retrieve', content, re.IGNORECASE))
        return tool_count

    def extract_entities(self, text: str) -> int:
        """提取实体数（简化版NER）"""
        entities = set()
        
        # 英文专名（大写开头）
        english_entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        entities.update(english_entities)
        
        # 中文专名（简化规则）
        chinese_entities = re.findall(r'[\u4e00-\u9fff]{2,4}(?:公司|大学|医院|银行|政府|组织)', text)
        entities.update(chinese_entities)
        
        # 数字和日期
        numbers = re.findall(r'\b\d{1,4}(?:[,.]?\d{3})*\b', text)
        entities.update(numbers)
        
        return len(entities)

    def count_numeric_ops(self, text: str) -> int:
        """统计数值操作"""
        count = 0
        text_lower = text.lower()
        
        for op in self.numeric_ops:
            count += text_lower.count(op)
        
        # 额外检查表达式模式
        count += len(re.findall(r'\d+\s*[+\-*/=]\s*\d+', text))
        count += len(re.findall(r'(\d+)%', text))  # 百分比
        
        return count

    def calculate_connector_density(self, text: str) -> float:
        """计算连接词密度（每100词）"""
        words = re.findall(r'\b\w+\b', text.lower())
        if len(words) == 0:
            return 0.0
        
        connector_count = sum(1 for word in words if word in self.connectors)
        return (connector_count / len(words)) * 100

    def calculate_clue_overlap(self, question: str, context: str) -> float:
        """计算线索重叠率（3-gram Jaccard）"""
        def get_ngrams(text: str, n: int = 3) -> set:
            words = re.findall(r'\b\w+\b', text.lower())
            return set(' '.join(words[i:i+n]) for i in range(len(words)-n+1))
        
        q_ngrams = get_ngrams(question)
        c_ngrams = get_ngrams(context)
        
        if len(q_ngrams) == 0 or len(c_ngrams) == 0:
            return 0.0
        
        intersection = len(q_ngrams & c_ngrams)
        union = len(q_ngrams | c_ngrams)
        
        return intersection / union if union > 0 else 0.0

    def count_pronouns(self, text: str) -> int:
        """统计指代词数"""
        words = re.findall(r'\b\w+\b', text.lower())
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        
        count = sum(1 for word in words if word in self.pronouns)
        count += sum(1 for char in chinese_chars if char in self.pronouns)
        
        return count

    def detect_ambiguity_flags(self, text: str, dialogue: List[Dict]) -> List[str]:
        """检测模糊性标记"""
        flags = []
        text_lower = text.lower()
        
        # 检查模糊性词汇
        if any(marker in text_lower for marker in self.ambiguity_markers):
            flags.append("under-specified")
        
        # 多实体检查
        if self.extract_entities(text) >= 5:
            flags.append("multi-entity")
        
        # 指代密度高
        if self.count_pronouns(text) >= 3:
            flags.append("high-coreference")
        
        # 长对话
        if self.count_turns(dialogue) >= 5:
            flags.append("long-dialogue")
        
        return flags

    def needs_clarification(self, dialogue: List[Dict]) -> bool:
        """判断是否需要澄清"""
        # 简化判断：包含问号或澄清词汇
        clarification_words = {'clarify', 'explain', 'what do you mean', 'unclear', '澄清', '解释', '什么意思'}
        
        for turn in dialogue:
            content = str(turn.get('content', '')).lower()
            if '?' in content or any(word in content for word in clarification_words):
                return True
        
        return False

    def analyze_sample(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """分析单个样本的难度指标"""
        # 提取基本信息
        sample_id = sample.get('id', hashlib.md5(str(sample).encode()).hexdigest()[:16])
        task = sample.get('task', 'unknown')
        
        # 合并文本内容
        question = sample.get('question', sample.get('query', ''))
        context = sample.get('context', '')
        dialogue = sample.get('dialogue', sample.get('conversation', []))
        
        full_text = f"{question} {context}"
        if dialogue:
            full_text += " " + " ".join([str(turn.get('content', '')) for turn in dialogue])
        
        # 计算各项指标
        metrics = {
            "id": sample_id,
            "task": task,
            "len_tokens": self.estimate_tokens(full_text),
            "turns": self.count_turns(dialogue) if dialogue else 1,
            "tool_hops": self.count_tool_hops(dialogue) if dialogue else 0,
            "entities": self.extract_entities(full_text),
            "ops_numeric": self.count_numeric_ops(full_text),
            "connector_density": self.calculate_connector_density(full_text),
            "coref_pronouns": self.count_pronouns(full_text),
            "clue_overlap": self.calculate_clue_overlap(question, context),
            "ambiguity_flags": self.detect_ambiguity_flags(full_text, dialogue),
            "needs_clarification": self.needs_clarification(dialogue) if dialogue else False
        }
        
        return metrics

def main():
    parser = argparse.ArgumentParser(description='提取数据难度指标')
    parser.add_argument('--in', dest='input_file', required=True, help='输入数据文件')
    parser.add_argument('--out', required=True, help='输出指标文件')
    
    args = parser.parse_args()
    
    input_path = Path(args.input_file)
    output_path = Path(args.out)
    
    if not input_path.exists():
        logger.error(f"输入文件不存在: {input_path}")
        return 1
    
    # 创建输出目录
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    analyzer = DifficultyAnalyzer()
    
    logger.info(f"开始分析文件: {input_path}")
    
    processed_count = 0
    with open(input_path, 'r', encoding='utf-8') as infile, \
         open(output_path, 'w', encoding='utf-8') as outfile:
        
        for line_num, line in enumerate(infile, 1):
            try:
                sample = json.loads(line.strip())
                metrics = analyzer.analyze_sample(sample)
                
                outfile.write(json.dumps(metrics, ensure_ascii=False) + '\n')
                processed_count += 1
                
                if processed_count % 1000 == 0:
                    logger.info(f"已处理 {processed_count} 个样本")
                    
            except Exception as e:
                logger.warning(f"处理第{line_num}行时出错: {e}")
                continue
    
    logger.info(f"完成！共处理 {processed_count} 个样本")
    logger.info(f"输出文件: {output_path}")
    
    return 0

if __name__ == "__main__":
    exit(main())
