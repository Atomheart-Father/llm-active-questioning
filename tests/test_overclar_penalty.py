#!/usr/bin/env python3
"""
过度澄清惩罚单元测试
"""

import unittest
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.overclar_penalty import OverClarificationPenalty

class TestOverClarificationPenalty(unittest.TestCase):
    def setUp(self):
        self.penalty = OverClarificationPenalty(alpha=0.07, cap=3)
    
    def test_no_clarification_needed(self):
        """测试不需要澄清的情况"""
        dialogue = {
            "turns": [
                {"role": "user", "content": "What is 2+2?"},
                {"role": "assistant", "content": "2+2 = 4"}
            ],
            "needs_clarification": False
        }
        
        result = self.penalty.compute_penalty(dialogue)
        self.assertEqual(result['penalty'], 0.0)
    
    def test_appropriate_clarification(self):
        """测试适当澄清的情况"""
        dialogue = {
            "turns": [
                {"role": "user", "content": "What do you think about it?"},
                {"role": "assistant", "content": "Could you clarify what 'it' refers to?"},
                {"role": "user", "content": "I mean the weather today."},
                {"role": "assistant", "content": "The weather is nice today."}
            ],
            "needs_clarification": True
        }
        
        result = self.penalty.compute_penalty(dialogue)
        self.assertEqual(result['penalty'], 0.0)  # 需要澄清且未超过cap
    
    def test_over_clarification(self):
        """测试过度澄清的情况"""
        dialogue = {
            "turns": [
                {"role": "user", "content": "What is 2+2?"},
                {"role": "assistant", "content": "请问你想要什么操作？"},
                {"role": "user", "content": "Addition."},
                {"role": "assistant", "content": "什么进制？"},
                {"role": "user", "content": "Base 10."},
                {"role": "assistant", "content": "你确定要精确结果吗？"},
                {"role": "user", "content": "Yes."},
                {"role": "assistant", "content": "需要显示计算过程吗？"},
                {"role": "user", "content": "No, just the answer."},
                {"role": "assistant", "content": "2+2 = 4"}
            ],
            "needs_clarification": False
        }
        
        result = self.penalty.compute_penalty(dialogue)
        # 应该检测到澄清行为
        self.assertGreaterEqual(result['clarify_turns'], 1)
    
    def test_clarification_detection(self):
        """测试澄清问题检测"""
        # 明确的澄清问题
        self.assertTrue(self.penalty._is_clarification_turn("Could you please clarify?"))
        self.assertTrue(self.penalty._is_clarification_turn("What do you mean by that?"))
        self.assertTrue(self.penalty._is_clarification_turn("请问你是什么意思？"))
        
        # 非澄清问题
        self.assertFalse(self.penalty._is_clarification_turn("The answer is 42."))
        self.assertFalse(self.penalty._is_clarification_turn("Let me solve this step by step."))
    
    def test_basic_functionality(self):
        """测试基本功能"""
        # 简单测试
        dialogue = {
            "turns": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ],
            "needs_clarification": False
        }
        
        result = self.penalty.compute_penalty(dialogue)
        self.assertIsInstance(result, dict)
        self.assertIn('penalty', result)
        self.assertIn('clarify_turns', result)

if __name__ == '__main__':
    unittest.main()
