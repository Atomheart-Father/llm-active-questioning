#!/usr/bin/env python3
"""
Qwen3-4B-Thinking 推理测试脚本
测试 llama.cpp + GGUF 的推理性能和质量
"""

import os
import sys
import subprocess
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QwenLlamaCppTester:
    """Qwen + llama.cpp 测试器"""
    
    def __init__(self):
        self.home_dir = Path.home()
        self.llama_cpp_dir = self.home_dir / "llama_cpp_workspace" / "llama.cpp"
        self.models_dir = self.home_dir / "llama_cpp_workspace" / "models"
        self.main_binary = self.llama_cpp_dir / "main"
        
        self.test_prompts = [
            {
                "id": "math_basic",
                "prompt": "请计算：25 × 4 = ?",
                "expected_type": "math",
                "description": "基础数学计算"
            },
            {
                "id": "reasoning_simple", 
                "prompt": "如果一个正方形的周长是20厘米，它的面积是多少？请详细说明计算步骤。",
                "expected_type": "math_reasoning",
                "description": "几何推理"
            },
            {
                "id": "question_ambiguous",
                "prompt": "他什么时候来的？",
                "expected_type": "clarification",
                "description": "歧义澄清测试"
            },
            {
                "id": "multi_hop",
                "prompt": "世界上最高的山峰在哪个国家？这个国家的首都是什么？",
                "expected_type": "multi_hop",
                "description": "多跳推理"
            },
            {
                "id": "thinking_chain",
                "prompt": "一个班级有30个学生，其中60%是女生。如果女生中有1/3戴眼镜，男生中有1/2戴眼镜，那么全班戴眼镜的学生有多少人？请用<think>标签显示你的思考过程。",
                "expected_type": "thinking",
                "description": "思考链测试"
            }
        ]
    
    def check_environment(self) -> bool:
        """检查环境是否就绪"""
        logger.info("🔍 检查测试环境...")
        
        # 检查 llama.cpp 可执行文件
        if not self.main_binary.exists():
            logger.error(f"❌ llama.cpp 主程序未找到: {self.main_binary}")
            logger.info("请先运行: ./scripts/setup_llama_cpp.sh")
            return False
        
        logger.info(f"✅ llama.cpp 主程序: {self.main_binary}")
        
        # 检查模型文件
        model_files = list(self.models_dir.glob("*.gguf"))
        if not model_files:
            logger.error(f"❌ 未找到 GGUF 模型文件: {self.models_dir}")
            logger.info("请先运行: python scripts/download_qwen_model.py")
            return False
        
        self.model_path = model_files[0]  # 使用第一个找到的模型
        logger.info(f"✅ 使用模型: {self.model_path}")
        
        return True
    
    def run_inference(self, prompt: str, max_tokens: int = 200, temperature: float = 0.7) -> Optional[str]:
        """运行单次推理"""
        try:
            cmd = [
                str(self.main_binary),
                "-m", str(self.model_path),
                "-p", prompt,
                "-n", str(max_tokens),
                "--temp", str(temperature),
                "-c", "2048",  # 上下文长度
                "--mlock",     # 锁定内存
                "-ngl", "999", # GPU 层数（对 Metal 有效）
            ]
            
            logger.info(f"🚀 执行推理: {prompt[:50]}...")
            start_time = time.time()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2分钟超时
            )
            
            end_time = time.time()
            inference_time = end_time - start_time
            
            if result.returncode == 0:
                # 解析输出，提取模型响应
                output = result.stdout
                
                # llama.cpp 的输出格式通常是：提示词 + 模型响应
                # 需要分离出模型的响应部分
                response = self._extract_model_response(output, prompt)
                
                logger.info(f"✅ 推理完成 ({inference_time:.2f}秒)")
                return response
            else:
                logger.error(f"❌ 推理失败: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("❌ 推理超时")
            return None
        except Exception as e:
            logger.error(f"❌ 推理异常: {e}")
            return None
    
    def _extract_model_response(self, full_output: str, prompt: str) -> str:
        """从完整输出中提取模型响应"""
        # 简单的响应提取逻辑
        lines = full_output.split('\n')
        
        # 查找包含模型响应的行
        response_lines = []
        capturing = False
        
        for line in lines:
            # 跳过系统输出和提示词
            if any(skip in line.lower() for skip in ['llama', 'main:', 'log', 'perplexity']):
                continue
            
            # 如果找到提示词，开始捕获后续内容
            if prompt.strip() in line:
                capturing = True
                # 提取提示词之后的部分
                prompt_index = line.find(prompt.strip())
                if prompt_index >= 0:
                    after_prompt = line[prompt_index + len(prompt.strip()):].strip()
                    if after_prompt:
                        response_lines.append(after_prompt)
                continue
            
            if capturing and line.strip():
                response_lines.append(line.strip())
        
        response = '\n'.join(response_lines).strip()
        
        # 如果提取失败，返回原始输出的清理版本
        if not response:
            # 移除明显的系统输出
            cleaned_lines = []
            for line in lines:
                if line.strip() and not any(skip in line.lower() for skip in ['llama', 'main:', 'log']):
                    cleaned_lines.append(line.strip())
            response = '\n'.join(cleaned_lines[-10:])  # 取最后10行
        
        return response
    
    def evaluate_response(self, prompt_data: Dict[str, Any], response: str) -> Dict[str, Any]:
        """评估响应质量"""
        evaluation = {
            "prompt_id": prompt_data["id"],
            "prompt": prompt_data["prompt"],
            "response": response,
            "response_length": len(response),
            "has_thinking": "<think>" in response.lower() or "思考" in response,
            "has_question": "?" in response or "？" in response,
            "expected_type": prompt_data["expected_type"],
            "quality_score": 0,
            "issues": []
        }
        
        # 基础质量检查
        if not response or len(response) < 10:
            evaluation["issues"].append("响应过短或为空")
            evaluation["quality_score"] = 0
        else:
            evaluation["quality_score"] = 50  # 基础分
            
            # 根据期望类型进行评估
            expected_type = prompt_data["expected_type"]
            
            if expected_type == "math" or expected_type == "math_reasoning":
                if any(char in response for char in ['=', '×', '÷', '+', '-']):
                    evaluation["quality_score"] += 20
                if "步骤" in response or "计算" in response:
                    evaluation["quality_score"] += 15
            
            elif expected_type == "clarification":
                if "?" in response or "？" in response:
                    evaluation["quality_score"] += 25
                if any(word in response for word in ["请问", "哪", "什么", "澄清"]):
                    evaluation["quality_score"] += 15
            
            elif expected_type == "multi_hop":
                if len(response) > 100:  # 多跳推理通常需要更长的响应
                    evaluation["quality_score"] += 20
                if any(word in response for word in ["首先", "然后", "最后", "第一", "第二"]):
                    evaluation["quality_score"] += 15
            
            elif expected_type == "thinking":
                if evaluation["has_thinking"]:
                    evaluation["quality_score"] += 30
                else:
                    evaluation["issues"].append("缺少思考过程标签")
        
        # 最终质量等级
        if evaluation["quality_score"] >= 80:
            evaluation["quality_grade"] = "A"
        elif evaluation["quality_score"] >= 60:
            evaluation["quality_grade"] = "B"
        else:
            evaluation["quality_grade"] = "C"
        
        return evaluation
    
    def run_performance_test(self) -> Dict[str, Any]:
        """运行性能测试"""
        logger.info("⚡ 开始性能测试...")
        
        performance_results = {
            "test_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model_path": str(self.model_path),
            "test_results": [],
            "summary": {}
        }
        
        total_time = 0
        successful_tests = 0
        
        for prompt_data in self.test_prompts:
            logger.info(f"🧪 测试: {prompt_data['description']}")
            
            start_time = time.time()
            response = self.run_inference(prompt_data["prompt"])
            end_time = time.time()
            
            inference_time = end_time - start_time
            total_time += inference_time
            
            if response:
                successful_tests += 1
                evaluation = self.evaluate_response(prompt_data, response)
                evaluation["inference_time"] = inference_time
                performance_results["test_results"].append(evaluation)
                
                logger.info(f"📊 质量: {evaluation['quality_grade']} ({evaluation['quality_score']}/100)")
                logger.info(f"⏱️ 时间: {inference_time:.2f}秒")
                logger.info(f"📝 响应: {response[:100]}...")
            else:
                logger.error(f"❌ 测试失败: {prompt_data['id']}")
                performance_results["test_results"].append({
                    "prompt_id": prompt_data["id"],
                    "status": "failed",
                    "inference_time": inference_time
                })
            
            logger.info("-" * 50)
        
        # 计算总结统计
        performance_results["summary"] = {
            "total_tests": len(self.test_prompts),
            "successful_tests": successful_tests,
            "success_rate": successful_tests / len(self.test_prompts),
            "total_time": total_time,
            "avg_time_per_test": total_time / len(self.test_prompts),
            "quality_distribution": self._calculate_quality_distribution(performance_results["test_results"])
        }
        
        return performance_results
    
    def _calculate_quality_distribution(self, test_results: List[Dict[str, Any]]) -> Dict[str, int]:
        """计算质量分布"""
        distribution = {"A": 0, "B": 0, "C": 0, "failed": 0}
        
        for result in test_results:
            if "quality_grade" in result:
                distribution[result["quality_grade"]] += 1
            else:
                distribution["failed"] += 1
        
        return distribution
    
    def save_results(self, results: Dict[str, Any]) -> str:
        """保存测试结果"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        results_file = f"qwen_llama_cpp_test_results_{timestamp}.json"
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 测试结果已保存: {results_file}")
        return results_file
    
    def print_summary(self, results: Dict[str, Any]):
        """打印测试总结"""
        summary = results["summary"]
        
        print("\n" + "=" * 60)
        print("🎯 Qwen3-4B-Thinking + llama.cpp 性能测试总结")
        print("=" * 60)
        print(f"📊 总测试数: {summary['total_tests']}")
        print(f"✅ 成功数: {summary['successful_tests']}")
        print(f"📈 成功率: {summary['success_rate']:.1%}")
        print(f"⏱️ 总时间: {summary['total_time']:.2f}秒")
        print(f"⚡ 平均时间: {summary['avg_time_per_test']:.2f}秒/测试")
        
        print(f"\n🏆 质量分布:")
        quality_dist = summary['quality_distribution']
        for grade, count in quality_dist.items():
            if count > 0:
                print(f"   {grade}级: {count} 个")
        
        print("\n📝 详细结果:")
        for result in results["test_results"]:
            if "quality_grade" in result:
                print(f"   {result['prompt_id']}: {result['quality_grade']}级 ({result['inference_time']:.2f}s)")
            else:
                print(f"   {result['prompt_id']}: 失败")
        
        print("=" * 60)

def main():
    """主函数"""
    logger.info("🚀 Qwen3-4B-Thinking + llama.cpp 推理测试")
    logger.info("=" * 60)
    
    tester = QwenLlamaCppTester()
    
    # 检查环境
    if not tester.check_environment():
        logger.error("❌ 环境检查失败，请先完成环境搭建")
        sys.exit(1)
    
    # 运行性能测试
    results = tester.run_performance_test()
    
    # 保存和展示结果
    results_file = tester.save_results(results)
    tester.print_summary(results)
    
    logger.info(f"🎉 测试完成！详细结果已保存到: {results_file}")

if __name__ == "__main__":
    main()
