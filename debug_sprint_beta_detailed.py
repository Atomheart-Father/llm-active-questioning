#!/usr/bin/env python3
"""详细调试Data Sprint-β卡住问题的脚本"""

import os
import sys
import time
import logging
import traceback

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug_sprint_beta.log')
    ]
)

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def debug_data_generation():
    """调试数据生成过程"""
    try:
        print("🚀 开始详细调试数据生成...")
        logger = logging.getLogger(__name__)

        # 步骤1: 导入模块
        logger.info("步骤1: 导入模块")
        from tools.data_generator import DataGenerator, GenerationConfig

        # 步骤2: 创建配置
        logger.info("步骤2: 创建配置")
        config = GenerationConfig(
            batch_date="2025-09-03",
            alc_count=5,  # 先用小数量测试
            ar_count=3,
            rsd_count=2
        )

        # 步骤3: 初始化生成器
        logger.info("步骤3: 初始化生成器")
        generator = DataGenerator(config)

        # 步骤4: 测试单个样本生成
        logger.info("步骤4: 测试ALC样本生成")
        alc_samples = generator.generate_alc_data()
        logger.info(f"ALC生成完成: {len(alc_samples)} 个样本")

        # 步骤5: 测试AR样本生成
        logger.info("步骤5: 测试AR样本生成")
        ar_samples = generator.generate_ar_data()
        logger.info(f"AR生成完成: {len(ar_samples)} 个样本")

        # 步骤6: 测试RSD样本生成
        logger.info("步骤6: 测试RSD样本生成")
        rsd_samples = generator.generate_rsd_data()
        logger.info(f"RSD生成完成: {len(rsd_samples)} 个样本")

        # 步骤7: 保存样本
        logger.info("步骤7: 保存样本")
        if alc_samples:
            generator.save_samples(alc_samples, "ALC/part-001.jsonl")
        if ar_samples:
            generator.save_samples(ar_samples, "AR/part-001.jsonl")
        if rsd_samples:
            generator.save_samples(rsd_samples, "RSD/part-001.jsonl")

        # 步骤8: 保存provenance
        logger.info("步骤8: 保存provenance")
        generator.save_provenance()

        total = len(alc_samples) + len(ar_samples) + len(rsd_samples)
        logger.info(f"✅ 数据生成完成: 总计 {total} 个样本")

        return True

    except Exception as e:
        logger.error(f"❌ 数据生成调试失败: {e}")
        traceback.print_exc()
        return False

def debug_full_pipeline():
    """调试完整流水线"""
    try:
        print("\n🚀 开始调试完整流水线...")
        logger = logging.getLogger(__name__)

        # 步骤1: 导入DataSprintBeta
        logger.info("流水线步骤1: 导入DataSprintBeta")
        from tools.data_sprint_beta import DataSprintBeta

        # 步骤2: 初始化
        logger.info("流水线步骤2: 初始化DataSprintBeta")
        sprint = DataSprintBeta(
            data_date="2025-09-03",
            target_alc=5,
            target_ar=3,
            target_rsd=2
        )

        # 步骤3: 环境检查
        logger.info("流水线步骤3: 环境检查")
        if not sprint.check_environment():
            logger.error("环境检查失败")
            return False

        # 步骤4: 数据生成
        logger.info("流水线步骤4: 数据生成")
        start_time = time.time()
        if not sprint.generate_data():
            logger.error("数据生成失败")
            return False
        generation_time = time.time() - start_time
        logger.info(".2f")
        # 步骤5: 去重处理
        logger.info("流水线步骤5: 去重处理")
        start_time = time.time()
        if not sprint.deduplicate_data():
            logger.error("去重处理失败")
            return False
        dedup_time = time.time() - start_time
        logger.info(".2f")
        # 步骤6: 质量评审
        logger.info("流水线步骤6: 质量评审")
        start_time = time.time()
        if not sprint.review_quality():
            logger.error("质量评审失败")
            return False
        review_time = time.time() - start_time
        logger.info(".2f")
        # 步骤7: 最终验证
        logger.info("流水线步骤7: 最终验证")
        if not sprint.validate_final_dataset():
            logger.error("最终验证失败")
            return False

        # 步骤8: 生成报告
        logger.info("流水线步骤8: 生成最终报告")
        if not sprint.generate_final_report():
            logger.error("生成报告失败")
            return False

        logger.info("✅ 完整流水线调试成功")
        return True

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"❌ 流水线调试失败: {e}")
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🚀 开始详细调试Data Sprint-β卡住问题...")
    print("=" * 60)

    # 设置更详细的日志
    logger = logging.getLogger(__name__)
    logger.info("开始调试会话")

    # 测试1: 数据生成过程
    print("\n📊 测试1: 数据生成过程")
    if not debug_data_generation():
        print("❌ 数据生成测试失败")
        return False

    # 测试2: 完整流水线
    print("\n📊 测试2: 完整流水线")
    if not debug_full_pipeline():
        print("❌ 流水线测试失败")
        return False

    print("\n" + "=" * 60)
    print("🎉 所有调试测试通过！")
    print("📋 检查 debug_sprint_beta.log 获取详细日志")
    print("💡 如果生产环境仍有问题，请查看日志文件定位具体卡住位置")

    logger.info("调试会话结束")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
