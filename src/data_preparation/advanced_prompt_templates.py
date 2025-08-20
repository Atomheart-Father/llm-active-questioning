#!/usr/bin/env python3
"""
高级Prompt模板设计
基于GPT-5反馈优化，支持三种推理类型的高质量对话生成
"""

from typing import Dict, List, Any, Optional
from enum import Enum
import json
import random

class ReasoningType(Enum):
    """推理类型枚举"""
    MATH_REASONING = "math_reasoning"
    MULTI_HOP = "multi_hop"
    AMBIGUITY_CLARIFICATION = "ambiguity_clarification"

class AdvancedPromptTemplates:
    """高级Prompt模板生成器"""
    
    def __init__(self):
        # 数学推理的示例模板
        self.math_examples = [
            {
                "original": "计算矩形面积",
                "reconstructed": "一个图形的长和宽分别是多少时面积最大？",
                "clarification": "请问您是要计算特定图形的面积，还是要了解如何优化面积？如果是计算面积，请提供具体的长和宽数值。",
                "user_response": "我想计算一个长10米、宽5米的矩形面积。",
                "final_answer": "好的，计算矩形面积使用公式：面积 = 长 × 宽。\n\n**计算步骤：**\n1. 确定已知条件：长 = 10米，宽 = 5米\n2. 应用面积公式：面积 = 长 × 宽\n3. 代入数值：面积 = 10 × 5 = 50\n4. 添加单位：面积 = 50平方米\n\n**答案：**该矩形的面积是50平方米。"
            }
        ]
        
        # 多跳推理的示例模板
        self.multi_hop_examples = [
            {
                "original": "世界最高峰在哪个山脉",
                "reconstructed": "那座著名的高峰属于哪个山脉系统？",
                "clarification": "请问您指的是哪座高峰？是世界最高峰，还是某个特定地区的最高峰？",
                "user_response": "我问的是世界最高峰。",
                "final_answer": "明白了，让我为您分析世界最高峰的山脉归属：\n\n**推理过程：**\n1. **确定世界最高峰**：世界最高峰是珠穆朗玛峰（海拔8848.86米）\n2. **查找地理位置**：珠穆朗玛峰位于中国西藏自治区与尼泊尔边境\n3. **确定山脉系统**：该地区属于喜马拉雅山脉\n4. **验证信息**：喜马拉雅山脉是世界上最高的山脉系统\n\n**答案：**世界最高峰珠穆朗玛峰属于喜马拉雅山脉。"
            }
        ]
        
        # 歧义澄清的示例模板
        self.ambiguity_examples = [
            {
                "original": "他什么时候出生的？",
                "reconstructed": "他什么时候出生的？",
                "clarification": "抱歉，我需要更明确的信息才能帮助您。请问您指的是哪位人物呢？",
                "user_response": "我说的是爱因斯坦。",
                "final_answer": "明白了！阿尔伯特·爱因斯坦出生于1879年3月14日，出生地是德国符腾堡王国乌尔姆市。他是20世纪最伟大的物理学家之一，提出了相对论等重要理论。"
            }
        ]
    
    def generate_math_reasoning_prompt(self, original_question: str, context: str = "") -> str:
        """生成数学推理类型的prompt"""
        
        prompt = f"""你是一位专业的数学教师，需要生成一个高质量的多轮推理对话。请严格按照以下要求：

**核心要求：**
1. 问题重构应制造合理的信息缺失，引导澄清
2. 澄清问题要精准且最小化，语言礼貌自然
3. 推理过程要逻辑严谨，每步都有明确依据
4. 计算过程要准确无误，包含单位验证
5. 表达要清晰简明，符合教学习惯

**原始问题：** {original_question}
{f"**背景信息：** {context}" if context else ""}

**输出格式（严格遵循JSON格式）：**
```json
{{
    "dialogue_type": "math_reasoning",
    "original_question": "{original_question}",
    "reconstructed_question": "重构后的问题（制造合理的信息缺失）",
    "turns": [
        {{
            "role": "user",
            "content": "重构后的问题"
        }},
        {{
            "role": "assistant", 
            "content": "礼貌的澄清问题，精准定位缺失信息"
        }},
        {{
            "role": "user",
            "content": "用户提供的澄清信息"
        }},
        {{
            "role": "assistant",
            "content": "包含完整推理链的最终答案：\\n\\n**推理步骤：**\\n1. 分析已知条件\\n2. 选择合适公式\\n3. 逐步计算过程\\n4. 验证结果合理性\\n\\n**最终答案：**明确的结论"
        }}
    ],
    "reasoning_quality": {{
        "logic_rigor": "逻辑严谨程度说明",
        "calculation_accuracy": "计算准确性说明", 
        "expression_clarity": "表达清晰度说明"
    }}
}}
```

**优秀示例参考：**
{json.dumps(self.math_examples[0], ensure_ascii=False, indent=2)}

**特别注意：**
- 澄清问题必须针对真实的信息缺失
- 计算过程要包含公式、代入、运算、验证四个环节
- 避免过度澄清或无关的推理步骤
- 确保单位使用的一致性和正确性

请生成符合上述要求的高质量数学推理对话："""

        return prompt
    
    def generate_multi_hop_prompt(self, original_question: str, context: str = "") -> str:
        """生成多跳推理类型的prompt"""
        
        prompt = f"""你是一位知识渊博的研究员，需要生成一个多跳推理对话。请严格按照以下要求：

**核心要求：**
1. 必须涉及2-4个不同信息源的整合
2. 推理链条要有明确的因果或依赖关系
3. 避免时间顺序错误或逻辑矛盾
4. 澄清问题要有助于确定推理方向
5. 每一跳都对最终答案有实质贡献

**原始问题：** {original_question}
{f"**背景信息：** {context}" if context else ""}

**输出格式（严格遵循JSON格式）：**
```json
{{
    "dialogue_type": "multi_hop",
    "original_question": "{original_question}",
    "reconstructed_question": "重构后的问题（增加推理复杂度）",
    "turns": [
        {{
            "role": "user",
            "content": "重构后的问题"
        }},
        {{
            "role": "assistant",
            "content": "澄清问题，帮助确定推理起点或方向"
        }},
        {{
            "role": "user", 
            "content": "用户的澄清回答"
        }},
        {{
            "role": "assistant",
            "content": "完整的多跳推理过程：\\n\\n**推理链条：**\\n**第一跳：**[信息点1的确定]\\n**第二跳：**[基于第一跳的进一步推理]\\n**第三跳：**[整合信息得出结论]\\n\\n**因果关系分析：**[解释各步骤间的逻辑关系]\\n\\n**最终答案：**[综合结论]"
        }}
    ],
    "reasoning_analysis": {{
        "information_sources": ["信息源1", "信息源2", "信息源3"],
        "reasoning_hops": ["跳跃1描述", "跳跃2描述", "跳跃3描述"],
        "causal_relationships": "因果关系分析"
    }}
}}
```

**优秀示例参考：**
{json.dumps(self.multi_hop_examples[0], ensure_ascii=False, indent=2)}

**特别注意：**
- 每个推理跳跃都要基于前一步的结果
- 避免将同时发生的事件误作因果关系
- 确保时间序列的逻辑正确性
- 信息整合要体现不同来源的结合

请生成符合上述要求的高质量多跳推理对话："""

        return prompt
    
    def generate_ambiguity_clarification_prompt(self, original_question: str, context: str = "") -> str:
        """生成歧义澄清类型的prompt"""
        
        prompt = f"""你是一位善于沟通的AI助手，需要生成一个歧义澄清对话。请严格按照以下要求：

**核心要求：**
1. 歧义必须真实存在（代词指代、范围模糊、意图不明等）
2. 澄清问题要礼貌自然，语气亲切
3. 一次澄清解决主要歧义，避免重复提问
4. 用户回答要前后一致，符合常理
5. 最终答案要完全解决用户的真实需求

**原始问题：** {original_question}
{f"**背景信息：** {context}" if context else ""}

**输出格式（严格遵循JSON格式）：**
```json
{{
    "dialogue_type": "ambiguity_clarification",
    "original_question": "{original_question}",
    "ambiguity_analysis": {{
        "ambiguity_type": "歧义类型（代词指代/范围模糊/意图不明等）",
        "ambiguous_elements": ["具体的歧义点1", "歧义点2"],
        "clarification_strategy": "澄清策略说明"
    }},
    "turns": [
        {{
            "role": "user",
            "content": "{original_question}"
        }},
        {{
            "role": "assistant",
            "content": "礼貌的澄清问题，如：抱歉，我想更好地帮助您。请问您指的是...？"
        }},
        {{
            "role": "user",
            "content": "用户提供的具体澄清信息"
        }},
        {{
            "role": "assistant",
            "content": "明白了！基于您的澄清，我来为您详细解答：[完整准确的回答]"
        }}
    ],
    "quality_indicators": {{
        "politeness_level": "礼貌程度评价",
        "specificity": "澄清精准度评价",
        "natural_flow": "对话自然度评价"
    }}
}}
```

**优秀示例参考：**
{json.dumps(self.ambiguity_examples[0], ensure_ascii=False, indent=2)}

**歧义类型举例：**
1. **代词指代不明**："他什么时候...？"、"这个怎么样？"
2. **范围模糊**："最近天气如何？"、"那附近有什么？"
3. **意图不明**："你能帮我吗？"、"这个可以吗？"
4. **上下文缺失**："继续上次的话题"、"按照之前说的"

**澄清语言要求：**
- 使用"请问"、"可以"、"能否"等礼貌用语
- 避免重复澄清同一问题
- 确保澄清问题简洁明确

请生成符合上述要求的高质量歧义澄清对话："""

        return prompt
    
    def generate_batch_prompts(self, questions: List[Dict[str, Any]]) -> List[str]:
        """批量生成prompts"""
        prompts = []
        
        for question_data in questions:
            question_text = question_data.get("question", "")
            reasoning_type = question_data.get("type", ReasoningType.MATH_REASONING)
            context = question_data.get("context", "")
            
            if reasoning_type == ReasoningType.MATH_REASONING:
                prompt = self.generate_math_reasoning_prompt(question_text, context)
            elif reasoning_type == ReasoningType.MULTI_HOP:
                prompt = self.generate_multi_hop_prompt(question_text, context)
            elif reasoning_type == ReasoningType.AMBIGUITY_CLARIFICATION:
                prompt = self.generate_ambiguity_clarification_prompt(question_text, context)
            else:
                raise ValueError(f"未支持的推理类型: {reasoning_type}")
            
            prompts.append(prompt)
        
        return prompts
    
    def create_sample_questions(self) -> List[Dict[str, Any]]:
        """创建第一阶段验证用的样本问题"""
        
        # 数学推理问题（50个）
        math_questions = [
            {"question": "一个正方形的周长是20厘米，求面积", "type": ReasoningType.MATH_REASONING},
            {"question": "小明买了3支笔和2本书，总共花了25元，每支笔3元，每本书多少元？", "type": ReasoningType.MATH_REASONING},
            {"question": "一辆车以60公里/小时的速度行驶，需要多长时间到达目的地？", "type": ReasoningType.MATH_REASONING},
            {"question": "计算复利：本金1000元，年利率5%，3年后本息合计多少？", "type": ReasoningType.MATH_REASONING},
            {"question": "一个圆的半径是多少时面积等于某个值？", "type": ReasoningType.MATH_REASONING},
            # ... 继续添加到50个
        ]
        
        # 多跳推理问题（50个）
        multi_hop_questions = [
            {"question": "世界上最大的沙漠位于哪个大洲的哪个国家？", "type": ReasoningType.MULTI_HOP},
            {"question": "发明电话的人是哪个国家的，他还发明了什么？", "type": ReasoningType.MULTI_HOP},
            {"question": "获得诺贝尔文学奖最多的国家的首都是什么？", "type": ReasoningType.MULTI_HOP},
            {"question": "太阳系中距离地球最近的行星的表面温度是多少？", "type": ReasoningType.MULTI_HOP},
            {"question": "中国古代四大发明中最晚发明的那个对哪个朝代影响最大？", "type": ReasoningType.MULTI_HOP},
            # ... 继续添加到50个
        ]
        
        # 歧义澄清问题（50个）
        ambiguity_questions = [
            {"question": "他什么时候出生的？", "type": ReasoningType.AMBIGUITY_CLARIFICATION},
            {"question": "那家餐厅怎么样？", "type": ReasoningType.AMBIGUITY_CLARIFICATION},
            {"question": "你能帮我完成这个吗？", "type": ReasoningType.AMBIGUITY_CLARIFICATION},
            {"question": "这个价格合理吗？", "type": ReasoningType.AMBIGUITY_CLARIFICATION},
            {"question": "上次说的那个地方在哪里？", "type": ReasoningType.AMBIGUITY_CLARIFICATION},
            # ... 继续添加到50个
        ]
        
        # 为了快速验证，先返回少量样本
        sample_size = 5  # 每类型5个，总共15个用于快速测试
        
        return (
            math_questions[:sample_size] + 
            multi_hop_questions[:sample_size] + 
            ambiguity_questions[:sample_size]
        )
    
    def validate_prompt_quality(self, prompt: str) -> Dict[str, Any]:
        """验证prompt质量"""
        quality_check = {
            "length_appropriate": 100 <= len(prompt) <= 3000,
            "has_examples": "示例" in prompt or "example" in prompt.lower(),
            "has_format_specification": "JSON" in prompt or "格式" in prompt,
            "has_quality_requirements": "要求" in prompt or "requirement" in prompt.lower(),
            "clear_instructions": "请生成" in prompt or "输出" in prompt
        }
        
        quality_score = sum(quality_check.values()) / len(quality_check) * 100
        
        return {
            "quality_score": quality_score,
            "checks": quality_check,
            "is_high_quality": quality_score >= 80
        }

def main():
    """测试prompt模板生成"""
    # 创建模板生成器
    template_generator = AdvancedPromptTemplates()
    
    # 创建样本问题
    sample_questions = template_generator.create_sample_questions()
    
    print(f"创建了{len(sample_questions)}个样本问题")
    
    # 生成prompt示例
    for i, question_data in enumerate(sample_questions[:3]):  # 只显示前3个
        print(f"\n--- 样本 {i+1} ---")
        print(f"问题: {question_data['question']}")
        print(f"类型: {question_data['type'].value}")
        
        # 根据类型生成对应的prompt
        if question_data['type'] == ReasoningType.MATH_REASONING:
            prompt = template_generator.generate_math_reasoning_prompt(question_data['question'])
        elif question_data['type'] == ReasoningType.MULTI_HOP:
            prompt = template_generator.generate_multi_hop_prompt(question_data['question'])
        else:
            prompt = template_generator.generate_ambiguity_clarification_prompt(question_data['question'])
        
        # 验证prompt质量
        quality_result = template_generator.validate_prompt_quality(prompt)
        print(f"Prompt质量分数: {quality_result['quality_score']:.1f}")
        
        if quality_result['is_high_quality']:
            print("✅ 高质量prompt")
        else:
            print("⚠️ 需要改进的prompt")

if __name__ == "__main__":
    main()
