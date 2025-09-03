#!/usr/bin/env python3
"""测试API连接性的临时脚本"""

import os
import sys
import time
import requests
import traceback

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_gemini_api():
    """测试Gemini API连接"""
    try:
        print("🔍 测试Gemini API连接...")

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("❌ GEMINI_API_KEY未设置")
            return False

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"

        payload = {
            "contents": [{
                "parts": [{"text": "Hello, test message"}]
            }]
        }

        print("📡 发送测试请求...")
        start_time = time.time()

        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        elapsed = time.time() - start_time
        print(".2f")
        if response.status_code == 200:
            print("✅ Gemini API连接成功")
            return True
        else:
            print(f"❌ Gemini API返回错误: {response.status_code}")
            print(f"响应内容: {response.text[:200]}...")
            return False

    except requests.exceptions.Timeout:
        print("❌ Gemini API请求超时")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Gemini API请求异常: {e}")
        return False
    except Exception as e:
        print(f"❌ Gemini API测试失败: {e}")
        traceback.print_exc()
        return False

def test_deepseek_api():
    """测试DeepSeek API连接"""
    try:
        print("\n🔍 测试DeepSeek API连接...")

        api_key = os.getenv("DeepSeek_API_KEY2")
        if not api_key:
            print("❌ DeepSeek_API_KEY2未设置")
            return False

        url = "https://api.deepseek.com/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "deepseek-reasoner",
            "messages": [{"role": "user", "content": "Hello, test message"}],
            "max_tokens": 10
        }

        print("📡 发送测试请求...")
        start_time = time.time()

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30
        )

        elapsed = time.time() - start_time
        print(".2f")
        if response.status_code == 200:
            print("✅ DeepSeek API连接成功")
            return True
        else:
            print(f"❌ DeepSeek API返回错误: {response.status_code}")
            print(f"响应内容: {response.text[:200]}...")
            return False

    except requests.exceptions.Timeout:
        print("❌ DeepSeek API请求超时")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ DeepSeek API请求异常: {e}")
        return False
    except Exception as e:
        print(f"❌ DeepSeek API测试失败: {e}")
        traceback.print_exc()
        return False

def test_network_connectivity():
    """测试基础网络连接"""
    try:
        print("🔍 测试基础网络连接...")

        # 测试Google连接
        response = requests.get("https://www.google.com", timeout=10)
        if response.status_code == 200:
            print("✅ 基础网络连接正常")
            return True
        else:
            print("❌ 基础网络连接异常")
            return False

    except Exception as e:
        print(f"❌ 网络连接测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 开始测试API连接性...")
    print("=" * 50)

    # 测试1: 基础网络连接
    if not test_network_connectivity():
        print("❌ 网络连接有问题，请检查网络设置")
        return False

    # 测试2: Gemini API
    gemini_ok = test_gemini_api()

    # 测试3: DeepSeek API
    deepseek_ok = test_deepseek_api()

    print("\n" + "=" * 50)
    if gemini_ok and deepseek_ok:
        print("🎉 所有API连接测试通过！")
        print("💡 如果脚本仍然卡住，可能是数据生成过程中的循环或等待问题")
        return True
    else:
        print("❌ API连接测试失败")
        if not gemini_ok:
            print("  - Gemini API连接失败")
        if not deepseek_ok:
            print("  - DeepSeek API连接失败")
        print("💡 请检查API密钥是否正确、网络连接是否稳定")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
