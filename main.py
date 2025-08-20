"""
主运行脚本
整合所有模块，提供完整的训练和评估流程
"""

import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.data_preparation.data_loader import DatasetLoader
from src.data_preparation.data_processor import DataProcessor
from src.simulation.gpt4_simulator import GPT4UserSimulator
from src.training.ppo_trainer import PPOModelTrainer, PPOTrainingConfig
from src.evaluation.evaluator import ModelEvaluator
from src.utils.config import get_config
from src.utils.logging import get_logger


def setup_environment():
    """设置环境"""
    # 设置环境变量
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    
    # 创建必要目录
    directories = ["data", "logs", "checkpoints", "models"]
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)


def prepare_data(use_mock: bool = False, generate_simulation_data: bool = False):
    """
    准备训练数据
    
    Args:
        use_mock: 是否使用模拟数据
        generate_simulation_data: 是否生成GPT-4模拟数据
    
    Returns:
        (训练数据集, 验证数据集, 评估数据集字典)
    """
    logger = get_logger()
    logger.info("开始准备数据...")
    
    # 1. 加载基础数据集
    data_loader = DatasetLoader()
    datasets = data_loader.load_all_datasets(use_mock=use_mock)
    
    if not datasets:
        logger.error("未能加载任何数据集")
        return None, None, None
    
    # 2. 数据处理和混合
    data_processor = DataProcessor()
    train_dataset, val_dataset = data_processor.prepare_training_data(datasets)
    
    # 3. 生成GPT-4模拟数据（可选）
    if generate_simulation_data:
        try:
            config = get_config()
            api_key = config.get("simulation.openai_api_key")
            
            if api_key:
                logger.info("生成GPT-4模拟数据...")
                simulator = GPT4UserSimulator(api_key)
                
                # 生成不同风格的问题
                simulation_questions = simulator.generate_batch_questions(
                    count=100,
                    styles=["simple_realistic", "complex_professional", "role_playing"]
                )
                
                # 保存模拟数据
                simulator.save_generated_data(
                    simulation_questions, 
                    "data/gpt4_simulation_data.json"
                )
                
                logger.info(f"已生成{len(simulation_questions)}个模拟问题")
            else:
                logger.warning("未配置OpenAI API密钥，跳过模拟数据生成")
        
        except Exception as e:
            logger.warning(f"生成模拟数据失败: {e}")
    
    # 4. 准备评估数据集
    eval_datasets = {}
    for dataset_name, dataset in datasets.items():
        # 使用验证或测试集作为评估数据
        eval_data = [item for item in dataset if item.get('split') in ['validation', 'test']]
        if eval_data:
            eval_datasets[dataset_name] = eval_data[:50]  # 限制评估样本数
    
    logger.info(f"数据准备完成 - 训练: {len(train_dataset)}, 验证: {len(val_dataset)}, 评估: {sum(len(d) for d in eval_datasets.values())}")
    
    return train_dataset, val_dataset, eval_datasets


def train_model(train_dataset, val_dataset, resume_from_checkpoint: str = None):
    """
    训练模型
    
    Args:
        train_dataset: 训练数据集
        val_dataset: 验证数据集
        resume_from_checkpoint: 恢复训练的检查点路径
    
    Returns:
        训练完成的模型训练器
    """
    logger = get_logger()
    logger.info("开始模型训练...")
    
    # 创建训练器
    trainer = PPOModelTrainer()
    
    # 如果需要从检查点恢复
    if resume_from_checkpoint and Path(resume_from_checkpoint).exists():
        logger.info(f"从检查点恢复训练: {resume_from_checkpoint}")
        # 这里可以添加检查点加载逻辑
    
    # 开始训练
    trainer.train(train_dataset, val_dataset)
    
    logger.info("模型训练完成")
    return trainer


def evaluate_model(model_trainer, eval_datasets):
    """
    评估模型
    
    Args:
        model_trainer: 模型训练器
        eval_datasets: 评估数据集字典
    
    Returns:
        评估结果
    """
    logger = get_logger()
    logger.info("开始模型评估...")
    
    # 初始化GPT-4模拟器（用于评估）
    gpt4_simulator = None
    try:
        config = get_config()
        api_key = config.get("simulation.openai_api_key")
        if api_key:
            gpt4_simulator = GPT4UserSimulator(api_key)
    except Exception as e:
        logger.warning(f"GPT-4模拟器初始化失败: {e}")
    
    # 创建评估器
    evaluator = ModelEvaluator(model_trainer, gpt4_simulator)
    
    # 执行综合评估
    from datasets import Dataset
    eval_datasets_formatted = {
        name: Dataset.from_list(data) 
        for name, data in eval_datasets.items()
    }
    
    results = evaluator.comprehensive_evaluation(eval_datasets_formatted)
    
    logger.info("模型评估完成")
    return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="LLM Human Collaboration Training")
    parser.add_argument("--mode", choices=["train", "eval", "full"], default="full",
                       help="运行模式: train(仅训练), eval(仅评估), full(完整流程)")
    parser.add_argument("--use-mock-data", action="store_true",
                       help="使用模拟数据进行测试")
    parser.add_argument("--generate-simulation", action="store_true",
                       help="生成GPT-4模拟数据")
    parser.add_argument("--resume-from", type=str,
                       help="从指定检查点恢复训练")
    parser.add_argument("--eval-only-model", type=str,
                       help="仅评估指定模型路径")
    parser.add_argument("--config", type=str,
                       help="配置文件路径")
    
    args = parser.parse_args()
    
    # 设置环境
    setup_environment()
    
    # 获取配置和日志器
    config = get_config()
    logger = get_logger()
    
    logger.info("=" * 50)
    logger.info("开始LLM人机协作训练实验")
    logger.info(f"运行模式: {args.mode}")
    logger.info("=" * 50)
    
    try:
        # 准备数据
        if args.mode in ["train", "full"]:
            train_dataset, val_dataset, eval_datasets = prepare_data(
                use_mock=args.use_mock_data,
                generate_simulation_data=args.generate_simulation
            )
            
            if train_dataset is None:
                logger.error("数据准备失败，退出程序")
                return
        
        # 训练模型
        model_trainer = None
        if args.mode in ["train", "full"]:
            model_trainer = train_model(
                train_dataset, 
                val_dataset, 
                resume_from_checkpoint=args.resume_from
            )
        
        # 评估模型
        if args.mode in ["eval", "full"]:
            if args.eval_only_model:
                # 仅评估指定模型
                logger.info(f"加载模型进行评估: {args.eval_only_model}")
                # 这里可以添加模型加载逻辑
                model_trainer = None  # 临时设置
            
            if args.mode == "eval" and not args.eval_only_model:
                # 需要准备评估数据
                _, _, eval_datasets = prepare_data(use_mock=args.use_mock_data)
            
            if model_trainer or args.eval_only_model:
                evaluation_results = evaluate_model(model_trainer, eval_datasets)
                logger.info(f"评估完成，综合分数: {evaluation_results.get('overall_score', 0.0):.3f}")
        
        logger.info("=" * 50)
        logger.info("实验完成！")
        logger.info("=" * 50)
    
    except KeyboardInterrupt:
        logger.info("用户中断训练")
    except Exception as e:
        logger.error(f"实验过程中发生错误: {e}")
        raise
    finally:
        # 清理资源
        logger.close()


if __name__ == "__main__":
    main()
