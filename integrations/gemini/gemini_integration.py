#!/usr/bin/env python3
"""
Gemini API集成模块
用于数据转换和多轮对话构造
"""

import requests
import json
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_config
from src.utils.logging import get_logger


class GeminiDataGenerator:
    """Gemini数据生成器"""
    
    def __init__(self, api_key: str = None):
        """
        初始化Gemini数据生成器
        
        Args:
            api_key: Gemini API密钥
        """
        self.config = get_config()
        self.logger = get_logger("gemini_generator")
        
        # 设置API密钥
        self.api_key = api_key or "AIzaSyBLECdu94qJWPFOZ--9dIKpeWaWjSGJ_z0"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        
        self.logger.info("Gemini数据生成器初始化完成")
    
    def test_api_connection(self) -> bool:
        """测试API连接"""
        try:
            response = self._make_request("测试连接：请简单回答'连接成功'")
            if response and "连接成功" in response:
                self.logger.info("✅ Gemini API连接测试成功")
                return True
            else:
                self.logger.warning(f"⚠️ API响应异常: {response}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ API连接测试失败: {e}")
            return False
    
    def _make_request(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """
        发送Gemini API请求
        
        Args:
            prompt: 提示文本
            max_retries: 最大重试次数
            
        Returns:
            生成的文本或None
        """
        headers = {
            'Content-Type': 'application/json',
            'X-goog-api-key': self.api_key
        }
        
        data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=data,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # 解析Gemini响应格式
                    if 'candidates' in result and len(result['candidates']) > 0:
                        candidate = result['candidates'][0]
                        if 'content' in candidate and 'parts' in candidate['content']:
                            parts = candidate['content']['parts']
                            if len(parts) > 0 and 'text' in parts[0]:
                                return parts[0]['text'].strip()
                    
                    self.logger.warning(f"意外的API响应格式: {result}")
                    return None
                    
                else:
                    self.logger.warning(f"API请求失败 (状态码: {response.status_code}): {response.text}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # 指数退避
                    
            except Exception as e:
                self.logger.error(f"请求异常 (尝试 {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        
        return None
    
    def generate_clarifying_dialogue(self, original_question: str, expected_answer: str = None) -> Dict[str, Any]:
        """
        生成澄清对话
        
        Args:
            original_question: 原始问题
            expected_answer: 期望答案（可选）
            
        Returns:
            生成的对话结构
        """
        prompt = f"""
请基于以下原始问题生成一个多轮澄清对话。

原始问题: "{original_question}"

要求：
1. 判断这个问题是否模糊或缺少信息
2. 如果模糊，生成一个澄清问题
3. 提供合理的用户澄清回答
4. 给出最终的准确答案

请按以下JSON格式输出：
{{
    "is_ambiguous": true/false,
    "clarifying_question": "澄清问题（如果需要）",
    "user_clarification": "用户的澄清回答",
    "final_answer": "最终答案",
    "reasoning": "判断理由"
}}

示例：
原始问题: "他什么时候出生的？"
输出: {{"is_ambiguous": true, "clarifying_question": "请问您指的是哪位人物？", "user_clarification": "我指的是爱因斯坦", "final_answer": "爱因斯坦于1879年3月14日出生", "reasoning": "问题中的'他'指代不明确"}}
"""
        
        response = self._make_request(prompt)
        
        if response:
            try:
                # 尝试解析JSON
                dialogue_data = json.loads(response)
                return dialogue_data
            except json.JSONDecodeError:
                # 如果JSON解析失败，尝试提取内容
                self.logger.warning("JSON解析失败，使用文本解析")
                return {
                    "is_ambiguous": "?" in original_question or "他" in original_question or "她" in original_question,
                    "clarifying_question": "请您提供更多具体信息。",
                    "user_clarification": "用户提供更多信息",
                    "final_answer": response,
                    "reasoning": "API返回格式异常"
                }
        
        return None
    
    def generate_multi_hop_dialogue(self, question: str, context: str = None) -> Dict[str, Any]:
        """
        生成多跳推理对话
        
        Args:
            question: 复杂问题
            context: 背景信息
            
        Returns:
            多跳推理对话结构
        """
        prompt = f"""
请为以下复杂问题设计一个多轮推理对话，模拟AI助手通过逐步提问来收集信息并推理的过程。

问题: "{question}"
{f"背景信息: {context}" if context else ""}

要求：
1. 将复杂问题分解为2-3个子问题
2. 设计AI助手的逐步提问
3. 提供用户的合理回答
4. 展示最终的推理和答案

请按以下格式输出：
{{
    "original_question": "原始问题",
    "reasoning_steps": [
        {{
            "step": 1,
            "ai_question": "AI的问题",
            "user_answer": "用户回答",
            "reasoning": "这一步的推理"
        }}
    ],
    "final_answer": "最终答案",
    "confidence": "high/medium/low"
}}
"""
        
        response = self._make_request(prompt)
        
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {
                    "original_question": question,
                    "reasoning_steps": [
                        {
                            "step": 1,
                            "ai_question": "让我帮您分析这个问题，请问您需要什么具体信息？",
                            "user_answer": "用户提供相关信息",
                            "reasoning": "需要收集更多信息进行推理"
                        }
                    ],
                    "final_answer": response,
                    "confidence": "medium"
                }
        
        return None
    
    def batch_generate_dialogues(self, questions: List[str], dialogue_type: str = "clarifying") -> List[Dict[str, Any]]:
        """
        批量生成对话数据
        
        Args:
            questions: 问题列表
            dialogue_type: 对话类型 ("clarifying" 或 "multi_hop")
            
        Returns:
            生成的对话列表
        """
        self.logger.info(f"开始批量生成{len(questions)}个{dialogue_type}对话...")
        
        results = []
        for i, question in enumerate(questions):
            try:
                if dialogue_type == "clarifying":
                    dialogue = self.generate_clarifying_dialogue(question)
                elif dialogue_type == "multi_hop":
                    dialogue = self.generate_multi_hop_dialogue(question)
                else:
                    self.logger.warning(f"未知的对话类型: {dialogue_type}")
                    continue
                
                if dialogue:
                    dialogue["source_question"] = question
                    dialogue["generation_type"] = dialogue_type
                    results.append(dialogue)
                    
                    self.logger.info(f"生成完成 {i+1}/{len(questions)}: {question[:30]}...")
                else:
                    self.logger.warning(f"生成失败: {question}")
                
                # 避免API限流
                if i % 5 == 4:
                    time.sleep(2)
                    
            except Exception as e:
                self.logger.error(f"生成对话失败 ({question}): {e}")
                continue
        
        self.logger.info(f"批量生成完成，成功生成{len(results)}个对话")
        return results
    
    def convert_qa_to_dialogue(self, qa_dataset: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        将QA数据集转换为多轮对话格式
        
        Args:
            qa_dataset: QA数据集 [{"question": "...", "answer": "..."}]
            
        Returns:
            转换后的对话数据集
        """
        self.logger.info(f"开始转换{len(qa_dataset)}个QA对为对话格式...")
        
        questions = [item["question"] for item in qa_dataset]
        
        # 生成澄清对话
        clarifying_dialogues = self.batch_generate_dialogues(questions, "clarifying")
        
        # 合并原始答案信息
        for i, dialogue in enumerate(clarifying_dialogues):
            if i < len(qa_dataset):
                dialogue["original_answer"] = qa_dataset[i].get("answer", "")
                dialogue["dataset_info"] = qa_dataset[i]
        
        return clarifying_dialogues
    
    def save_generated_data(self, dialogues: List[Dict[str, Any]], output_file: str):
        """保存生成的对话数据"""
        output_path = Path(output_file)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dialogues, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"已保存{len(dialogues)}个对话到: {output_path}")


def test_gemini_integration():
    """测试Gemini集成功能"""
    print("开始测试Gemini API集成...")
    print("="*50)
    
    # 初始化生成器
    generator = GeminiDataGenerator()
    
    # 测试API连接
    print("🔄 测试API连接...")
    if not generator.test_api_connection():
        print("❌ API连接失败，请检查密钥和网络")
        return
    
    # 测试澄清对话生成
    print("\n🧪 测试澄清对话生成...")
    test_questions = [
        "他什么时候出生的？",
        "那家餐厅好吃吗？",
        "预订一张票",
        "北京的天气怎么样？"  # 控制案例：不模糊
    ]
    
    clarifying_results = generator.batch_generate_dialogues(test_questions, "clarifying")
    
    print(f"\n✅ 成功生成{len(clarifying_results)}个澄清对话")
    
    # 显示示例
    if clarifying_results:
        print("\n📝 示例对话:")
        example = clarifying_results[0]
        print(f"原问题: {example.get('source_question', '')}")
        print(f"是否模糊: {example.get('is_ambiguous', False)}")
        if example.get('is_ambiguous'):
            print(f"澄清问题: {example.get('clarifying_question', '')}")
            print(f"用户回答: {example.get('user_clarification', '')}")
        print(f"最终答案: {example.get('final_answer', '')}")
    
    # 测试多跳推理对话生成
    print("\n🔍 测试多跳推理对话生成...")
    complex_questions = [
        "谁是写《哈利波特》的作者的丈夫？",
        "世界上最高山峰所在国家的首都是什么？"
    ]
    
    multi_hop_results = generator.batch_generate_dialogues(complex_questions, "multi_hop")
    
    print(f"\n✅ 成功生成{len(multi_hop_results)}个多跳对话")
    
    # 保存测试结果
    all_results = {
        "clarifying_dialogues": clarifying_results,
        "multi_hop_dialogues": multi_hop_results,
        "test_timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    generator.save_generated_data([all_results], "gemini_test_results.json")
    
    print("\n🎯 Gemini集成测试完成！")
    print("📋 可以开始大规模数据转换工作")


if __name__ == "__main__":
    test_gemini_integration()
