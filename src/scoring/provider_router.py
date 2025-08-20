#!/usr/bin/env python3
"""
评分提供商路由器 - RC1强制单一provider
"""

import os

# RC1强制检查：仅允许Gemini
def enforce_rc1_provider():
    """RC1强制检查：仅允许SCORER_PROVIDER=gemini"""
    provider = os.getenv("SCORER_PROVIDER", "").lower()
    if provider != "gemini":
        raise RuntimeError(f"RC1 仅允许 SCORER_PROVIDER=gemini，当前: {provider}")

# 立即执行检查
enforce_rc1_provider()

class ProviderRouter:
    """评分提供商路由器"""
    
    def __init__(self):
        # 再次确认provider
        enforce_rc1_provider()
        self.provider = "gemini"
    
    def route_scoring_request(self, request):
        """路由评分请求 - RC1仅支持Gemini"""
        if self.provider != "gemini":
            raise RuntimeError("RC1禁用非Gemini provider分支")
        
        # 其他provider路径全部禁用
        if hasattr(self, '_route_deepseek'):
            raise AssertionError("DeepSeek分支不可到达")
        if hasattr(self, '_route_openai'):
            raise AssertionError("OpenAI分支不可到达")
            
        return self._route_gemini(request)
    
    def _route_gemini(self, request):
        """Gemini路由实现"""
        from src.evaluation.advanced_reward_system import MultiDimensionalRewardSystem
        system = MultiDimensionalRewardSystem()
        return system.evaluate_dialogue(request)
    
    # 禁用其他provider方法
    def _route_deepseek(self, request):
        raise AssertionError("RC1禁用：DeepSeek分支不可到达")
    
    def _route_openai(self, request):
        raise AssertionError("RC1禁用：OpenAI分支不可到达")
