#!/usr/bin/env python3
"""
Qwen3-4B-Thinking GGUF 模型下载脚本
"""

import os
import sys
import subprocess
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_huggingface_cli():
    """检查并安装 huggingface_hub"""
    try:
        import huggingface_hub
        logger.info("✅ huggingface_hub 已安装")
        return True
    except ImportError:
        logger.info("📦 安装 huggingface_hub...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub[cli]"])
            return True
        except subprocess.CalledProcessError:
            logger.error("❌ huggingface_hub 安装失败")
            return False

def download_qwen_gguf():
    """下载 Qwen3-4B-Thinking GGUF 模型"""
    
    # 检查依赖
    if not check_huggingface_cli():
        return False
    
    # 设置下载目录
    home_dir = Path.home()
    models_dir = home_dir / "llama_cpp_workspace" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"📂 模型下载目录: {models_dir}")
    
    # Qwen3-4B-Thinking 的 GGUF 模型信息
    # 注意：实际的模型仓库名可能需要调整
    model_repo = "unsloth/Qwen3-4B-Thinking-2507-GGUF"  # 这是假设的仓库名
    
    # 常见的 GGUF 模型文件名模式
    possible_files = [
        "qwen3-4b-thinking-q4_k_m.gguf",
        "qwen3-4b-thinking-q4_0.gguf", 
        "qwen3-4b-thinking-q5_k_m.gguf",
        "qwen3-4b-thinking-q8_0.gguf",
        "qwen3-4b-thinking.gguf"
    ]
    
    logger.info("🔍 搜索可用的 GGUF 模型文件...")
    
    # 方法1: 尝试直接下载（如果知道确切的文件名）
    try:
        from huggingface_hub import hf_hub_download, list_repo_files
        
        # 先列出仓库中的文件
        try:
            files = list_repo_files(model_repo)
            gguf_files = [f for f in files if f.endswith('.gguf')]
            
            if gguf_files:
                logger.info(f"📋 找到 GGUF 文件: {gguf_files}")
                
                # 优先选择 q4_k_m 量化版本（平衡质量和大小）
                selected_file = None
                for preferred in ["q4_k_m.gguf", "q4_0.gguf", "q5_k_m.gguf"]:
                    for file in gguf_files:
                        if preferred in file:
                            selected_file = file
                            break
                    if selected_file:
                        break
                
                if not selected_file:
                    selected_file = gguf_files[0]  # 选择第一个可用文件
                
                logger.info(f"📥 下载模型文件: {selected_file}")
                
                downloaded_path = hf_hub_download(
                    repo_id=model_repo,
                    filename=selected_file,
                    local_dir=models_dir,
                    local_dir_use_symlinks=False
                )
                
                logger.info(f"✅ 模型下载完成: {downloaded_path}")
                return True
                
            else:
                logger.warning(f"⚠️ 仓库 {model_repo} 中未找到 GGUF 文件")
                
        except Exception as e:
            logger.warning(f"⚠️ 无法访问仓库 {model_repo}: {e}")
    
    except ImportError:
        logger.error("❌ huggingface_hub 导入失败")
        return False
    
    # 方法2: 提供手动下载指南
    logger.info("📖 手动下载指南:")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("1. 访问 Hugging Face 模型页面:")
    logger.info("   https://huggingface.co/Qwen/Qwen3-4B-Thinking")
    logger.info("")
    logger.info("2. 查找 GGUF 格式的模型文件，或者使用转换工具:")
    logger.info("   - 寻找以 .gguf 结尾的文件")
    logger.info("   - 推荐选择 q4_k_m 或 q4_0 量化版本（平衡质量和大小）")
    logger.info("")
    logger.info("3. 下载后将文件放置到:")
    logger.info(f"   {models_dir}")
    logger.info("")
    logger.info("4. 重命名为: qwen3-4b-thinking.gguf")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    return False

def main():
    """主函数"""
    logger.info("🚀 Qwen3-4B-Thinking GGUF 模型下载工具")
    logger.info("=" * 50)
    
    success = download_qwen_gguf()
    
    if success:
        logger.info("🎉 模型下载完成！可以开始测试了。")
    else:
        logger.info("ℹ️ 请按照上述指南手动下载模型文件。")

if __name__ == "__main__":
    main()
