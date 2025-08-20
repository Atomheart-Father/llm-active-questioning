#!/usr/bin/env python3
"""
构建PPO训练种子池
生成多样化的对话轨迹用于强化学习训练
"""

import json
import argparse
import logging
import random
from pathlib import Path
from typing import Dict, List, Any, Tuple
import hashlib
import uuid

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RolloutPoolBuilder:
    def __init__(self, templates_dir: str):
        self.templates_dir = Path(templates_dir)
        self.load_templates()

    def load_templates(self):
        """加载模板包"""
        # 简化实现：生成基础模板结构
        self.task_templates = {
            'hotpotqa': [
                "根据给定信息回答问题：{question}\n上下文：{context}",
                "请分析并回答多跳推理问题：{question}\n提供的信息：{context}",
                "综合以下信息回答问题：{question}\n相关材料：{context}"
            ],
            'strategyqa': [
                "判断以下陈述的真假并给出推理：{question}",
                "请分析这个策略性问题：{question}\n给出是/否答案及理由",
                "基于常识推理回答：{question}"
            ],
            'gsm8k': [
                "解决这个数学应用题：{question}",
                "请一步步解答：{question}",
                "计算并解释解题过程：{question}"
            ]
        }
        
        self.clarification_templates = [
            "我需要澄清一下：{clarification}",
            "为了更好地回答，请问：{clarification}",
            "我想确认一下：{clarification}",
            "Could you clarify: {clarification}",
            "I need to understand: {clarification}"
        ]

    def generate_base_samples(self, task: str, count: int) -> List[Dict[str, Any]]:
        """生成基础样本"""
        samples = []
        
        # 简化实现：生成模拟数据
        for i in range(count):
            sample_id = str(uuid.uuid4())[:16]
            
            if task == 'hotpotqa':
                question = f"What is the relationship between entity A{i} and entity B{i}?"
                context = f"Entity A{i} is connected to entity B{i} through relationship R{i}. Additional context about these entities..."
                answer = f"Entity A{i} and entity B{i} are related through R{i}."
            
            elif task == 'strategyqa':
                question = f"Is it possible for event X{i} to occur under condition Y{i}?"
                context = f"Given the constraints and common knowledge about condition Y{i}..."
                answer = f"Yes/No, because of reason R{i}."
            
            elif task == 'gsm8k':
                question = f"John has {10+i} apples and gives away {2+i%3} apples. How many does he have left?"
                context = "This is a basic arithmetic problem."
                answer = f"John has {10+i-(2+i%3)} apples left."
            
            else:
                question = f"Sample question {i} for task {task}"
                context = f"Context for question {i}"
                answer = f"Answer for question {i}"
            
            sample = {
                'id': sample_id,
                'task': task,
                'question': question,
                'context': context,
                'gold_answer': answer,
                'template_id': f"{task}_template_{i % 3}",
                'metadata': {
                    'generated': True,
                    'difficulty': random.choice(['easy', 'medium', 'hard']),
                    'requires_tools': random.choice([True, False]),
                    'multi_hop': random.choice([True, False])
                }
            }
            
            samples.append(sample)
        
        return samples

    def add_clarification_dialogue(self, sample: Dict[str, Any], 
                                  clarify_rate: float, max_turns: int) -> Dict[str, Any]:
        """添加澄清对话"""
        if random.random() > clarify_rate:
            return sample
        
        dialogue = [
            {'role': 'user', 'content': sample['question']},
        ]
        
        # 随机添加1-2轮澄清
        num_clarifications = random.randint(1, min(2, max_turns-2))
        
        for i in range(num_clarifications):
            # AI请求澄清
            clarification = f"Could you specify what you mean by '{random.choice(['the relationship', 'the context', 'the condition'])}'?"
            dialogue.append({
                'role': 'assistant', 
                'content': random.choice(self.clarification_templates).format(clarification=clarification)
            })
            
            # 用户回应
            user_response = f"I mean {random.choice(['specifically', 'in particular', 'more precisely'])} the {random.choice(['main aspect', 'key point', 'important detail'])}."
            dialogue.append({
                'role': 'user',
                'content': user_response
            })
        
        # 最终回答
        dialogue.append({
            'role': 'assistant',
            'content': sample['gold_answer']
        })
        
        sample['dialogue'] = dialogue
        sample['has_clarification'] = True
        sample['clarification_turns'] = num_clarifications
        
        return sample

    def add_tool_usage(self, sample: Dict[str, Any], tools: List[str]) -> Dict[str, Any]:
        """添加工具使用"""
        if not sample['metadata']['requires_tools'] or not tools:
            return sample
        
        tool_calls = []
        num_tools = random.randint(1, min(3, len(tools)))
        
        for i in range(num_tools):
            tool = random.choice(tools)
            
            if tool == 'wiki':
                tool_call = {
                    'tool': 'wiki',
                    'query': f"search for {random.choice(['information about', 'details on', 'background of'])} the topic",
                    'result': f"Found relevant information about the topic..."
                }
            elif tool == 'calc':
                tool_call = {
                    'tool': 'calc',
                    'expression': f"{random.randint(10,100)} + {random.randint(5,50)}",
                    'result': str(random.randint(15,150))
                }
            else:
                tool_call = {
                    'tool': tool,
                    'input': "generic input",
                    'result': "generic result"
                }
            
            tool_calls.append(tool_call)
        
        sample['tool_calls'] = tool_calls
        sample['tool_count'] = len(tool_calls)
        
        return sample

    def build_pool(self, n: int, task_mix: Dict[str, float], 
                  max_turns: int, clarify_rate: float, tools: List[str]) -> List[Dict[str, Any]]:
        """构建完整的种子池"""
        logger.info(f"开始构建种子池，目标 {n} 个样本")
        logger.info(f"任务配比: {task_mix}")
        
        all_samples = []
        
        for task, ratio in task_mix.items():
            task_count = int(n * ratio)
            logger.info(f"生成 {task} 任务样本: {task_count}")
            
            # 生成基础样本
            base_samples = self.generate_base_samples(task, task_count)
            
            # 添加澄清对话和工具使用
            enhanced_samples = []
            for sample in base_samples:
                # 添加澄清对话
                sample = self.add_clarification_dialogue(sample, clarify_rate, max_turns)
                
                # 添加工具使用
                sample = self.add_tool_usage(sample, tools)
                
                enhanced_samples.append(sample)
            
            all_samples.extend(enhanced_samples)
        
        # 打乱顺序
        random.shuffle(all_samples)
        
        logger.info(f"种子池构建完成，共 {len(all_samples)} 个样本")
        
        return all_samples

def parse_task_mix(mix_str: str) -> Dict[str, float]:
    """解析任务配比字符串"""
    mix = {}
    for pair in mix_str.split(','):
        task, ratio = pair.split(':')
        mix[task.strip()] = float(ratio.strip())
    
    # 归一化
    total = sum(mix.values())
    if abs(total - 1.0) > 1e-6:
        logger.warning(f"任务配比总和不为1: {total}, 进行归一化")
        mix = {k: v/total for k, v in mix.items()}
    
    return mix

def main():
    parser = argparse.ArgumentParser(description='构建PPO训练种子池')
    parser.add_argument('--out', required=True, help='输出文件路径')
    parser.add_argument('--n', type=int, required=True, help='样本总数')
    parser.add_argument('--mix', required=True, help='任务配比，如hotpotqa:0.45,strategyqa:0.30,gsm8k:0.25')
    parser.add_argument('--max_turns', type=int, default=6, help='最大对话轮次')
    parser.add_argument('--clarify_rate', type=float, default=0.30, help='澄清对话比例')
    parser.add_argument('--tools', default='wiki,calc', help='可用工具，逗号分隔')
    parser.add_argument('--templates_dir', default='templates/pack_v2', help='模板目录')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    
    args = parser.parse_args()
    
    # 设置随机种子
    random.seed(args.seed)
    
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 解析参数
    task_mix = parse_task_mix(args.mix)
    tools = [tool.strip() for tool in args.tools.split(',')]
    
    # 构建种子池
    builder = RolloutPoolBuilder(args.templates_dir)
    samples = builder.build_pool(
        n=args.n,
        task_mix=task_mix,
        max_turns=args.max_turns,
        clarify_rate=args.clarify_rate,
        tools=tools
    )
    
    # 保存结果
    with open(output_path, 'w', encoding='utf-8') as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    
    logger.info(f"种子池保存到: {output_path}")
    
    # 生成统计信息
    stats = {
        'total_samples': len(samples),
        'task_distribution': {},
        'has_clarification': sum(1 for s in samples if s.get('has_clarification', False)),
        'has_tools': sum(1 for s in samples if s.get('tool_calls', [])),
        'parameters': {
            'task_mix': task_mix,
            'max_turns': args.max_turns,
            'clarify_rate': args.clarify_rate,
            'tools': tools,
            'seed': args.seed
        }
    }
    
    # 统计任务分布
    for task in task_mix.keys():
        task_samples = [s for s in samples if s.get('task') == task]
        stats['task_distribution'][task] = len(task_samples)
    
    stats_path = output_path.with_suffix('.stats.json')
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    logger.info(f"统计信息保存到: {stats_path}")
    
    return 0

if __name__ == "__main__":
    exit(main())
