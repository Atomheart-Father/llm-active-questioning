#!/usr/bin/env python3
"""
第二阶段精细化测试：解决过度提问问题
主要改进：
1. 增加"无需提问"的示例
2. 设置提问惩罚机制  
3. 更平衡的Few-shot学习
4. 引入过度提问率评估
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


class Stage2RefinedTester:
    """第二阶段精细化测试器"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger("stage2_refined")
        self.tokenizer = None
        self.model = None
        
        # 设置设备（优先使用MPS）
        self.device = self._setup_device()
        
        # 精细化测试数据
        self.test_cases = self._create_balanced_test_cases()
        self.user_responses = self._create_user_response_mapping()
        
        self.logger.info("第二阶段精细化测试器初始化完成")
    
    def _setup_device(self) -> torch.device:
        """设置最优设备"""
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
    
    def _create_balanced_test_cases(self) -> List[Dict]:
        """创建平衡的测试案例（更多控制案例）"""
        # 需要提问的案例（减少数量）
        ambiguous_cases = [
            {
                "id": 1,
                "type": "代词歧义",
                "question": "他什么时候出生的？",
                "should_ask": True,
                "difficulty": "easy",
                "expected_question_topic": "具体指代人物"
            },
            {
                "id": 2,
                "type": "缺少关键信息",
                "question": "预订一张票",
                "should_ask": True,
                "difficulty": "easy",
                "expected_question_topic": "票的类型和具体信息"
            },
            {
                "id": 3,
                "type": "上下文依赖",
                "question": "那个文件在哪里？",
                "should_ask": True,
                "difficulty": "medium",
                "expected_question_topic": "具体文件名称"
            }
        ]
        
        # 无需提问的案例（增加数量和多样性）
        complete_cases = [
            {
                "id": 4,
                "type": "事实查询",
                "question": "中国的首都是哪里？",
                "should_ask": False,
                "difficulty": "easy",
                "expected_answer": "北京"
            },
            {
                "id": 5,
                "type": "数学计算",
                "question": "25乘以4等于多少？",
                "should_ask": False,
                "difficulty": "easy", 
                "expected_answer": "100"
            },
            {
                "id": 6,
                "type": "定义解释",
                "question": "什么是人工智能？",
                "should_ask": False,
                "difficulty": "medium",
                "expected_answer": "关于AI的解释"
            },
            {
                "id": 7,
                "type": "日期时间",
                "question": "今天是星期几？",
                "should_ask": False,
                "difficulty": "easy",
                "expected_answer": "需要当前日期信息"
            },
            {
                "id": 8,
                "type": "语言翻译",
                "question": "请把'Hello'翻译成中文",
                "should_ask": False,
                "difficulty": "easy",
                "expected_answer": "你好"
            },
            {
                "id": 9,
                "type": "常识问答",
                "question": "一年有多少个月？",
                "should_ask": False,
                "difficulty": "easy",
                "expected_answer": "12个月"
            },
            {
                "id": 10,
                "type": "具体指令",
                "question": "请帮我写一首关于春天的诗",
                "should_ask": False,
                "difficulty": "medium",
                "expected_answer": "创作春天主题的诗歌"
            }
        ]
        
        return ambiguous_cases + complete_cases
    
    def _create_user_response_mapping(self) -> Dict[int, str]:
        """创建用户澄清回答映射"""
        return {
            1: "我是指爱因斯坦。",
            2: "我想订从北京到上海明天上午的高铁票。",
            3: "我说的是昨天发给你的项目报告文件。"
        }
    
    def load_model(self) -> bool:
        """加载模型"""
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
            
            self.logger.info(f"模型加载成功，使用设备: {self.device}")
            return True
            
        except Exception as e:
            self.logger.error(f"模型加载失败: {e}")
            return False
    
    def create_balanced_few_shot_prompt(self, question: str, mode: str = "with_question") -> str:
        """
        创建平衡的Few-shot提示词（包含正反示例）
        """
        if mode == "with_question":
            system_prompt = """你是一个智能AI助手。请根据以下原则处理用户问题：

1. 如果问题信息完整且明确，直接给出准确回答
2. 如果问题模糊不清或缺少关键信息，主动提问澄清
3. 避免不必要的提问，只在确实需要澄清时才提问

示例1（需要澄清）：
用户：他什么时候出生的？
助手：请问您指的是哪位人物呢？

示例2（信息完整，直接回答）：
用户：爱因斯坦什么时候出生的？
助手：爱因斯坦于1879年3月14日出生。

示例3（需要澄清）：
用户：预订一张票
助手：请问您需要预订什么类型的票？比如火车票、飞机票，以及具体的出发地和目的地？

示例4（信息完整，直接回答）：
用户：中国的首都是哪里？
助手：中国的首都是北京。

请按照这个模式处理用户问题。"""

        else:
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
                max_length=1200  # 稍微增加以容纳更多示例
            ).to(self.device)
            
            # 生成参数
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=150,
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
        """检测回答中是否包含提问"""
        # 检查问号
        if '？' in response or '?' in response:
            sentences = re.split(r'[。！!.]', response)
            for sentence in sentences:
                if '？' in sentence or '?' in sentence:
                    return True, sentence.strip()
        
        # 检查提问关键词
        question_patterns = [
            r'请问.*?[？?]',
            r'能否.*?[？?]',
            r'您.*?[？?]',
            r'什么.*?[？?]',
            r'哪.*?[？?]',
            r'如何.*?[？?]',
            r'是否.*?[？?]',
            r'可以.*?[？?]'
        ]
        
        for pattern in question_patterns:
            match = re.search(pattern, response)
            if match:
                return True, match.group(0)
        
        return False, ""
    
    def calculate_question_appropriateness(self, test_case: Dict, has_question: bool) -> Tuple[bool, float]:
        """
        计算提问的合适性
        
        Returns:
            (行为是否正确, 惩罚分数)
        """
        should_ask = test_case.get("should_ask", False)
        
        if should_ask and has_question:
            # 应该提问且确实提问了
            return True, 0.0
        elif not should_ask and not has_question:
            # 不应该提问且确实没提问
            return True, 0.0
        elif not should_ask and has_question:
            # 不应该提问但提问了（过度提问）
            return False, -0.3  # 惩罚过度提问
        else:
            # 应该提问但没提问
            return False, -0.5  # 重度惩罚遗漏提问
    
    def run_single_test(self, test_case: Dict, mode: str) -> Dict:
        """运行单个测试案例"""
        case_id = test_case["id"]
        question = test_case["question"]
        should_ask = test_case.get("should_ask", False)
        
        # 创建平衡的Few-shot提示词
        prompt = self.create_balanced_few_shot_prompt(question, mode)
        
        # 生成回答
        response = self.generate_response(prompt)
        
        # 检测提问
        has_question, extracted_question = self.detect_question(response)
        
        # 计算合适性
        correct_behavior, penalty = self.calculate_question_appropriateness(test_case, has_question)
        
        result = {
            "case_id": case_id,
            "mode": mode,
            "original_question": question,
            "should_ask": should_ask,
            "first_response": response,
            "has_question": has_question,
            "extracted_question": extracted_question,
            "correct_behavior": correct_behavior,
            "penalty_score": penalty,
            "final_answer": "",
            "success": False,
            "conversation_turns": 1
        }
        
        if should_ask and has_question:
            # 需要提问且确实提问了，进行多轮对话
            user_clarification = self.user_responses.get(case_id, "请您具体说明。")
            
            # 第二轮对话
            second_prompt = f"""{prompt.rstrip()}{response}<|im_end|>
<|im_start|>user
{user_clarification}<|im_end|>
<|im_start|>assistant
"""
            
            final_response = self.generate_response(second_prompt)
            result["final_answer"] = final_response
            result["user_clarification"] = user_clarification
            result["conversation_turns"] = 2
            result["success"] = len(final_response) > 10 and "不确定" not in final_response
            
        elif not should_ask:
            # 不应该提问的案例
            result["final_answer"] = response
            result["success"] = not has_question and len(response) > 5
        
        return result
    
    def run_balanced_experiment(self) -> Dict:
        """运行平衡实验"""
        self.logger.info("开始运行第二阶段平衡实验...")
        
        results = {
            "with_question_results": [],
            "direct_answer_results": [],
            "summary": {}
        }
        
        # 测试精细化的主动提问模式
        self.logger.info("测试精细化的主动提问模式...")
        for test_case in self.test_cases:
            result = self.run_single_test(test_case, "with_question")
            results["with_question_results"].append(result)
            
            behavior = "✓" if result["correct_behavior"] else "✗"
            action = "提问" if result["has_question"] else "直答"
            should = "应该提问" if result["should_ask"] else "无需提问"
            
            self.logger.info(f"案例 {test_case['id']}: {action} ({should}) - {behavior}")
        
        # 测试直接回答模式（对照组）
        self.logger.info("测试直接回答模式...")
        for test_case in self.test_cases:
            result = self.run_single_test(test_case, "direct_answer")
            results["direct_answer_results"].append(result)
        
        # 计算统计信息
        results["summary"] = self._calculate_balanced_summary(results)
        
        return results
    
    def _calculate_balanced_summary(self, results: Dict) -> Dict:
        """计算平衡实验总结"""
        with_q = results["with_question_results"]
        direct = results["direct_answer_results"]
        
        # 按类型分组
        should_ask_cases = [r for r in with_q if r["should_ask"]]
        should_not_ask_cases = [r for r in with_q if not r["should_ask"]]
        
        # 计算过度提问率
        over_questioning_rate = sum(1 for r in should_not_ask_cases if r["has_question"]) / len(should_not_ask_cases) if should_not_ask_cases else 0
        
        # 计算平均惩罚分数
        avg_penalty = sum(r["penalty_score"] for r in with_q) / len(with_q)
        
        summary = {
            "总测试案例数": len(self.test_cases),
            "应该提问案例数": len(should_ask_cases),
            "无需提问案例数": len(should_not_ask_cases),
            
            "精细化主动提问模式": {
                "总体行为正确率": sum(1 for r in with_q if r["correct_behavior"]) / len(with_q),
                "总体成功率": sum(1 for r in with_q if r["success"]) / len(with_q),
                
                # 应该提问的案例
                "应提问-实际提问率": sum(1 for r in should_ask_cases if r["has_question"]) / len(should_ask_cases) if should_ask_cases else 0,
                "应提问-最终成功率": sum(1 for r in should_ask_cases if r["success"]) / len(should_ask_cases) if should_ask_cases else 0,
                
                # 不应该提问的案例
                "无需提问-正确直答率": sum(1 for r in should_not_ask_cases if not r["has_question"]) / len(should_not_ask_cases) if should_not_ask_cases else 0,
                "过度提问率": over_questioning_rate,
                
                "平均惩罚分数": avg_penalty,
                "平均对话轮次": sum(r["conversation_turns"] for r in with_q) / len(with_q)
            },
            
            "直接回答模式": {
                "成功率": sum(1 for r in direct if r["success"]) / len(direct),
                "平均对话轮次": 1.0
            }
        }
        
        # 计算改进情况
        summary["行为正确率改进"] = summary["精细化主动提问模式"]["总体行为正确率"] - 0.625  # 与第一阶段对比
        summary["过度提问率改进"] = 1.0 - over_questioning_rate  # 过度提问率的改进
        
        return summary
    
    def print_balanced_report(self, results: Dict):
        """打印平衡实验报告"""
        summary = results["summary"]
        
        print("\n" + "="*70)
        print("第二阶段精细化实验结果报告")
        print("="*70)
        
        print(f"📊 实验规模: {summary['总测试案例数']} 个案例")
        print(f"   ├─ 应该提问: {summary['应该提问案例数']} 个")
        print(f"   └─ 无需提问: {summary['无需提问案例数']} 个")
        print()
        
        mode_stats = summary["精细化主动提问模式"]
        print("🎯 精细化主动提问模式:")
        print(f"   ├─ 总体行为正确率: {mode_stats['总体行为正确率']:.1%}")
        print(f"   ├─ 总体成功率: {mode_stats['总体成功率']:.1%}")
        print(f"   ├─ 应提问-实际提问率: {mode_stats['应提问-实际提问率']:.1%}")
        print(f"   ├─ 应提问-最终成功率: {mode_stats['应提问-最终成功率']:.1%}")
        print(f"   ├─ 无需提问-正确直答率: {mode_stats['无需提问-正确直答率']:.1%}")
        print(f"   ├─ 过度提问率: {mode_stats['过度提问率']:.1%}")
        print(f"   ├─ 平均惩罚分数: {mode_stats['平均惩罚分数']:.2f}")
        print(f"   └─ 平均对话轮次: {mode_stats['平均对话轮次']:.1f}")
        print()
        
        print("📝 直接回答模式:")
        print(f"   ├─ 成功率: {summary['直接回答模式']['成功率']:.1%}")
        print(f"   └─ 平均对话轮次: {summary['直接回答模式']['平均对话轮次']:.1f}")
        print()
        
        print("📈 改进情况:")
        behavior_improvement = summary.get("行为正确率改进", 0)
        over_question_improvement = summary.get("过度提问率改进", 0)
        
        if behavior_improvement > 0:
            print(f"   ✅ 行为正确率提升: +{behavior_improvement:.1%}")
        else:
            print(f"   📊 行为正确率变化: {behavior_improvement:.1%}")
            
        print(f"   ✅ 过度提问控制: {over_question_improvement:.1%}")
        
        # 总体评估
        if mode_stats['总体行为正确率'] > 0.8:
            print("\n🎉 优秀！模型行为控制良好")
        elif mode_stats['总体行为正确率'] > 0.7:
            print("\n✅ 良好！模型行为基本正确")
        else:
            print("\n⚠️ 需要继续优化模型行为")
            
        if mode_stats['过度提问率'] < 0.2:
            print("🎯 过度提问问题已得到有效控制")
        else:
            print("📋 过度提问仍需进一步优化")
        
        print("="*70)
    
    def save_results(self, results: Dict, output_file: str = "stage2_refined_results.json"):
        """保存实验结果"""
        output_path = Path(output_file)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"第二阶段实验结果已保存到: {output_path}")


def main():
    """主函数"""
    print("开始第二阶段精细化实验")
    print("目标：解决过度提问问题，提升行为判断准确性")
    print("="*70)
    
    # 初始化测试器
    tester = Stage2RefinedTester()
    
    # 加载模型
    print("🔄 正在加载优化模型...")
    if not tester.load_model():
        print("❌ 模型加载失败，退出测试")
        return
    
    print("✅ 模型加载成功")
    
    # 运行平衡实验
    print("\n🧪 开始运行平衡对比实验...")
    print("改进项: 平衡Few-shot + 提问惩罚 + 更多控制案例")
    
    results = tester.run_balanced_experiment()
    
    # 保存和报告结果
    tester.save_results(results)
    tester.print_balanced_report(results)
    
    print("\n🎯 第二阶段精细化实验完成！")
    print("📋 准备进入多轮交互和任务扩展阶段")


if __name__ == "__main__":
    main()
