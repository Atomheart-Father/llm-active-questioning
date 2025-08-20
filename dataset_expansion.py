#!/usr/bin/env python3
"""
数据集扩展模块
基于HotpotQA、StrategyQA、AmbigQA等数据集创建多轮对话训练数据
"""

import sys
import json
import random
from pathlib import Path
from typing import Dict, List, Any, Optional
from datasets import load_dataset

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_config
from src.utils.logging import get_logger
from gemini_integration import GeminiDataGenerator


class DatasetExpander:
    """数据集扩展器"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger("dataset_expander")
        self.gemini_generator = GeminiDataGenerator()
        
        # 数据集配置
        self.dataset_configs = {
            "hotpot_qa": {
                "name": "hotpot_qa",
                "config": "fullwiki",
                "sample_size": 50,
                "description": "多跳推理问答数据集"
            },
            "ambig_qa": {
                "name": "ambig_qa",
                "config": "light",
                "sample_size": 30,
                "description": "歧义问答数据集"
            },
            "gsm8k": {
                "name": "gsm8k",
                "config": "main",
                "sample_size": 40,
                "description": "数学推理问题数据集"
            }
        }
        
        self.logger.info("数据集扩展器初始化完成")
    
    def load_sample_data(self, dataset_name: str, sample_size: int = None) -> List[Dict[str, Any]]:
        """
        加载并采样数据集
        
        Args:
            dataset_name: 数据集名称
            sample_size: 采样大小
            
        Returns:
            采样的数据列表
        """
        config = self.dataset_configs.get(dataset_name)
        if not config:
            self.logger.error(f"未知数据集: {dataset_name}")
            return []
        
        sample_size = sample_size or config["sample_size"]
        
        try:
            self.logger.info(f"加载数据集: {config['name']} ({config['description']})")
            
            if dataset_name == "hotpot_qa":
                dataset = load_dataset(config["name"], config["config"], split="train")
                # 过滤复杂度适中的问题
                filtered_data = [item for item in dataset if len(item.get("question", "")) < 150]
                samples = random.sample(filtered_data, min(sample_size, len(filtered_data)))
                
                processed_samples = []
                for item in samples:
                    processed_samples.append({
                        "question": item["question"],
                        "answer": item["answer"],
                        "type": "multi_hop",
                        "supporting_facts": item.get("supporting_facts", []),
                        "dataset": "hotpot_qa"
                    })
                
            elif dataset_name == "ambig_qa":
                dataset = load_dataset(config["name"], config["config"], split="train")
                samples = random.sample(list(dataset), min(sample_size, len(dataset)))
                
                processed_samples = []
                for item in samples:
                    # AmbigQA可能有多个可能的答案
                    annotations = item.get("annotations", [])
                    if annotations:
                        processed_samples.append({
                            "question": item["question"],
                            "answer": annotations[0].get("long_answer", ""),
                            "type": "ambiguous",
                            "multiple_answers": [ann.get("long_answer", "") for ann in annotations],
                            "dataset": "ambig_qa"
                        })
            
            elif dataset_name == "gsm8k":
                dataset = load_dataset(config["name"], config["config"], split="train")
                samples = random.sample(list(dataset), min(sample_size, len(dataset)))
                
                processed_samples = []
                for item in samples:
                    processed_samples.append({
                        "question": item["question"],
                        "answer": item["answer"],
                        "type": "math_reasoning",
                        "dataset": "gsm8k"
                    })
            
            else:
                self.logger.warning(f"数据集 {dataset_name} 处理逻辑未实现")
                return []
            
            self.logger.info(f"成功加载{len(processed_samples)}个{config['description']}样本")
            return processed_samples
            
        except Exception as e:
            self.logger.error(f"加载数据集失败 {dataset_name}: {e}")
            return []
    
    def create_mock_datasets(self) -> Dict[str, List[Dict[str, Any]]]:
        """创建模拟数据集（当无法加载真实数据集时使用）"""
        self.logger.info("创建模拟数据集...")
        
        mock_data = {
            "hotpot_qa": [
                {
                    "question": "谁是写《哈利波特》的作者的丈夫？",
                    "answer": "尼尔·默里（Neil Murray）",
                    "type": "multi_hop",
                    "reasoning_steps": ["找到《哈利波特》作者", "找到作者的丈夫"],
                    "dataset": "hotpot_qa_mock"
                },
                {
                    "question": "世界最高峰所在国家的首都是什么？",
                    "answer": "加德满都",
                    "type": "multi_hop", 
                    "reasoning_steps": ["确定世界最高峰", "确定所在国家", "找到首都"],
                    "dataset": "hotpot_qa_mock"
                },
                {
                    "question": "第一个登上月球的人出生在哪个州？",
                    "answer": "俄亥俄州",
                    "type": "multi_hop",
                    "reasoning_steps": ["确定第一个登月的人", "查找出生地"],
                    "dataset": "hotpot_qa_mock"
                }
            ],
            "ambig_qa": [
                {
                    "question": "他什么时候出生的？",
                    "answer": "需要明确指代对象",
                    "type": "ambiguous",
                    "clarification_needed": "请问您指的是哪位人物？",
                    "dataset": "ambig_qa_mock"
                },
                {
                    "question": "那家餐厅好吃吗？",
                    "answer": "需要明确具体餐厅",
                    "type": "ambiguous",
                    "clarification_needed": "请问您指的是哪家餐厅？",
                    "dataset": "ambig_qa_mock"
                },
                {
                    "question": "这个价格合理吗？",
                    "answer": "需要明确商品和价格信息",
                    "type": "ambiguous",
                    "clarification_needed": "请问您指的是什么商品和价格？",
                    "dataset": "ambig_qa_mock"
                }
            ],
            "gsm8k": [
                {
                    "question": "一个班级有25个学生，如果每个学生需要3本书，总共需要多少本书？",
                    "answer": "75本书",
                    "type": "math_reasoning",
                    "calculation": "25 × 3 = 75",
                    "dataset": "gsm8k_mock"
                },
                {
                    "question": "张三有120元，买了3支笔，每支笔15元，还剩多少钱？",
                    "answer": "75元",
                    "type": "math_reasoning", 
                    "calculation": "120 - (3 × 15) = 120 - 45 = 75",
                    "dataset": "gsm8k_mock"
                },
                {
                    "question": "一辆车每小时行驶60公里，行驶了2.5小时，总共行驶了多少公里？",
                    "answer": "150公里",
                    "type": "math_reasoning",
                    "calculation": "60 × 2.5 = 150",
                    "dataset": "gsm8k_mock"
                }
            ]
        }
        
        self.logger.info(f"创建了{sum(len(v) for v in mock_data.values())}个模拟样本")
        return mock_data
    
    def convert_to_multi_turn_dialogues(self, samples: List[Dict[str, Any]], 
                                       dataset_type: str) -> List[Dict[str, Any]]:
        """
        将样本转换为多轮对话格式
        
        Args:
            samples: 原始样本
            dataset_type: 数据集类型
            
        Returns:
            多轮对话数据
        """
        self.logger.info(f"转换{len(samples)}个{dataset_type}样本为多轮对话格式...")
        
        multi_turn_dialogues = []
        
        for i, sample in enumerate(samples):
            try:
                if dataset_type == "ambiguous":
                    # 歧义问题：需要澄清
                    dialogue = self._create_clarification_dialogue(sample)
                elif dataset_type == "multi_hop":
                    # 多跳推理：分步骤提问
                    dialogue = self._create_step_wise_dialogue(sample)
                elif dataset_type == "math_reasoning":
                    # 数学推理：可能需要澄清条件
                    dialogue = self._create_math_dialogue(sample)
                else:
                    # 默认处理
                    dialogue = self._create_simple_dialogue(sample)
                
                if dialogue:
                    dialogue["sample_id"] = i
                    dialogue["original_dataset"] = sample.get("dataset", dataset_type)
                    multi_turn_dialogues.append(dialogue)
                    
                self.logger.info(f"转换完成 {i+1}/{len(samples)}")
                
            except Exception as e:
                self.logger.error(f"转换样本失败 {i}: {e}")
                continue
        
        self.logger.info(f"成功转换{len(multi_turn_dialogues)}个多轮对话")
        return multi_turn_dialogues
    
    def _create_clarification_dialogue(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """创建澄清对话"""
        question = sample["question"]
        
        # 使用Gemini生成澄清对话
        try:
            dialogue_data = self.gemini_generator.generate_clarifying_dialogue(question)
            if dialogue_data:
                return {
                    "dialogue_type": "clarification",
                    "original_question": question,
                    "is_ambiguous": dialogue_data.get("is_ambiguous", True),
                    "turns": [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": dialogue_data.get("clarifying_question", "请您提供更多信息。")},
                        {"role": "user", "content": dialogue_data.get("user_clarification", "用户提供澄清信息")},
                        {"role": "assistant", "content": dialogue_data.get("final_answer", sample.get("answer", ""))}
                    ],
                    "expected_outcome": "successful_clarification"
                }
        except Exception as e:
            self.logger.warning(f"Gemini生成失败，使用简化版本: {e}")
        
        # 备用简化版本
        return {
            "dialogue_type": "clarification",
            "original_question": question,
            "is_ambiguous": True,
            "turns": [
                {"role": "user", "content": question},
                {"role": "assistant", "content": "请您提供更多具体信息，这样我能更好地帮助您。"},
                {"role": "user", "content": "我需要具体信息"},
                {"role": "assistant", "content": sample.get("answer", "根据您提供的信息，我的回答是...")}
            ],
            "expected_outcome": "successful_clarification"
        }
    
    def _create_step_wise_dialogue(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """创建分步推理对话"""
        question = sample["question"]
        
        # 使用Gemini生成多跳推理对话
        try:
            dialogue_data = self.gemini_generator.generate_multi_hop_dialogue(question)
            if dialogue_data:
                turns = [{"role": "user", "content": question}]
                
                steps = dialogue_data.get("reasoning_steps", [])
                for step in steps:
                    turns.append({"role": "assistant", "content": step.get("ai_question", "让我分析一下...")})
                    turns.append({"role": "user", "content": step.get("user_answer", "用户提供信息")})
                
                turns.append({"role": "assistant", "content": dialogue_data.get("final_answer", sample.get("answer", ""))})
                
                return {
                    "dialogue_type": "multi_step_reasoning",
                    "original_question": question,
                    "reasoning_complexity": "multi_hop",
                    "turns": turns,
                    "expected_outcome": "successful_reasoning"
                }
        except Exception as e:
            self.logger.warning(f"Gemini生成多跳对话失败: {e}")
        
        # 备用版本
        return {
            "dialogue_type": "multi_step_reasoning", 
            "original_question": question,
            "reasoning_complexity": "multi_hop",
            "turns": [
                {"role": "user", "content": question},
                {"role": "assistant", "content": "这个问题需要分步分析，让我先确认第一步信息。"},
                {"role": "user", "content": "请继续分析"},
                {"role": "assistant", "content": sample.get("answer", "基于分析，答案是...")}
            ],
            "expected_outcome": "successful_reasoning"
        }
    
    def _create_math_dialogue(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """创建数学推理对话"""
        question = sample["question"]
        answer = sample.get("answer", "")
        
        return {
            "dialogue_type": "math_reasoning",
            "original_question": question,
            "complexity": "calculation",
            "turns": [
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"让我来计算这个问题。{answer}"}
            ],
            "expected_outcome": "correct_calculation"
        }
    
    def _create_simple_dialogue(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """创建简单对话"""
        return {
            "dialogue_type": "simple_qa",
            "original_question": sample["question"],
            "turns": [
                {"role": "user", "content": sample["question"]},
                {"role": "assistant", "content": sample.get("answer", "我来回答您的问题。")}
            ],
            "expected_outcome": "direct_answer"
        }
    
    def build_comprehensive_training_dataset(self, use_real_data: bool = True) -> Dict[str, Any]:
        """
        构建综合训练数据集
        
        Args:
            use_real_data: 是否使用真实数据集
            
        Returns:
            综合训练数据集
        """
        self.logger.info("开始构建综合训练数据集...")
        
        all_dialogues = []
        dataset_stats = {}
        
        if use_real_data:
            # 尝试加载真实数据集
            for dataset_name in self.dataset_configs.keys():
                try:
                    samples = self.load_sample_data(dataset_name)
                    if samples:
                        dataset_type = samples[0].get("type", "unknown")
                        dialogues = self.convert_to_multi_turn_dialogues(samples, dataset_type)
                        all_dialogues.extend(dialogues)
                        dataset_stats[dataset_name] = len(dialogues)
                except Exception as e:
                    self.logger.warning(f"加载真实数据集{dataset_name}失败: {e}")
        
        # 如果真实数据集加载失败或不使用，使用模拟数据
        if not all_dialogues:
            self.logger.info("使用模拟数据集...")
            mock_datasets = self.create_mock_datasets()
            
            for dataset_name, samples in mock_datasets.items():
                dataset_type = samples[0].get("type", "unknown")
                dialogues = self.convert_to_multi_turn_dialogues(samples, dataset_type)
                all_dialogues.extend(dialogues)
                dataset_stats[dataset_name] = len(dialogues)
        
        # 随机打乱数据
        random.shuffle(all_dialogues)
        
        training_dataset = {
            "version": "1.0",
            "total_dialogues": len(all_dialogues),
            "dataset_distribution": dataset_stats,
            "dialogue_types": {
                "clarification": len([d for d in all_dialogues if d["dialogue_type"] == "clarification"]),
                "multi_step_reasoning": len([d for d in all_dialogues if d["dialogue_type"] == "multi_step_reasoning"]),
                "math_reasoning": len([d for d in all_dialogues if d["dialogue_type"] == "math_reasoning"]),
                "simple_qa": len([d for d in all_dialogues if d["dialogue_type"] == "simple_qa"])
            },
            "dialogues": all_dialogues
        }
        
        self.logger.info(f"构建完成！总计{len(all_dialogues)}个多轮对话")
        self.logger.info(f"数据分布: {dataset_stats}")
        
        return training_dataset
    
    def save_training_dataset(self, dataset: Dict[str, Any], output_file: str = "multi_turn_training_data.json"):
        """保存训练数据集"""
        output_path = Path(output_file)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"训练数据集已保存到: {output_path}")
        
        # 生成数据集统计报告
        self._generate_dataset_report(dataset, output_path.with_suffix('.report.txt'))
    
    def _generate_dataset_report(self, dataset: Dict[str, Any], report_file: Path):
        """生成数据集报告"""
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("多轮对话训练数据集报告\n")
            f.write("=" * 40 + "\n\n")
            
            f.write(f"数据集版本: {dataset['version']}\n")
            f.write(f"总对话数: {dataset['total_dialogues']}\n\n")
            
            f.write("数据来源分布:\n")
            for source, count in dataset['dataset_distribution'].items():
                f.write(f"  {source}: {count} 个对话\n")
            
            f.write("\n对话类型分布:\n")
            for dialogue_type, count in dataset['dialogue_types'].items():
                f.write(f"  {dialogue_type}: {count} 个对话\n")
            
            f.write("\n示例对话:\n")
            if dataset['dialogues']:
                example = dataset['dialogues'][0]
                f.write(f"类型: {example['dialogue_type']}\n")
                f.write(f"原始问题: {example['original_question']}\n")
                f.write("对话轮次:\n")
                for i, turn in enumerate(example['turns']):
                    f.write(f"  {i+1}. {turn['role']}: {turn['content'][:100]}...\n")
        
        self.logger.info(f"数据集报告已保存到: {report_file}")


def main():
    """主函数：构建多轮对话训练数据集"""
    print("多轮对话训练数据集构建器")
    print("=" * 50)
    
    # 初始化数据集扩展器
    expander = DatasetExpander()
    
    # 构建综合训练数据集
    print("🔄 开始构建综合训练数据集...")
    training_dataset = expander.build_comprehensive_training_dataset(use_real_data=False)  # 先使用模拟数据
    
    # 保存数据集
    expander.save_training_dataset(training_dataset)
    
    # 显示统计信息
    print(f"\n📊 数据集构建完成!")
    print(f"   总对话数: {training_dataset['total_dialogues']}")
    print(f"   数据来源: {list(training_dataset['dataset_distribution'].keys())}")
    print(f"   对话类型: {list(training_dataset['dialogue_types'].keys())}")
    
    # 显示示例
    if training_dataset['dialogues']:
        example = training_dataset['dialogues'][0]
        print(f"\n💬 示例对话 ({example['dialogue_type']}):")
        print(f"   问题: {example['original_question']}")
        print(f"   轮次: {len(example['turns'])} 轮")
    
    print(f"\n🎯 多轮对话训练数据集构建完成！")
    print(f"📋 可用于强化学习训练和模型微调")


if __name__ == "__main__":
    main()
