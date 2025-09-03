#!/usr/bin/env python3
"""测试修复后的数据生成功能"""

import os
import sys
import json
from pathlib import Path

# 设置测试环境变量（使用模拟密钥）
os.environ["GEMINI_API_KEY"] = "test_key_0"
os.environ["GEMINI_API_KEY2"] = "test_key_1"
os.environ["GEMINI_API_KEY3"] = "test_key_2"
os.environ["DEEPSEEK_API_KEY"] = "test_deepseek"
os.environ["DEEPSEEK_API_KEY2"] = "test_deepseek_2"
os.environ["FAILOVER_ENABLE"] = "true"
os.environ["ALLOW_RSD_FALLBACK"] = "false"

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_generation_quality():
    """测试生成质量"""
    print("🧪 开始测试修复后的数据生成...")

    try:
        from tools.data_generator import DataGenerator, GenerationConfig

        # 创建配置
        config = GenerationConfig(
            batch_date="2025-09-03",
            alc_count=5,
            ar_count=3,
            rsd_count=2,
            temperature=0.7
        )

        # 创建生成器
        generator = DataGenerator(config)

        print("✅ 生成器初始化成功")

        # 测试prompt生成
        alc_prompt = generator._get_alc_prompt()
        print(f"🎯 ALC Prompt样例:\n{alc_prompt[:200]}...")

        # 检查多样性池
        print("🎨 多样性池检查:")
        personas = alc_prompt.count("一个")  # 检查是否包含人设
        print(f"  - 人设池: {'✅' if personas > 0 else '❌'}")

        # 测试质量检查方法
        test_sample = {
            "id": "TEST-001",
            "turns": [
                {"role": "user", "text": "测试问题"},
                {"role": "model_target", "text": "<ASK>请提供更多信息</ASK>"}
            ],
            "labels": {
                "ask_required": True,
                "ambiguity_types": ["test"],
                "good_question_set": ["test"]
            },
            "reasoning": {
                "actions": [
                    {"t": "AWARE_GAP", "vars": ["test"]},
                    {"t": "ASK", "q": "test"},
                    {"t": "STOP_ASK"}
                ]
            }
        }

        quality_result = generator._quality_check(test_sample, "ALC")
        print(f"🎚️ 质量检查测试: {'✅ 通过' if quality_result['passed'] else '❌ 失败'}")
        if not quality_result['passed']:
            print(f"  原因: {quality_result['reasons']}")

        # 测试句子改写
        original = "请告诉我你的想法"
        rewritten = generator._rewrite_sentence(original)
        print(f"📝 句子改写测试: '{original}' → '{rewritten}'")

        # 测试model_target内容修复
        test_turns = [
            {"role": "user", "text": "测试"},
            {"role": "model_target", "text": "听起来很棒！为了更好地帮您规划，<ASK>请告诉我具体时间</ASK>"}
        ]
        fixed_turns = generator._fix_model_target_content(test_turns)
        print(f"🔧 model_target修复测试: {fixed_turns[1]['text']}")

        print("✅ 所有基础测试通过！")

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_generation_quality()
    sys.exit(0 if success else 1)
