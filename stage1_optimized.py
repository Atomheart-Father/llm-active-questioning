#!/usr/bin/env python3
"""
第一阶段优化版本：基于GPT5架构师指导的改进
主要改进：
1. 启用MPS加速
2. 使用Few-shot学习和自然语言提问
3. 改进prompt设计
4. 更灵活的提问检测机制
"""

import sys
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM
import json
import re
from typing import Dict, List, Tuple

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_config
from src.utils.logging import get_logger


class OptimizedStage1Tester:
    """优化的第一阶段测试器"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger("stage1_optimized")
        self.tokenizer = None
        self.model = None
        
        # 设置设备（优先使用MPS）
        self.device = self._setup_device()
        
        # MVP测试数据
        self.test_cases = self._create_optimized_test_cases()
        self.user_responses = self._create_user_response_mapping()
        
        self.logger.info("优化的第一阶段测试器初始化完成")
    
    def _setup_device(self) -> torch.device:
        """设置最优设备（按GPT5建议优先使用MPS）"""
        if torch.backends.mps.is_available():
            device = torch.device("mps")
            self.logger.info("使用Apple Silicon MPS加速")
        elif torch.cuda.is_available():
            device = torch.device("cuda")
            self.logger.info("使用CUDA GPU")
        else:
            device = torch.device("cpu")
            self.logger.info("使用CPU（性能可能较慢）")
        
        return device
    
    def _create_optimized_test_cases(self) -> List[Dict]:
        """创建优化的测试案例（包含控制案例）"""
        # 需要提问的案例
        ambiguous_cases = [
            {
                "id": 1,
                "type": "代词歧义",
                "question": "他是哪年去世的？",
                "should_ask": True,
                "expected_question_topic": "具体指代人物",
                "complete_info": "爱因斯坦是1955年去世的"
            },
            {
                "id": 2,
                "type": "指代不清",
                "question": "那家餐厅的营业时间是什么？",
                "should_ask": True,
                "expected_question_topic": "餐厅名称",
                "complete_info": "海底捞火锅店的营业时间是11:00-22:00"
            },
            {
                "id": 3,
                "type": "缺少参数",
                "question": "订一张票",
                "should_ask": True,
                "expected_question_topic": "票的类型/目的地",
                "complete_info": "北京到上海的高铁票"
            },
            {
                "id": 4,
                "type": "上下文缺失",
                "question": "这个会议什么时候开始？",
                "should_ask": True,
                "expected_question_topic": "具体会议",
                "complete_info": "项目评审会议下周一上午9点开始"
            },
            {
                "id": 5,
                "type": "模糊指代",
                "question": "她现在住在哪里？",
                "should_ask": True,
                "expected_question_topic": "具体人员",
                "complete_info": "王小红现在住在北京朝阳区"
            }
        ]
        
        # 无需提问的控制案例
        control_cases = [
            {
                "id": 6,
                "type": "完整问题",
                "question": "法国的首都是什么？",
                "should_ask": False,
                "expected_answer": "巴黎",
                "complete_info": "法国的首都是巴黎"
            },
            {
                "id": 7,
                "type": "明确计算",
                "question": "15乘以8等于多少？",
                "should_ask": False,
                "expected_answer": "120",
                "complete_info": "15乘以8等于120"
            },
            {
                "id": 8,
                "type": "具体查询",
                "question": "北京今天的天气怎么样？",
                "should_ask": False,
                "expected_answer": "需要查询实时天气",
                "complete_info": "北京今天多云，气温15-22度"
            }
        ]
        
        return ambiguous_cases + control_cases
    
    def _create_user_response_mapping(self) -> Dict[int, str]:
        """创建用户澄清回答映射"""
        return {
            1: "我是指爱因斯坦。",
            2: "我说的是北京三里屯的海底捞火锅店。",
            3: "我想订从北京到上海的高铁票。",
            4: "我问的是下周一的项目评审会议。",
            5: "我是指我同事王小红。"
        }
    
    def load_model(self) -> bool:
        """加载模型并优化设置"""
        try:
            model_name = self.config.get("model.name", "Qwen/Qwen3-4B-Thinking-2507")
            self.logger.info(f"正在加载模型: {model_name}")
            
            # 加载分词器
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True,
                padding_side="left"
            )
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # 加载模型（根据设备优化）
            if self.device.type == "mps":
                # MPS优化设置
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    torch_dtype=torch.float16,
                    trust_remote_code=True
                ).to(self.device)
            else:
                # 通用设置
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    device_map="auto" if torch.cuda.is_available() else None,
                    trust_remote_code=True,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
                )
            
            self.logger.info(f"模型加载成功，使用设备: {self.device}")
            return True
            
        except Exception as e:
            self.logger.error(f"模型加载失败: {e}")
            return False
    
    def create_few_shot_prompt(self, question: str, mode: str = "with_question") -> str:
        """
        创建包含Few-shot示例的提示词
        
        Args:
            question: 用户问题
            mode: "with_question" 或 "direct_answer"
        """
        if mode == "with_question":
            # 包含Few-shot学习的主动提问模式
            system_prompt = """你是一个智能AI助手。当遇到信息不完整或模糊的问题时，你应该主动向用户提问澄清，而不是猜测。

以下是一些正确处理模糊问题的示例：

示例1：
用户：安排一个会议
助手：好的！请问您希望什么时候安排会议？参与人员有哪些？

示例2：
用户：帮我查一下价格
助手：请问您想查询什么产品的价格呢？

现在请按照同样的方式处理用户的问题。如果信息充足就直接回答，如果信息不足就主动提问澄清。"""

        else:
            # 直接回答模式
            system_prompt = """你是一个AI助手。请根据用户的问题尽力给出回答。"""
        
        prompt = f"""<|im_start|>system
{system_prompt}<|im_end|>
<|im_start|>user
{question}<|im_end|>
<|im_start|>assistant
"""
        return prompt
    
    def generate_response(self, prompt: str) -> str:
        """生成模型回答（优化版本）"""
        if not self.model or not self.tokenizer:
            return "模型未加载"
        
        try:
            # 分词
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=1024
            ).to(self.device)
            
            # 生成参数优化
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=200,  # 减少长度，提高速度
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id
                )
            
            # 解码回答
            input_length = inputs["input_ids"].shape[1]
            response_tokens = outputs[0][input_length:]
            response = self.tokenizer.decode(response_tokens, skip_special_tokens=True)
            
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"生成回答失败: {e}")
            return f"生成失败: {e}"
    
    def detect_question(self, response: str) -> Tuple[bool, str]:
        """
        检测回答中是否包含提问（改进的检测逻辑）
        
        Returns:
            (是否包含提问, 提取的问题内容)
        """
        # 方法1: 检查问号
        if '？' in response or '?' in response:
            # 提取包含问号的句子
            sentences = re.split(r'[。！!.]', response)
            for sentence in sentences:
                if '？' in sentence or '?' in sentence:
                    return True, sentence.strip()
        
        # 方法2: 检查提问关键词
        question_patterns = [
            r'请问.*?[？?]',
            r'能否.*?[？?]',
            r'您.*?[？?]',
            r'什么.*?[？?]',
            r'哪.*?[？?]',
            r'如何.*?[？?]',
            r'是否.*?[？?]'
        ]
        
        for pattern in question_patterns:
            match = re.search(pattern, response)
            if match:
                return True, match.group(0)
        
        # 方法3: 检查原有的<QUESTION>标签（兼容性）
        if "<QUESTION>" in response and "</QUESTION>" in response:
            start = response.find("<QUESTION>") + len("<QUESTION>")
            end = response.find("</QUESTION>")
            question = response[start:end].strip()
            return True, question
        
        return False, ""
    
    def simulate_user_clarification(self, case_id: int, model_question: str) -> str:
        """模拟用户澄清回答（确保协作性）"""
        if case_id in self.user_responses:
            return self.user_responses[case_id]
        else:
            return "请您具体说明一下。"
    
    def run_single_test(self, test_case: Dict, mode: str) -> Dict:
        """运行单个测试案例（优化版本）"""
        case_id = test_case["id"]
        question = test_case["question"]
        should_ask = test_case.get("should_ask", False)
        
        # 创建Few-shot提示词
        prompt = self.create_few_shot_prompt(question, mode)
        
        # 生成第一轮回答
        response = self.generate_response(prompt)
        
        # 检查是否包含提问
        has_question, extracted_question = self.detect_question(response)
        
        result = {
            "case_id": case_id,
            "mode": mode,
            "original_question": question,
            "should_ask": should_ask,
            "first_response": response,
            "has_question": has_question,
            "extracted_question": extracted_question,
            "final_answer": "",
            "success": False,
            "conversation_turns": 1,
            "correct_behavior": False
        }
        
        # 评估行为正确性
        if should_ask:
            # 应该提问的案例
            result["correct_behavior"] = has_question
            
            if has_question:
                # 模拟用户澄清
                user_clarification = self.simulate_user_clarification(case_id, extracted_question)
                
                # 创建第二轮对话
                second_prompt = f"""{prompt.rstrip()}{response}<|im_end|>
<|im_start|>user
{user_clarification}<|im_end|>
<|im_start|>assistant
"""
                
                # 生成最终回答
                final_response = self.generate_response(second_prompt)
                result["final_answer"] = final_response
                result["user_clarification"] = user_clarification
                result["conversation_turns"] = 2
                
                # 判断最终成功（包含具体信息且合理）
                result["success"] = len(final_response) > 10 and "不确定" not in final_response
        else:
            # 不应该提问的案例
            result["correct_behavior"] = not has_question
            result["final_answer"] = response
            result["success"] = len(response) > 5 and not has_question
        
        return result
    
    def run_comparison_experiment(self) -> Dict:
        """运行优化的对比实验"""
        self.logger.info("开始运行优化的对比实验...")
        
        results = {
            "with_question_results": [],
            "direct_answer_results": [],
            "summary": {}
        }
        
        # 测试主动提问模式
        self.logger.info("测试主动提问模式（包含Few-shot学习）...")
        for test_case in self.test_cases:
            result = self.run_single_test(test_case, "with_question")
            results["with_question_results"].append(result)
            
            behavior = "正确" if result["correct_behavior"] else "错误"
            action = "提问" if result["has_question"] else "直答"
            self.logger.info(f"案例 {test_case['id']}: {action} - 行为{behavior}")
        
        # 测试直接回答模式
        self.logger.info("测试直接回答模式...")
        for test_case in self.test_cases:
            result = self.run_single_test(test_case, "direct_answer")
            results["direct_answer_results"].append(result)
        
        # 计算统计信息
        results["summary"] = self._calculate_optimized_summary(results)
        
        return results
    
    def _calculate_optimized_summary(self, results: Dict) -> Dict:
        """计算优化实验的总结统计"""
        with_q = results["with_question_results"]
        direct = results["direct_answer_results"]
        
        # 按是否应该提问分组
        should_ask_cases = [r for r in with_q if r["should_ask"]]
        should_not_ask_cases = [r for r in with_q if not r["should_ask"]]
        
        summary = {
            "总测试案例数": len(self.test_cases),
            "应该提问的案例数": len(should_ask_cases),
            "不应该提问的案例数": len(should_not_ask_cases),
            
            "主动提问模式": {
                # 整体统计
                "总体行为正确率": sum(1 for r in with_q if r["correct_behavior"]) / len(with_q),
                "总体成功率": sum(1 for r in with_q if r["success"]) / len(with_q),
                
                # 应该提问的案例
                "需要提问-实际提问率": sum(1 for r in should_ask_cases if r["has_question"]) / len(should_ask_cases) if should_ask_cases else 0,
                "需要提问-最终成功率": sum(1 for r in should_ask_cases if r["success"]) / len(should_ask_cases) if should_ask_cases else 0,
                
                # 不应该提问的案例
                "无需提问-实际未提问率": sum(1 for r in should_not_ask_cases if not r["has_question"]) / len(should_not_ask_cases) if should_not_ask_cases else 0,
                
                "平均对话轮次": sum(r["conversation_turns"] for r in with_q) / len(with_q)
            },
            
            "直接回答模式": {
                "成功率": sum(1 for r in direct if r["success"]) / len(direct),
                "平均对话轮次": 1.0
            }
        }
        
        # 计算提升
        success_improvement = (summary["主动提问模式"]["总体成功率"] - 
                             summary["直接回答模式"]["成功率"])
        summary["成功率提升"] = success_improvement
        
        return summary
    
    def print_optimized_report(self, results: Dict):
        """打印优化实验报告"""
        summary = results["summary"]
        
        print("\n" + "="*60)
        print("第一阶段优化实验结果总结")
        print("="*60)
        
        print(f"📊 测试案例: {summary['总测试案例数']} (需要提问: {summary['应该提问的案例数']}, 无需提问: {summary['不应该提问的案例数']})")
        print()
        
        print("🤖 主动提问模式（Few-shot优化）:")
        print(f"  ├─ 总体行为正确率: {summary['主动提问模式']['总体行为正确率']:.1%}")
        print(f"  ├─ 总体成功率: {summary['主动提问模式']['总体成功率']:.1%}")
        print(f"  ├─ 需要提问-实际提问率: {summary['主动提问模式']['需要提问-实际提问率']:.1%}")
        print(f"  ├─ 需要提问-最终成功率: {summary['主动提问模式']['需要提问-最终成功率']:.1%}")
        print(f"  ├─ 无需提问-实际未提问率: {summary['主动提问模式']['无需提问-实际未提问率']:.1%}")
        print(f"  └─ 平均轮次: {summary['主动提问模式']['平均对话轮次']:.1f}")
        print()
        
        print("📝 直接回答模式:")
        print(f"  ├─ 成功率: {summary['直接回答模式']['成功率']:.1%}")
        print(f"  └─ 平均轮次: {summary['直接回答模式']['平均对话轮次']:.1f}")
        print()
        
        improvement = summary['成功率提升']
        if improvement > 0:
            print(f"✅ 成功率提升: +{improvement:.1%}")
            print("🎉 主动提问机制显示正面效果！")
        else:
            print(f"❌ 成功率变化: {improvement:.1%}")
            
        behavior_rate = summary['主动提问模式']['总体行为正确率']
        if behavior_rate > 0.5:
            print("✅ 模型行为正确率良好！")
        else:
            print("⚠️ 模型行为需要进一步优化")
        
        print("="*60)
    
    def save_results(self, results: Dict, output_file: str = "stage1_optimized_results.json"):
        """保存优化实验结果"""
        output_path = Path(output_file)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"优化实验结果已保存到: {output_path}")


def main():
    """主函数"""
    print("开始第一阶段优化实验")
    print("基于GPT5架构师指导的改进方案")
    print("="*60)
    
    # 初始化优化测试器
    tester = OptimizedStage1Tester()
    
    # 加载模型（启用MPS加速）
    print("🔄 正在加载Qwen3-4B-Thinking模型（启用加速）...")
    if not tester.load_model():
        print("❌ 模型加载失败，退出测试")
        return
    
    print("✅ 模型加载成功，开始性能测试")
    
    # 运行优化的对比实验
    print("\n🧪 开始运行优化的MVP实验...")
    print("改进项: Few-shot学习 + 自然语言提问 + MPS加速")
    
    results = tester.run_comparison_experiment()
    
    # 保存和报告结果
    tester.save_results(results)
    tester.print_optimized_report(results)
    
    print("\n🎯 第一阶段优化实验完成！")
    print("📋 准备向产品经理和GPT5架构师汇报结果")


if __name__ == "__main__":
    main()
