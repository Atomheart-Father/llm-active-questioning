#!/usr/bin/env python3
"""
快速测试脚本
验证各个模块是否正常工作
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_config():
    """测试配置模块"""
    print("测试配置模块...")
    try:
        from src.utils.config import get_config
        config = get_config()
        print(f"✅ 配置加载成功")
        print(f"   模型名称: {config.get('model.name')}")
        print(f"   数据目录: {config.get('data.data_dir')}")
        return True
    except Exception as e:
        print(f"❌ 配置模块测试失败: {e}")
        return False

def test_logging():
    """测试日志模块"""
    print("测试日志模块...")
    try:
        from src.utils.logging import get_logger
        logger = get_logger("test")
        logger.info("这是一条测试日志")
        print("✅ 日志模块正常")
        return True
    except Exception as e:
        print(f"❌ 日志模块测试失败: {e}")
        return False

def test_data_loader():
    """测试数据加载模块"""
    print("测试数据加载模块...")
    try:
        from src.data_preparation.data_loader import DatasetLoader
        loader = DatasetLoader()
        
        # 测试模拟数据集
        mock_datasets = loader.create_mock_datasets()
        print(f"✅ 数据加载器正常，模拟数据集数量: {len(mock_datasets)}")
        
        for name, dataset in mock_datasets.items():
            print(f"   {name}: {len(dataset)} 样本")
        
        return True
    except Exception as e:
        print(f"❌ 数据加载模块测试失败: {e}")
        return False

def test_data_processor():
    """测试数据处理模块"""
    print("测试数据处理模块...")
    try:
        from src.data_preparation.data_loader import DatasetLoader
        from src.data_preparation.data_processor import DataProcessor
        
        # 加载模拟数据
        loader = DatasetLoader()
        datasets = loader.create_mock_datasets()
        
        # 处理数据
        processor = DataProcessor()
        train_dataset, val_dataset = processor.prepare_training_data(datasets)
        
        print(f"✅ 数据处理器正常")
        print(f"   训练集: {len(train_dataset)} 样本")
        print(f"   验证集: {len(val_dataset)} 样本")
        
        # 检查格式化结果
        if len(train_dataset) > 0:
            sample = train_dataset[0]
            print(f"   样本格式: {list(sample.keys())}")
        
        return True
    except Exception as e:
        print(f"❌ 数据处理模块测试失败: {e}")
        return False

def test_reward_system():
    """测试奖励系统"""
    print("测试奖励系统...")
    try:
        from src.training.reward_system import RewardCalculator
        
        calculator = RewardCalculator()
        
        # 测试样本
        sample = {
            'dataset': 'gsm8k',
            'answer': 'Janet has 3 ducks that each lay 1 egg per day, so she gets 3*1 = 3 eggs per day. In a week (7 days), she gets 3*7 = 21 eggs. #### 21'
        }
        
        prediction = "Janet有3只鸭子，每只每天下1个蛋，所以她每天得到3个蛋。一周(7天)内，她得到3*7 = 21个蛋。答案是21。"
        
        reward = calculator.calculate_total_reward(sample, prediction)
        
        print(f"✅ 奖励系统正常")
        print(f"   正确性奖励: {reward['correctness']:.3f}")
        print(f"   安全性奖励: {reward['safety']:.3f}")
        print(f"   总奖励: {reward['total']:.3f}")
        
        return True
    except Exception as e:
        print(f"❌ 奖励系统测试失败: {e}")
        return False

def test_gpt4_simulator():
    """测试GPT-4模拟器"""
    print("测试GPT-4模拟器...")
    try:
        from src.utils.config import get_config
        
        config = get_config()
        api_key = config.get("simulation.openai_api_key")
        
        if not api_key:
            print("⚠️  未配置OpenAI API密钥，跳过GPT-4模拟器测试")
            return True
        
        from src.simulation.gpt4_simulator import GPT4UserSimulator
        
        simulator = GPT4UserSimulator(api_key)
        
        # 生成一个测试问题
        question = simulator.generate_user_question(style="simple_realistic")
        print(f"✅ GPT-4模拟器正常")
        print(f"   生成的问题: {question[:100]}...")
        
        return True
    except Exception as e:
        print(f"❌ GPT-4模拟器测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 50)
    print("开始项目模块测试")
    print("=" * 50)
    
    tests = [
        test_config,
        test_logging,
        test_data_loader,
        test_data_processor,
        test_reward_system,
        test_gpt4_simulator
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ 测试异常: {e}")
        print()
    
    print("=" * 50)
    print(f"测试完成: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！项目准备就绪。")
        return 0
    else:
        print("⚠️  部分测试失败，请检查相关模块。")
        return 1

if __name__ == "__main__":
    exit(main())
