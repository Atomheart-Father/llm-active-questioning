"""
GPT-4用户模拟模块
使用GPT-4模拟不同风格的用户对话和提问
"""

import asyncio
import json
import time
from typing import List, Dict, Any, Optional
import openai
from openai import AsyncOpenAI
import random

from ..utils.config import get_config
from ..utils.logging import get_logger


class GPT4UserSimulator:
    """GPT-4用户模拟器"""
    
    def __init__(self, api_key: str = None):
        """
        初始化GPT-4模拟器
        
        Args:
            api_key: OpenAI API密钥
        """
        self.config = get_config()
        self.logger = get_logger()
        
        # 设置API密钥
        if api_key is None:
            api_key = self.config.get("simulation.openai_api_key")
        
        if not api_key:
            raise ValueError("未提供OpenAI API密钥，请在配置文件中设置或传入参数")
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.sync_client = openai.OpenAI(api_key=api_key)
        
        # 配置参数
        self.model = self.config.get("simulation.model", "gpt-4")
        self.temperature = self.config.get("simulation.temperature", 0.7)
        self.max_tokens = self.config.get("simulation.max_tokens", 1024)
        
        # 风格分布
        self.style_distribution = self.config.get("simulation.style_distribution", {
            "simple_realistic": 0.8,
            "complex_professional": 0.1,
            "role_playing": 0.05,
            "format_specific": 0.05
        })
        
        self.logger.info("GPT-4用户模拟器初始化完成")
    
    def _get_style_prompt(self, style: str) -> str:
        """
        获取不同风格的提示词
        
        Args:
            style: 风格类型
            
        Returns:
            提示词
        """
        prompts = {
            "simple_realistic": """
你是一个普通用户，正在向AI助手提问。请生成一个简洁、直接的问题，就像日常对话中会问的那样。
问题应该：
- 语言自然、简洁
- 不要过于复杂或专业
- 像真实用户会问的问题
- 可以是各种领域的常见问题

请直接输出问题，不要加其他说明。
            """,
            
            "complex_professional": """
你是一个专业领域的用户，需要向AI助手咨询复杂问题。请生成一个详细、专业的问题。
问题应该：
- 包含背景信息和具体要求
- 涉及多个步骤或层面
- 使用专业词汇和概念
- 要求详细的分析或解释

请直接输出问题，不要加其他说明。
            """,
            
            "role_playing": """
你在特定场景中扮演某个角色，向AI助手提问。请生成一个角色扮演式的问题。
可能的角色场景：
- 学生向老师请教
- 顾客向客服咨询
- 患者向医生询问
- 员工向专家求助

请选择一个角色场景，直接输出相应的问题，不要加其他说明。
            """,
            
            "format_specific": """
你需要AI助手以特定格式回答问题。请生成一个明确要求特定输出格式的问题。
格式要求可以是：
- 列表或表格形式
- 逐步说明
- 分类整理
- JSON格式
- 带标题的分段回答

请直接输出问题（包含格式要求），不要加其他说明。
            """
        }
        
        return prompts.get(style, prompts["simple_realistic"])
    
    def _select_style(self) -> str:
        """
        根据配置的分布随机选择风格
        
        Returns:
            选中的风格
        """
        styles = list(self.style_distribution.keys())
        weights = list(self.style_distribution.values())
        return random.choices(styles, weights=weights)[0]
    
    async def generate_user_question_async(self, style: str = None, topic: str = None) -> str:
        """
        异步生成用户问题
        
        Args:
            style: 问题风格，None时随机选择
            topic: 问题主题，None时不限制
            
        Returns:
            生成的用户问题
        """
        if style is None:
            style = self._select_style()
        
        # 构建提示词
        system_prompt = self._get_style_prompt(style)
        
        user_prompt = "请生成一个问题。"
        if topic:
            user_prompt += f"问题应该与以下主题相关：{topic}"
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            question = response.choices[0].message.content.strip()
            self.logger.debug(f"生成{style}风格问题: {question[:50]}...")
            
            return question
            
        except Exception as e:
            self.logger.error(f"生成用户问题失败: {e}")
            # 返回默认问题
            return "请帮我解决一个问题。"
    
    def generate_user_question(self, style: str = None, topic: str = None) -> str:
        """
        同步生成用户问题
        
        Args:
            style: 问题风格，None时随机选择
            topic: 问题主题，None时不限制
            
        Returns:
            生成的用户问题
        """
        if style is None:
            style = self._select_style()
        
        # 构建提示词
        system_prompt = self._get_style_prompt(style)
        
        user_prompt = "请生成一个问题。"
        if topic:
            user_prompt += f"问题应该与以下主题相关：{topic}"
        
        try:
            response = self.sync_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            question = response.choices[0].message.content.strip()
            self.logger.debug(f"生成{style}风格问题: {question[:50]}...")
            
            return question
            
        except Exception as e:
            self.logger.error(f"生成用户问题失败: {e}")
            # 返回默认问题
            return "请帮我解决一个问题。"
    
    async def generate_batch_questions_async(self, count: int, styles: List[str] = None, topics: List[str] = None) -> List[Dict[str, str]]:
        """
        异步批量生成用户问题
        
        Args:
            count: 生成数量
            styles: 指定风格列表，None时随机选择
            topics: 主题列表，None时不限制
            
        Returns:
            问题列表，每个元素包含question、style、topic字段
        """
        self.logger.info(f"开始批量生成{count}个用户问题...")
        
        # 准备任务
        tasks = []
        for i in range(count):
            style = styles[i % len(styles)] if styles else None
            topic = topics[i % len(topics)] if topics else None
            tasks.append(self.generate_user_question_async(style, topic))
        
        # 执行任务（控制并发数）
        semaphore = asyncio.Semaphore(10)  # 最多10个并发请求
        
        async def limited_generate(task):
            async with semaphore:
                return await task
        
        results = await asyncio.gather(*[limited_generate(task) for task in tasks])
        
        # 构建返回结果
        questions = []
        for i, question in enumerate(results):
            style = styles[i % len(styles)] if styles else self._select_style()
            topic = topics[i % len(topics)] if topics else None
            
            questions.append({
                'question': question,
                'style': style,
                'topic': topic
            })
        
        self.logger.info(f"批量生成完成，共{len(questions)}个问题")
        return questions
    
    def generate_batch_questions(self, count: int, styles: List[str] = None, topics: List[str] = None) -> List[Dict[str, str]]:
        """
        同步批量生成用户问题
        
        Args:
            count: 生成数量
            styles: 指定风格列表，None时随机选择
            topics: 主题列表，None时不限制
            
        Returns:
            问题列表，每个元素包含question、style、topic字段
        """
        self.logger.info(f"开始批量生成{count}个用户问题...")
        
        questions = []
        for i in range(count):
            try:
                style = styles[i % len(styles)] if styles else None
                topic = topics[i % len(topics)] if topics else None
                
                question = self.generate_user_question(style, topic)
                
                questions.append({
                    'question': question,
                    'style': style or self._select_style(),
                    'topic': topic
                })
                
                # 避免API限流
                if i % 10 == 9:
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"生成第{i+1}个问题失败: {e}")
                continue
        
        self.logger.info(f"批量生成完成，共{len(questions)}个问题")
        return questions
    
    async def evaluate_response_async(self, question: str, response: str) -> Dict[str, Any]:
        """
        异步评估模型回答质量
        
        Args:
            question: 用户问题
            response: 模型回答
            
        Returns:
            评估结果
        """
        system_prompt = """
你是一个专业的AI回答评估专家。请对AI助手的回答进行评估。

评估标准：
1. 准确性 (1-10分): 回答是否正确、准确
2. 有用性 (1-10分): 回答是否真正解决了用户问题
3. 清晰性 (1-10分): 回答是否清楚易懂
4. 完整性 (1-10分): 回答是否完整，没有遗漏重要信息
5. 安全性 (1-10分): 回答是否安全，没有有害内容

请以JSON格式返回评估结果：
{
    "accuracy": 分数,
    "usefulness": 分数,
    "clarity": 分数,
    "completeness": 分数,
    "safety": 分数,
    "overall_score": 总分(1-10),
    "comments": "简要评价"
}
        """
        
        user_prompt = f"""
用户问题：{question}

AI回答：{response}

请对这个回答进行评估。
        """
        
        try:
            response_obj = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # 使用较低温度确保评估一致性
                max_tokens=500
            )
            
            evaluation_text = response_obj.choices[0].message.content.strip()
            
            # 尝试解析JSON
            try:
                evaluation = json.loads(evaluation_text)
            except json.JSONDecodeError:
                # 如果解析失败，提取数字分数
                self.logger.warning("GPT-4返回的评估不是标准JSON格式，尝试解析")
                evaluation = {
                    "accuracy": 7.0,
                    "usefulness": 7.0,
                    "clarity": 7.0,
                    "completeness": 7.0,
                    "safety": 9.0,
                    "overall_score": 7.0,
                    "comments": evaluation_text
                }
            
            return evaluation
            
        except Exception as e:
            self.logger.error(f"评估回答失败: {e}")
            return {
                "accuracy": 5.0,
                "usefulness": 5.0,
                "clarity": 5.0,
                "completeness": 5.0,
                "safety": 8.0,
                "overall_score": 5.0,
                "comments": "评估失败"
            }
    
    def evaluate_response(self, question: str, response: str) -> Dict[str, Any]:
        """
        同步评估模型回答质量
        
        Args:
            question: 用户问题
            response: 模型回答
            
        Returns:
            评估结果
        """
        return asyncio.run(self.evaluate_response_async(question, response))
    
    def save_generated_data(self, questions: List[Dict[str, str]], output_file: str):
        """
        保存生成的问题数据
        
        Args:
            questions: 问题列表
            output_file: 输出文件路径
        """
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(questions, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"已保存{len(questions)}个问题到{output_file}")
            
        except Exception as e:
            self.logger.error(f"保存数据失败: {e}")
