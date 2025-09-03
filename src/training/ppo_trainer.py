"""
PPO训练模块
基于TRL库实现强化学习训练循环
"""

import os
import torch
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM,
    TrainingArguments,
    BitsAndBytesConfig
)
from trl import PPOTrainer, PPOConfig, AutoModelForCausalLMWithValueHead
from peft import LoraConfig, get_peft_model, TaskType
import numpy as np
from datasets import Dataset

from .reward_system import RewardCalculator
# Optional import for GPT-4 evaluation (Sidecar)
try:
    from integrations.simulation.gpt4_simulator import GPT4UserSimulator
    GPT4_AVAILABLE = True
except ImportError:
    GPT4_AVAILABLE = False
    GPT4UserSimulator = None
from ..utils.config import get_config
from ..utils.logging import get_logger


@dataclass
class PPOTrainingConfig:
    """PPO训练配置"""
    model_name: str = "Qwen/Qwen3-4B-Thinking-2507"
    max_length: int = 2048
    batch_size: int = 8
    mini_batch_size: int = 2
    gradient_accumulation_steps: int = 4
    learning_rate: float = 1.41e-5
    num_epochs: int = 3
    ppo_epochs: int = 4
    clip_range: float = 0.2
    kl_coef: float = 0.02
    vf_coef: float = 0.1
    target_kl: float = 0.01
    max_grad_norm: float = 1.0
    use_lora: bool = True
    load_in_8bit: bool = False
    load_in_4bit: bool = False


class PPOModelTrainer:
    """PPO模型训练器"""
    
    def __init__(self, config: PPOTrainingConfig = None):
        """
        初始化PPO训练器
        
        Args:
            config: 训练配置
        """
        self.global_config = get_config()
        self.logger = get_logger()
        
        # 设置训练配置
        if config is None:
            config = self._create_config_from_global()
        self.config = config
        
        # 初始化组件
        self.tokenizer = None
        self.model = None
        self.ppo_trainer = None
        self.reward_calculator = None
        self.gpt4_simulator = None
        
        # 设置设备
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.logger.info(f"使用设备: {self.device}")
        
        self.logger.info("PPO训练器初始化完成")
    
    def _create_config_from_global(self) -> PPOTrainingConfig:
        """从全局配置创建PPO配置"""
        model_config = self.global_config.model_config
        training_config = self.global_config.training_config
        
        return PPOTrainingConfig(
            model_name=model_config.get("name", "Qwen/Qwen2.5-7B-Instruct"),
            max_length=model_config.get("max_length", 2048),
            batch_size=training_config.get("batch_size", 8),
            mini_batch_size=training_config.get("mini_batch_size", 2),
            gradient_accumulation_steps=training_config.get("gradient_accumulation_steps", 4),
            learning_rate=training_config.get("learning_rate", 1.41e-5),
            num_epochs=training_config.get("num_epochs", 3),
            ppo_epochs=training_config.get("ppo_epochs", 4),
            clip_range=training_config.get("clip_range", 0.2),
            kl_coef=training_config.get("kl_coef", 0.02),
            vf_coef=training_config.get("vf_coef", 0.1),
            target_kl=training_config.get("target_kl", 0.01),
            max_grad_norm=training_config.get("max_grad_norm", 1.0),
            use_lora=model_config.get("use_lora", True),
            load_in_8bit=model_config.get("load_in_8bit", False),
            load_in_4bit=model_config.get("load_in_4bit", False)
        )
    
    def setup_model_and_tokenizer(self):
        """设置模型和分词器"""
        self.logger.info(f"加载模型: {self.config.model_name}")
        
        # 加载分词器
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_name,
            trust_remote_code=True,
            padding_side="left"
        )
        
        # 设置pad token
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        # 量化配置
        quantization_config = None
        if self.config.load_in_4bit:
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
        elif self.config.load_in_8bit:
            quantization_config = BitsAndBytesConfig(load_in_8bit=True)
        
        # 加载模型
        model = AutoModelForCausalLM.from_pretrained(
            self.config.model_name,
            quantization_config=quantization_config,
            device_map="auto" if torch.cuda.is_available() else None,
            trust_remote_code=True,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
        )
        
        # 添加值函数头
        self.model = AutoModelForCausalLMWithValueHead.from_pretrained(model)
        
        # 应用LoRA（如果启用）
        if self.config.use_lora:
            lora_config = LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                inference_mode=False,
                r=16,
                lora_alpha=32,
                lora_dropout=0.1,
                target_modules=["q_proj", "v_proj", "k_proj", "o_proj"]
            )
            self.model = get_peft_model(self.model, lora_config)
            self.logger.info("已应用LoRA配置")
        
        self.logger.info("模型和分词器设置完成")
    
    def setup_ppo_trainer(self):
        """设置PPO训练器"""
        # PPO配置
        ppo_config = PPOConfig(
            model_name=self.config.model_name,
            learning_rate=self.config.learning_rate,
            batch_size=self.config.batch_size,
            mini_batch_size=self.config.mini_batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            ppo_epochs=self.config.ppo_epochs,
            cliprange=self.config.clip_range,
            kl_coef=self.config.kl_coef,
            vf_coef=self.config.vf_coef,
            target_kl=self.config.target_kl,
            max_grad_norm=self.config.max_grad_norm,
        )
        
        # 创建PPO训练器
        self.ppo_trainer = PPOTrainer(
            config=ppo_config,
            model=self.model,
            tokenizer=self.tokenizer,
        )
        
        self.logger.info("PPO训练器设置完成")
    
    def setup_reward_system(self):
        """设置奖励系统"""
        # 初始化GPT-4模拟器（如果配置了API密钥）
        try:
            api_key = self.global_config.get("simulation.openai_api_key")
            if api_key and GPT4_AVAILABLE:
                self.gpt4_simulator = GPT4UserSimulator(api_key)
                self.logger.info("GPT-4模拟器初始化完成")
            else:
                if not GPT4_AVAILABLE:
                    self.logger.warning("GPT-4模拟器模块不可用")
                else:
                    self.logger.warning("未配置OpenAI API密钥，将跳过GPT-4偏好评估")
        except Exception as e:
            self.logger.warning(f"GPT-4模拟器初始化失败: {e}")
        
        # 初始化奖励计算器
        self.reward_calculator = RewardCalculator(self.gpt4_simulator)
        self.logger.info("奖励系统设置完成")
    
    def format_prompt(self, sample: Dict[str, Any]) -> str:
        """
        格式化输入提示
        
        Args:
            sample: 训练样本
            
        Returns:
            格式化的提示字符串
        """
        user_input = sample.get('user', '')
        
        # 构建对话格式
        prompt = f"<|im_start|>system\n你是一个有用的AI助手。如果遇到不确定或需要澄清的问题，可以主动向用户提问以获得更准确的信息。<|im_end|>\n"
        prompt += f"<|im_start|>user\n{user_input}<|im_end|>\n"
        prompt += f"<|im_start|>assistant\n"
        
        return prompt
    
    def generate_responses(self, prompts: List[str]) -> List[str]:
        """
        生成模型回答
        
        Args:
            prompts: 提示列表
            
        Returns:
            生成的回答列表
        """
        # 分词
        inputs = self.tokenizer(
            prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.config.max_length
        ).to(self.device)
        
        # 生成回答
        with torch.no_grad():
            outputs = self.model.generate(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                max_new_tokens=512,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )
        
        # 解码回答
        responses = []
        for i, output in enumerate(outputs):
            # 去除输入部分
            input_length = inputs["input_ids"][i].shape[0]
            response_tokens = output[input_length:]
            
            # 解码
            response = self.tokenizer.decode(response_tokens, skip_special_tokens=True)
            responses.append(response.strip())
        
        return responses
    
    def compute_rewards(self, samples: List[Dict[str, Any]], responses: List[str], prompts: List[str]) -> List[float]:
        """
        计算奖励
        
        Args:
            samples: 样本列表
            responses: 回答列表
            prompts: 提示列表
            
        Returns:
            奖励列表
        """
        # 提取用户问题
        questions = [sample.get('user', '') for sample in samples]
        
        # 批量计算奖励
        reward_breakdowns = self.reward_calculator.batch_calculate_rewards(
            samples, responses, questions
        )
        
        # 提取总奖励
        rewards = [breakdown['total'] for breakdown in reward_breakdowns]
        
        # 记录奖励统计
        avg_reward = np.mean(rewards)
        self.logger.info(f"平均奖励: {avg_reward:.4f}")
        
        return rewards
    
    def train_step(self, batch_samples: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        执行一步训练
        
        Args:
            batch_samples: 批次样本
            
        Returns:
            训练统计信息
        """
        # 格式化提示
        prompts = [self.format_prompt(sample) for sample in batch_samples]
        
        # 生成回答
        responses = self.generate_responses(prompts)
        
        # 计算奖励
        rewards = self.compute_rewards(batch_samples, responses, prompts)
        
        # 分词处理
        query_tensors = []
        response_tensors = []
        
        for prompt, response in zip(prompts, responses):
            # 分词查询
            query_tokens = self.tokenizer.encode(prompt, return_tensors="pt").squeeze()
            query_tensors.append(query_tokens)
            
            # 分词回答
            response_tokens = self.tokenizer.encode(response, return_tensors="pt").squeeze()
            response_tensors.append(response_tokens)
        
        # 转换为张量
        reward_tensors = [torch.tensor(reward) for reward in rewards]
        
        # PPO训练步骤
        stats = self.ppo_trainer.step(query_tensors, response_tensors, reward_tensors)
        
        # 添加自定义统计
        stats.update({
            'rewards/mean': np.mean(rewards),
            'rewards/std': np.std(rewards),
            'rewards/min': np.min(rewards),
            'rewards/max': np.max(rewards)
        })
        
        return stats
    
    def train(self, train_dataset: Dataset, eval_dataset: Dataset = None, num_epochs: int = None):
        """
        执行完整训练
        
        Args:
            train_dataset: 训练数据集
            eval_dataset: 评估数据集
            num_epochs: 训练轮数
        """
        if num_epochs is None:
            num_epochs = self.config.num_epochs
        
        self.logger.info(f"开始PPO训练，共{num_epochs}轮，训练样本{len(train_dataset)}条")
        
        # 设置所有组件
        self.setup_model_and_tokenizer()
        self.setup_ppo_trainer()
        self.setup_reward_system()
        
        # 训练循环
        global_step = 0
        
        for epoch in range(num_epochs):
            self.logger.info(f"开始第{epoch + 1}/{num_epochs}轮训练")
            
            # 打乱数据
            shuffled_indices = np.random.permutation(len(train_dataset))
            
            # 批次训练
            for batch_start in range(0, len(train_dataset), self.config.batch_size):
                batch_end = min(batch_start + self.config.batch_size, len(train_dataset))
                batch_indices = shuffled_indices[batch_start:batch_end]
                
                # 获取批次样本
                batch_samples = [train_dataset[i] for i in batch_indices]
                
                # 训练步骤
                try:
                    stats = self.train_step(batch_samples)
                    global_step += 1
                    
                    # 记录统计信息
                    if global_step % 10 == 0:
                        self.logger.log_metrics(stats, step=global_step)
                    
                    # 评估和保存
                    if global_step % 100 == 0:
                        if eval_dataset:
                            self.evaluate(eval_dataset)
                        self.save_checkpoint(global_step)
                    
                except Exception as e:
                    self.logger.error(f"训练步骤失败: {e}")
                    continue
            
            self.logger.info(f"第{epoch + 1}轮训练完成")
        
        # 保存最终模型
        self.save_model("final_model")
        self.logger.info("PPO训练完成")
    
    def evaluate(self, eval_dataset: Dataset) -> Dict[str, float]:
        """
        评估模型
        
        Args:
            eval_dataset: 评估数据集
            
        Returns:
            评估结果
        """
        self.logger.info("开始模型评估...")
        
        eval_samples = eval_dataset[:min(100, len(eval_dataset))]  # 最多评估100个样本
        prompts = [self.format_prompt(sample) for sample in eval_samples]
        
        # 生成回答
        responses = self.generate_responses(prompts)
        
        # 计算奖励
        rewards = self.compute_rewards(eval_samples, responses, prompts)
        
        eval_results = {
            'eval/mean_reward': np.mean(rewards),
            'eval/std_reward': np.std(rewards),
            'eval/min_reward': np.min(rewards),
            'eval/max_reward': np.max(rewards)
        }
        
        self.logger.log_metrics(eval_results)
        self.logger.info(f"评估完成，平均奖励: {eval_results['eval/mean_reward']:.4f}")
        
        return eval_results
    
    def save_checkpoint(self, step: int):
        """保存检查点"""
        checkpoint_dir = f"./logs/checkpoint-{step}"
        os.makedirs(checkpoint_dir, exist_ok=True)
        
        self.model.save_pretrained(checkpoint_dir)
        self.tokenizer.save_pretrained(checkpoint_dir)
        
        self.logger.info(f"检查点已保存到: {checkpoint_dir}")
    
    def save_model(self, output_dir: str):
        """保存最终模型"""
        os.makedirs(output_dir, exist_ok=True)
        
        self.model.save_pretrained(output_dir)
        self.tokenizer.save_pretrained(output_dir)
        
        self.logger.info(f"模型已保存到: {output_dir}")
