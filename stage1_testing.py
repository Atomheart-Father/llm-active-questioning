#!/usr/bin/env python3
"""
第一阶段测试脚本：核心概念验证
主要任务：
1. 验证Qwen3-4B-Thinking模型加载
2. 实现基础的主动提问机制
3. 构建MVP测试数据
4. 进行初步对比实验
"""

import sys
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM
import json
from typing import Dict, List, Tuple

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_config
from src.utils.logging import get_logger


class Stage1Tester:
    """第一阶段测试器"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger("stage1_test")
        self.tokenizer = None
        self.model = None
        
        # MVP测试数据
        self.test_cases = self._create_mvp_test_cases()
        self.user_responses = self._create_user_response_mapping()
        
        self.logger.info("第一阶段测试器初始化完成")
    
    def _create_mvp_test_cases(self) -> List[Dict]:
        """创建MVP测试案例 - 5-10个精心设计的场景"""
        return [
            {
                "id": 1,
                "type": "歧义型",
                "question": "他是哪年去世的？",
                "context": "",
                "expected_behavior": "提问澄清指代对象",
                "correct_answer": "需要知道具体指谁才能回答"
            },
            {
                "id": 2,
                "type": "上下文不足型", 
                "question": "那家餐厅的营业时间是什么？",
                "context": "",
                "expected_behavior": "提问具体餐厅名称",
                "correct_answer": "需要知道具体餐厅名称"
            },
            {
                "id": 3,
                "type": "模糊表述型",
                "question": "她现在住在哪里？",
                "context": "",
                "expected_behavior": "提问指代的具体人员",
                "correct_answer": "需要明确是哪位女性"
            },
            {
                "id": 4,
                "type": "歧义型",
                "question": "这个会议什么时候开始？",
                "context": "",
                "expected_behavior": "提问具体会议",
                "correct_answer": "需要知道是哪个会议"
            },
            {
                "id": 5,
                "type": "上下文不足型",
                "question": "票价是多少？",
                "context": "",
                "expected_behavior": "提问什么票/哪里的票",
                "correct_answer": "需要知道具体票务信息"
            },
            {
                "id": 6,
                "type": "模糊表述型",
                "question": "那个项目进展如何？",
                "context": "",
                "expected_behavior": "提问具体项目名称",
                "correct_answer": "需要明确是哪个项目"
            },
            {
                "id": 7,
                "type": "歧义型",
                "question": "它的重量是多少？",
                "context": "",
                "expected_behavior": "提问指代物品",
                "correct_answer": "需要知道指的是什么物品"
            },
            {
                "id": 8,
                "type": "上下文不足型",
                "question": "天气怎么样？",
                "context": "",
                "expected_behavior": "提问具体时间地点",
                "correct_answer": "需要知道哪里、什么时候的天气"
            }
        ]
    
    def _create_user_response_mapping(self) -> Dict[int, str]:
        """创建用户澄清回答映射"""
        return {
            1: "我是指爱因斯坦，阿尔伯特·爱因斯坦。",
            2: "我说的是北京三里屯的海底捞火锅店。",
            3: "我是指我的同事李小明的妻子王小红。",
            4: "我是指下周一的项目评审会议。",
            5: "我想问的是从北京到上海的高铁票价。",
            6: "我说的是我们公司的AI聊天机器人项目。",
            7: "我是指刚买的新款MacBook Pro。",
            8: "我想知道明天北京的天气情况。"
        }
    
    def load_model(self) -> bool:
        """加载Qwen3-4B-Thinking模型"""
        try:
            model_name = self.config.get("model.name", "Qwen/Qwen3-4B-Thinking-2507")
            self.logger.info(f"正在加载模型: {model_name}")
            
            # 加载分词器
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True,
                padding_side="left"
            )
            
            # 设置pad token
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # 加载模型
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                device_map="auto" if torch.cuda.is_available() else "cpu",
                trust_remote_code=True,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
            )
            
            self.logger.info("模型加载成功")
            return True
            
        except Exception as e:
            self.logger.error(f"模型加载失败: {e}")
            return False
    
    def create_prompts(self, question: str, mode: str = "with_question") -> str:
        """
        创建不同模式的提示词
        
        Args:
            question: 用户问题
            mode: "with_question" 或 "direct_answer"
        """
        if mode == "with_question":
            # 带主动提问机制的prompt
            system_prompt = """你是一个聪明的AI助手。当你发现问题信息不完整、存在歧义或无法准确回答时，应该主动向用户提问澄清，而不是猜测或臆断。

如果你需要更多信息才能准确回答，请使用以下格式：
<QUESTION>你的澄清问题</QUESTION>

如果信息充足可以直接回答，就正常回答即可。"""
        else:
            # 直接回答模式的prompt  
            system_prompt = """你是一个AI助手。请根据用户的问题尽力给出回答。"""
        
        prompt = f"""<|im_start|>system
{system_prompt}<|im_end|>
<|im_start|>user
{question}<|im_end|>
<|im_start|>assistant
"""
        return prompt
    
    def generate_response(self, prompt: str) -> str:
        """生成模型回答"""
        if not self.model or not self.tokenizer:
            return "模型未加载"
        
        try:
            # 分词
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=1024
            )
            
            # 移动到模型设备
            if torch.cuda.is_available():
                inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
            
            # 生成
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=256,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id
                )
            
            # 解码回答（去除输入部分）
            input_length = inputs["input_ids"].shape[1]
            response_tokens = outputs[0][input_length:]
            response = self.tokenizer.decode(response_tokens, skip_special_tokens=True)
            
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"生成回答失败: {e}")
            return f"生成失败: {e}"
    
    def extract_question(self, response: str) -> Tuple[bool, str]:
        """
        从回答中提取提问
        
        Returns:
            (是否包含提问, 提取的问题内容)
        """
        if "<QUESTION>" in response and "</QUESTION>" in response:
            start = response.find("<QUESTION>") + len("<QUESTION>")
            end = response.find("</QUESTION>")
            question = response[start:end].strip()
            return True, question
        return False, ""
    
    def simulate_user_clarification(self, case_id: int, model_question: str) -> str:
        """模拟用户澄清回答"""
        if case_id in self.user_responses:
            return self.user_responses[case_id]
        else:
            return "我不确定你在问什么。"
    
    def run_single_test(self, test_case: Dict, mode: str) -> Dict:
        """运行单个测试案例"""
        case_id = test_case["id"]
        question = test_case["question"]
        
        # 创建提示词
        prompt = self.create_prompts(question, mode)
        
        # 生成第一轮回答
        response = self.generate_response(prompt)
        
        # 检查是否包含提问
        has_question, extracted_question = self.extract_question(response)
        
        result = {
            "case_id": case_id,
            "mode": mode,
            "original_question": question,
            "first_response": response,
            "has_question": has_question,
            "extracted_question": extracted_question,
            "final_answer": "",
            "success": False,
            "conversation_turns": 1
        }
        
        if mode == "with_question" and has_question:
            # 模拟用户澄清
            user_clarification = self.simulate_user_clarification(case_id, extracted_question)
            
            # 创建第二轮对话
            second_prompt = f"""<|im_start|>system
你是一个聪明的AI助手。<|im_end|>
<|im_start|>user
{question}<|im_end|>
<|im_start|>assistant
<QUESTION>{extracted_question}</QUESTION><|im_end|>
<|im_start|>user
{user_clarification}<|im_end|>
<|im_start|>assistant
"""
            
            # 生成最终回答
            final_response = self.generate_response(second_prompt)
            result["final_answer"] = final_response
            result["user_clarification"] = user_clarification
            result["conversation_turns"] = 2
            
            # 简单判断成功（包含具体信息）
            result["success"] = len(final_response) > 10 and "不确定" not in final_response
        
        elif mode == "direct_answer":
            result["final_answer"] = response
            # 直接回答模式的成功判断（较宽松）
            result["success"] = len(response) > 5
        
        return result
    
    def run_comparison_experiment(self) -> Dict:
        """运行对比实验"""
        self.logger.info("开始运行对比实验...")
        
        results = {
            "with_question_results": [],
            "direct_answer_results": [],
            "summary": {}
        }
        
        # 测试主动提问模式
        self.logger.info("测试主动提问模式...")
        for test_case in self.test_cases:
            result = self.run_single_test(test_case, "with_question")
            results["with_question_results"].append(result)
            
            self.logger.info(f"案例 {test_case['id']}: {'提问' if result['has_question'] else '直答'}")
        
        # 测试直接回答模式
        self.logger.info("测试直接回答模式...")
        for test_case in self.test_cases:
            result = self.run_single_test(test_case, "direct_answer")
            results["direct_answer_results"].append(result)
        
        # 计算统计信息
        results["summary"] = self._calculate_summary(results)
        
        return results
    
    def _calculate_summary(self, results: Dict) -> Dict:
        """计算实验总结统计"""
        with_q = results["with_question_results"]
        direct = results["direct_answer_results"]
        
        summary = {
            "总测试案例数": len(self.test_cases),
            "主动提问模式": {
                "提问率": sum(1 for r in with_q if r["has_question"]) / len(with_q),
                "成功率": sum(1 for r in with_q if r["success"]) / len(with_q),
                "平均对话轮次": sum(r["conversation_turns"] for r in with_q) / len(with_q)
            },
            "直接回答模式": {
                "成功率": sum(1 for r in direct if r["success"]) / len(direct),
                "平均对话轮次": 1.0
            }
        }
        
        # 计算提升
        success_improvement = (summary["主动提问模式"]["成功率"] - 
                             summary["直接回答模式"]["成功率"])
        summary["成功率提升"] = success_improvement
        
        return summary
    
    def save_results(self, results: Dict, output_file: str = "stage1_results.json"):
        """保存实验结果"""
        output_path = Path(output_file)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"实验结果已保存到: {output_path}")
    
    def print_summary_report(self, results: Dict):
        """打印总结报告"""
        summary = results["summary"]
        
        print("\n" + "="*50)
        print("第一阶段实验结果总结")
        print("="*50)
        
        print(f"📊 测试案例数: {summary['总测试案例数']}")
        print()
        
        print("🤖 主动提问模式:")
        print(f"  ├─ 提问率: {summary['主动提问模式']['提问率']:.1%}")
        print(f"  ├─ 成功率: {summary['主动提问模式']['成功率']:.1%}")
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
            print("⚠️ 需要进一步优化提问机制")
        
        print("="*50)


def main():
    """主函数"""
    print("开始第一阶段核心概念验证实验")
    print("="*50)
    
    # 初始化测试器
    tester = Stage1Tester()
    
    # 加载模型
    print("🔄 正在加载Qwen3-4B-Thinking模型...")
    if not tester.load_model():
        print("❌ 模型加载失败，退出测试")
        return
    
    print("✅ 模型加载成功")
    
    # 运行对比实验
    print("\n🧪 开始运行MVP对比实验...")
    results = tester.run_comparison_experiment()
    
    # 保存结果
    tester.save_results(results)
    
    # 打印报告
    tester.print_summary_report(results)
    
    print("\n🎯 第一阶段实验完成！")
    print("📋 下一步: 根据结果分析并准备第二阶段开发")


if __name__ == "__main__":
    main()
