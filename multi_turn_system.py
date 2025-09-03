#!/usr/bin/env python3
"""
多轮交互系统框架
支持主动提问-用户回答-继续推理的完整流程
"""

import sys
import torch
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from transformers import AutoTokenizer, AutoModelForCausalLM
from enum import Enum

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_config
from src.utils.logging import get_logger
# REMOVED: from gemini_integration import GeminiDataGenerator


class InteractionMode(Enum):
    """交互模式枚举"""
    ACTIVE_QUESTIONING = "active_questioning"  # 主动提问模式
    STANDARD_QA = "standard_qa"  # 标准问答模式
    USER_INTERRUPT = "user_interrupt"  # 用户打断模式


class ConversationState(Enum):
    """对话状态枚举"""
    INITIAL_QUERY = "initial_query"  # 初始查询
    CLARIFICATION_NEEDED = "clarification_needed"  # 需要澄清
    CLARIFICATION_PROVIDED = "clarification_provided"  # 澄清已提供
    FINAL_ANSWER = "final_answer"  # 最终答案
    USER_INTERRUPTED = "user_interrupted"  # 用户打断
    COMPLETED = "completed"  # 对话完成


class MultiTurnInteractionSystem:
    """多轮交互系统"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger("multi_turn_system")
        
        # 模型和组件
        self.tokenizer = None
        self.model = None
        self.gemini_generator = None
        
        # 设备配置
        self.device = self._setup_device()
        
        # 交互统计
        self.interaction_stats = {
            "total_conversations": 0,
            "successful_clarifications": 0,
            "user_interruptions": 0,
            "direct_answers": 0
        }
        
        self.logger.info("多轮交互系统初始化完成")
    
    def _setup_device(self) -> torch.device:
        """设置设备"""
        if torch.backends.mps.is_available():
            device = torch.device("mps")
            self.logger.info("使用Apple Silicon MPS加速")
        elif torch.cuda.is_available():
            device = torch.device("cuda")
            self.logger.info("使用CUDA GPU")
        else:
            device = torch.device("cpu")
            self.logger.info("使用CPU")
        
        return device
    
    def initialize_components(self):
        """初始化所有组件"""
        self.logger.info("初始化系统组件...")
        
        # 初始化模型
        self._load_model()
        
        # 初始化Gemini生成器
        self.gemini_generator = GeminiDataGenerator()
        
        self.logger.info("所有组件初始化完成")
    
    def _load_model(self):
        """加载语言模型"""
        try:
            model_name = self.config.get("model.name", "Qwen/Qwen3-4B-Thinking-2507")
            self.logger.info(f"加载模型: {model_name}")
            
            # 加载分词器
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True,
                padding_side="left"
            )
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # 加载模型
            if self.device.type == "mps":
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    torch_dtype=torch.float16,
                    trust_remote_code=True
                ).to(self.device)
            else:
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    device_map="auto" if torch.cuda.is_available() else None,
                    trust_remote_code=True,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
                )
            
            self.logger.info("模型加载成功")
            
        except Exception as e:
            self.logger.error(f"模型加载失败: {e}")
            raise
    
    def create_multi_turn_prompt(self, conversation_history: List[Dict[str, str]], 
                                mode: InteractionMode = InteractionMode.ACTIVE_QUESTIONING) -> str:
        """
        创建多轮对话的提示词
        
        Args:
            conversation_history: 对话历史 [{"role": "user/assistant", "content": "..."}]
            mode: 交互模式
            
        Returns:
            格式化的提示词
        """
        if mode == InteractionMode.ACTIVE_QUESTIONING:
            system_prompt = """你是一个智能AI助手，能够通过多轮对话来准确理解和回答用户问题。

核心原则：
1. 如果用户问题明确且信息充足，直接给出准确答案
2. 如果问题模糊或缺少关键信息，主动提出一个具体的澄清问题
3. 在得到用户澄清后，结合所有信息给出完整答案
4. 保持对话自然流畅，避免不必要的提问

对话示例：
用户：他什么时候出生的？
助手：请问您指的是哪位人物呢？
用户：爱因斯坦
助手：爱因斯坦于1879年3月14日出生于德国乌尔姆。"""

        elif mode == InteractionMode.STANDARD_QA:
            system_prompt = """你是一个AI助手，请直接回答用户的问题，不要提出额外的澄清问题。"""
        
        else:
            system_prompt = """你是一个适应性强的AI助手，能够根据对话情况灵活调整回答策略。"""
        
        # 构建完整对话
        prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
        
        for turn in conversation_history:
            role = turn["role"]
            content = turn["content"]
            prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
        
        prompt += "<|im_start|>assistant\n"
        
        return prompt
    
    def generate_response(self, prompt: str) -> str:
        """生成模型回答"""
        if not self.model or not self.tokenizer:
            return "模型未初始化"
        
        try:
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=1500
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=200,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id
                )
            
            input_length = inputs["input_ids"].shape[1]
            response_tokens = outputs[0][input_length:]
            response = self.tokenizer.decode(response_tokens, skip_special_tokens=True)
            
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"生成回答失败: {e}")
            return f"生成失败: {e}"
    
    def detect_clarification_need(self, response: str) -> Tuple[bool, str]:
        """
        检测是否需要澄清
        
        Returns:
            (是否需要澄清, 提取的问题)
        """
        # 检查问号
        if '？' in response or '?' in response:
            # 提取问题
            import re
            sentences = re.split(r'[。！!.]', response)
            for sentence in sentences:
                if '？' in sentence or '?' in sentence:
                    return True, sentence.strip()
        
        # 检查澄清关键词
        clarification_patterns = [
            r'请问.*?[？?]',
            r'您.*?[？?]',
            r'哪.*?[？?]',
            r'什么.*?[？?]',
            r'能否.*?[？?]'
        ]
        
        import re
        for pattern in clarification_patterns:
            match = re.search(pattern, response)
            if match:
                return True, match.group(0)
        
        return False, ""
    
    def simulate_user_response(self, clarification_question: str, original_question: str, 
                              mode: str = "cooperative") -> str:
        """
        模拟用户回答澄清问题
        
        Args:
            clarification_question: 澄清问题
            original_question: 原始问题
            mode: 模拟模式 ("cooperative", "uncooperative", "interrupt")
            
        Returns:
            模拟的用户回答
        """
        if mode == "uncooperative":
            uncooperative_responses = [
                "我不想回答这个问题。",
                "你应该能理解我的意思。",
                "算了，不问了。"
            ]
            import random
            return random.choice(uncooperative_responses)
        
        elif mode == "interrupt":
            interrupt_responses = [
                "等等，我想问另一个问题。",
                "先别管这个，你能告诉我...",
                "我改主意了，我想知道..."
            ]
            import random
            return random.choice(interrupt_responses)
        
        else:  # cooperative mode
            # 使用Gemini生成合理的澄清回答
            if self.gemini_generator:
                try:
                    prompt = f"""
基于以下对话情况，生成一个合理的用户澄清回答。

原始问题: {original_question}
AI的澄清问题: {clarification_question}

请生成一个自然、有帮助的用户回答，提供AI需要的具体信息。回答应该简洁明确。

示例：
原始问题: "他什么时候出生的？"
澄清问题: "请问您指的是哪位人物？"
用户回答: "我说的是爱因斯坦。"

请直接输出用户的回答，不要包含其他内容。
"""
                    
                    response = self.gemini_generator._make_request(prompt)
                    if response:
                        return response.strip()
                
                except Exception as e:
                    self.logger.warning(f"Gemini生成用户回答失败: {e}")
            
            # 备用的简单回答
            return "我需要更具体的信息，请您详细说明。"
    
    def run_conversation(self, initial_question: str, 
                        interaction_mode: InteractionMode = InteractionMode.ACTIVE_QUESTIONING,
                        user_simulation_mode: str = "cooperative",
                        max_turns: int = 5) -> Dict[str, Any]:
        """
        运行完整的多轮对话
        
        Args:
            initial_question: 初始问题
            interaction_mode: 交互模式
            user_simulation_mode: 用户模拟模式
            max_turns: 最大轮次
            
        Returns:
            对话结果和统计信息
        """
        conversation_id = f"conv_{int(time.time())}"
        self.logger.info(f"开始对话 {conversation_id}: {initial_question}")
        
        # 初始化对话状态
        conversation_history = [{"role": "user", "content": initial_question}]
        state = ConversationState.INITIAL_QUERY
        turn_count = 1
        
        conversation_log = {
            "conversation_id": conversation_id,
            "initial_question": initial_question,
            "interaction_mode": interaction_mode.value,
            "user_simulation_mode": user_simulation_mode,
            "turns": [],
            "final_state": None,
            "success": False,
            "total_turns": 0
        }
        
        while turn_count <= max_turns and state not in [ConversationState.COMPLETED, ConversationState.USER_INTERRUPTED]:
            
            # 生成AI回答
            prompt = self.create_multi_turn_prompt(conversation_history, interaction_mode)
            ai_response = self.generate_response(prompt)
            
            conversation_history.append({"role": "assistant", "content": ai_response})
            
            # 检测是否需要澄清
            needs_clarification, clarification_question = self.detect_clarification_need(ai_response)
            
            # 记录当前轮次
            turn_data = {
                "turn": turn_count,
                "ai_response": ai_response,
                "needs_clarification": needs_clarification,
                "clarification_question": clarification_question,
                "state": state.value
            }
            
            if needs_clarification and state == ConversationState.INITIAL_QUERY:
                # 需要澄清，模拟用户回答
                state = ConversationState.CLARIFICATION_NEEDED
                
                user_clarification = self.simulate_user_response(
                    clarification_question, 
                    initial_question, 
                    user_simulation_mode
                )
                
                conversation_history.append({"role": "user", "content": user_clarification})
                
                turn_data["user_clarification"] = user_clarification
                turn_data["user_simulation_mode"] = user_simulation_mode
                
                # 检查用户是否合作
                if user_simulation_mode == "uncooperative":
                    state = ConversationState.USER_INTERRUPTED
                elif user_simulation_mode == "interrupt":
                    state = ConversationState.USER_INTERRUPTED
                else:
                    state = ConversationState.CLARIFICATION_PROVIDED
                
            elif not needs_clarification:
                # 直接回答，对话完成
                state = ConversationState.FINAL_ANSWER
                conversation_log["success"] = True
                
            conversation_log["turns"].append(turn_data)
            turn_count += 1
            
            # 如果状态是澄清已提供，下一轮将生成最终答案
            if state == ConversationState.CLARIFICATION_PROVIDED:
                state = ConversationState.FINAL_ANSWER
        
        # 最终状态
        conversation_log["final_state"] = state.value
        conversation_log["total_turns"] = turn_count - 1
        
        # 更新统计
        self.interaction_stats["total_conversations"] += 1
        if conversation_log["success"]:
            if any(turn.get("needs_clarification") for turn in conversation_log["turns"]):
                self.interaction_stats["successful_clarifications"] += 1
            else:
                self.interaction_stats["direct_answers"] += 1
        
        if state == ConversationState.USER_INTERRUPTED:
            self.interaction_stats["user_interruptions"] += 1
        
        self.logger.info(f"对话完成 {conversation_id}: {state.value}, 成功: {conversation_log['success']}")
        
        return conversation_log
    
    def batch_conversation_test(self, test_questions: List[str], 
                               test_scenarios: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        批量对话测试
        
        Args:
            test_questions: 测试问题列表
            test_scenarios: 测试场景配置
            
        Returns:
            批量测试结果
        """
        if test_scenarios is None:
            test_scenarios = [
                {"interaction_mode": InteractionMode.ACTIVE_QUESTIONING, "user_mode": "cooperative"},
                {"interaction_mode": InteractionMode.ACTIVE_QUESTIONING, "user_mode": "uncooperative"},
                {"interaction_mode": InteractionMode.STANDARD_QA, "user_mode": "cooperative"}
            ]
        
        self.logger.info(f"开始批量测试: {len(test_questions)}个问题 x {len(test_scenarios)}个场景")
        
        all_results = []
        
        for question in test_questions:
            question_results = {"question": question, "scenarios": []}
            
            for scenario in test_scenarios:
                result = self.run_conversation(
                    question,
                    scenario["interaction_mode"],
                    scenario["user_mode"]
                )
                result["scenario_config"] = scenario
                question_results["scenarios"].append(result)
            
            all_results.append(question_results)
        
        # 生成总结报告
        summary = self._generate_batch_summary(all_results)
        
        return {
            "results": all_results,
            "summary": summary,
            "system_stats": self.interaction_stats
        }
    
    def _generate_batch_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成批量测试总结"""
        total_conversations = sum(len(r["scenarios"]) for r in results)
        successful_conversations = sum(
            sum(1 for s in r["scenarios"] if s["success"]) 
            for r in results
        )
        
        clarification_conversations = sum(
            sum(1 for s in r["scenarios"] 
                if any(turn.get("needs_clarification") for turn in s["turns"])) 
            for r in results
        )
        
        return {
            "total_questions": len(results),
            "total_conversations": total_conversations,
            "success_rate": successful_conversations / total_conversations if total_conversations > 0 else 0,
            "clarification_rate": clarification_conversations / total_conversations if total_conversations > 0 else 0,
            "avg_turns_per_conversation": sum(
                sum(s["total_turns"] for s in r["scenarios"]) 
                for r in results
            ) / total_conversations if total_conversations > 0 else 0
        }
    
    def save_conversation_data(self, results: Dict[str, Any], output_file: str):
        """保存对话数据"""
        output_path = Path(output_file)
        
        # 自定义JSON编码器处理枚举类型
        def json_serializer(obj):
            if isinstance(obj, (InteractionMode, ConversationState)):
                return obj.value
            raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=json_serializer)
        
        self.logger.info(f"对话数据已保存到: {output_path}")


def main():
    """主函数：演示多轮交互系统"""
    print("多轮交互系统演示")
    print("="*50)
    
    # 初始化系统
    system = MultiTurnInteractionSystem()
    system.initialize_components()
    
    # 测试问题
    test_questions = [
        "他什么时候出生的？",  # 需要澄清
        "那家餐厅好吃吗？",    # 需要澄清
        "中国的首都是什么？",  # 不需要澄清
        "预订一张票",          # 需要澄清
        "谁是《哈利波特》作者的丈夫？"  # 复杂推理
    ]
    
    print(f"🧪 开始测试{len(test_questions)}个问题...")
    
    # 运行批量测试
    results = system.batch_conversation_test(test_questions)
    
    # 保存结果
    system.save_conversation_data(results, "multi_turn_test_results.json")
    
    # 显示总结
    summary = results["summary"]
    print(f"\n📊 测试结果总结:")
    print(f"   总问题数: {summary['total_questions']}")
    print(f"   总对话数: {summary['total_conversations']}")
    print(f"   成功率: {summary['success_rate']:.1%}")
    print(f"   澄清率: {summary['clarification_rate']:.1%}")
    print(f"   平均轮次: {summary['avg_turns_per_conversation']:.1f}")
    
    print(f"\n🎯 多轮交互系统测试完成！")
    print(f"📋 数据已收集，可用于后续强化学习训练")


if __name__ == "__main__":
    main()
