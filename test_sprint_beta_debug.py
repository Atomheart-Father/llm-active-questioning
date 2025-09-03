#!/usr/bin/env python3
"""调试Data Sprint-β脚本问题的临时脚本"""

import os
import sys
import traceback

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_imports():
    """测试模块导入"""
    try:
        print("🔍 测试模块导入...")
        from tools.data_sprint_beta import DataSprintBeta
        from tools.data_generator import DataGenerator, GenerationConfig
        from tools.deduplication import DataDeduplicator
        from tools.quality_reviewer import QualityPipeline
        print("✅ 所有模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        traceback.print_exc()
        return False

def test_environment():
    """测试环境变量"""
    try:
        print("\n🔍 测试环境变量...")
        required_keys = [
            "GEMINI_API_KEY",
            "GEMINI_API_KEY2",
            "GEMINI_API_KEY3",
            "DeepSeek_API_KEY",
            "DeepSeek_API_KEY2"
        ]

        missing = []
        for key in required_keys:
            value = os.getenv(key)
            if value:
                print(f"✅ {key}: {value[:20]}...")
            else:
                print(f"❌ {key}: 未设置")
                missing.append(key)

        if missing:
            print(f"❌ 缺少环境变量: {missing}")
            return False

        print("✅ 环境变量检查通过")
        return True

    except Exception as e:
        print(f"❌ 环境变量测试失败: {e}")
        traceback.print_exc()
        return False

def test_data_sprint_beta_init():
    """测试DataSprintBeta初始化"""
    try:
        print("\n🔍 测试DataSprintBeta初始化...")
        from tools.data_sprint_beta import DataSprintBeta

        sprint = DataSprintBeta(
            data_date="2025-09-03",
            target_alc=500,
            target_ar=300,
            target_rsd=200
        )

        print("✅ DataSprintBeta初始化成功")
        print(f"   数据日期: {sprint.batch_date}")
        print(f"   ALC目标: {sprint.target_alc}")
        print(f"   AR目标: {sprint.target_ar}")
        print(f"   RSD目标: {sprint.target_rsd}")
        return True

    except Exception as e:
        print(f"❌ DataSprintBeta初始化失败: {e}")
        traceback.print_exc()
        return False

def test_data_generator_init():
    """测试DataGenerator初始化"""
    try:
        print("\n🔍 测试DataGenerator初始化...")
        from tools.data_generator import DataGenerator, GenerationConfig

        config = GenerationConfig(
            batch_date="2025-09-03",
            alc_count=500,
            ar_count=300,
            rsd_count=200
        )

        generator = DataGenerator(config)
        print("✅ DataGenerator初始化成功")
        print(f"   输出目录: {generator.output_dir}")
        print(f"   客户端数量: {len(generator.clients)}")
        return True

    except Exception as e:
        print(f"❌ DataGenerator初始化失败: {e}")
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🚀 开始调试Data Sprint-β脚本问题...")
    print("=" * 50)

    # 测试1: 模块导入
    if not test_imports():
        return False

    # 测试2: 环境变量
    if not test_environment():
        return False

    # 测试3: DataSprintBeta初始化
    if not test_data_sprint_beta_init():
        return False

    # 测试4: DataGenerator初始化
    if not test_data_generator_init():
        return False

    print("\n" + "=" * 50)
    print("🎉 所有测试通过！脚本应该可以正常运行")
    print("💡 如果仍有问题，可能是API调用或网络问题")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
