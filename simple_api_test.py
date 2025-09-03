#!/usr/bin/env python3
"""简单API测试脚本"""

import os
import sys
import requests

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_gemini_simple():
    """简单测试Gemini API"""
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("❌ GEMINI_API_KEY未设置")
            return False

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"

        payload = {
            "contents": [{
                "parts": [{"text": "Say hello in one word"}]
            }]
        }

        print("🔍 测试Gemini API...")
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            result = response.json()
            print("✅ Gemini API正常")
            return True
        else:
            print(f"❌ Gemini API错误: {response.status_code}")
            print(f"详情: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == "__main__":
    # 加载环境变量
    if os.path.exists('.env'):
        from dotenv import load_dotenv
        load_dotenv()

    success = test_gemini_simple()
    sys.exit(0 if success else 1)
