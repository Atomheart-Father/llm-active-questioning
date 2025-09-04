#!/usr/bin/env python3
"""临时脚本：运行10条微批验证"""
import os
import sys
import subprocess

def load_env():
    """加载.env文件中的环境变量"""
    env_file = ".env"
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('set') and 'export' in line and '=' in line:
                    # 解析 export KEY="value" 格式
                    parts = line.replace('export', '').strip().split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        # 移除引号
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        os.environ[key] = value

def main():
    # 加载环境变量
    load_env()

    # 验证关键环境变量
    required_keys = ['GEMINI_API_KEY', 'GEMINI_API_KEY2', 'GEMINI_API_KEY3', 'DeepSeek_API_KEY2']
    missing = [k for k in required_keys if not os.environ.get(k)]
    if missing:
        print(f"❌ 缺少环境变量: {', '.join(missing)}")
        return False

    print("✅ 环境变量加载成功")

    # 设置Python路径和环境变量
    env = os.environ.copy()
    env['PYTHONPATH'] = '/Users/bozhongxiao/Desktop/克罗米王国国立电台/代码项目/project'
    # 设置微批验证的参数（严格遵守RULE3：不超过20条）
    env['DATA_DATE'] = '2025-09-03'
    env['TARGET_ALC'] = '4'   # 4个ALC样本
    env['TARGET_AR'] = '3'    # 3个AR样本
    env['TARGET_RSD'] = '3'   # 3个RSD样本
    # 总计10条，符合微批验证要求

    # 运行10条微批验证
    cmd = [
        sys.executable,
        "tools/data_sprint_beta.py"
    ]

    print("🚀 启动10条微批验证...")
    try:
        result = subprocess.run(cmd, env=env, timeout=300)  # 5分钟超时
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("❌ 执行超时")
        return False
    except Exception as e:
        print(f"❌ 执行异常: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
