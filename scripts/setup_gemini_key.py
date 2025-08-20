#!/usr/bin/env python3
"""
安全配置Gemini API Key
避免在聊天中暴露敏感信息
"""

import os
import sys
from pathlib import Path

def setup_gemini_key():
    """交互式设置Gemini API Key"""
    print("🔑 Gemini API Key 安全配置")
    print("=" * 40)
    
    env_file = Path(".env")
    
    if env_file.exists():
        print("📄 发现现有.env文件")
        with open(env_file, 'r') as f:
            content = f.read()
        if "GEMINI_API_KEY" in content:
            print("✅ 已配置GEMINI_API_KEY")
            return True
    
    print("\n请在下方输入您的Gemini API Key:")
    print("(从 https://ai.google.dev/gemini-api/docs/api-key 获取)")
    
    key = input("Gemini API Key: ").strip()
    
    if not key or not key.startswith("AIza"):
        print("❌ 无效的Gemini API Key格式")
        return False
    
    # 创建.env文件
    env_content = f"""# RC1生产环境配置
# 自动生成 - 请勿提交到git
RUN_MODE=prod
SCORER_PROVIDER=gemini
GEMINI_API_KEY={key}
SESSION_ID=rc1_training_{int(time.time())}
"""
    
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print("✅ .env文件已创建")
    print("⚠️  请确保.env文件不会提交到git (.gitignore已配置)")
    
    return True

def verify_key():
    """验证API Key有效性"""
    print("\n🔍 验证API Key有效性...")
    
    # 加载环境变量
    if Path(".env").exists():
        with open(".env", 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    
    # 运行探针
    import subprocess
    result = subprocess.run([
        "python", "scripts/probe_scorer.py", 
        "--n", "3", "--provider", "gemini", "--live"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Gemini API Key验证成功")
        return True
    else:
        print("❌ API Key验证失败:")
        print(result.stderr)
        return False

if __name__ == "__main__":
    import time
    
    if setup_gemini_key():
        if verify_key():
            print("\n🎉 Gemini API配置完成！")
            print("现在可以运行防伪闸门检查了:")
            print("  python scripts/assert_not_simulated.py --cache_hit_lt 0.90")
        else:
            print("\n❌ 请检查API Key是否正确")
            sys.exit(1)
    else:
        print("\n❌ API Key配置失败")
        sys.exit(1)
