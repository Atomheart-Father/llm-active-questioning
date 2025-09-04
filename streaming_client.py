#!/usr/bin/env python3
"""
DeepSeek流式客户端 - 解决超时问题
支持流式推理、增量落盘、分块输出拼装
"""

import os
import json
import time
import asyncio
import threading
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import logging

from openai import OpenAI
from openai import APIError, Timeout, RateLimitError

logger = logging.getLogger(__name__)

class StreamingLLMClient:
    """流式LLM客户端，支持超时保护和Fail-Over"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.connect_timeout = 10  # 连接超时10秒
        self.read_timeout = 180    # 读取超时180秒（从120增加到180）
        self.write_timeout = 120   # 写入超时120秒
        self.total_timeout = 300   # 总超时5分钟
        self.idle_timeout = 60     # 空闲超时60秒（从15增加到60）
        self.max_retries = 3       # 最大重试次数

    def stream_chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        output_file: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        流式对话，支持增量落盘和超时保护

        Args:
            model: 模型名称
            messages: 消息列表
            output_file: 输出文件路径（可选，用于增量落盘）
            **kwargs: 其他参数

        Returns:
            完整的响应结果
        """
        full_response = ""
        last_activity = time.time()

        # 准备输出文件
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # 开启流式请求
            stream = self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                timeout=self.total_timeout,
                **kwargs
            )

            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    last_activity = time.time()

                    # 增量落盘
                    if output_file:
                        self._save_partial_response(output_file, full_response)

                # 检查空闲超时
                if time.time() - last_activity > self.idle_timeout:
                    logger.warning(f"流式响应空闲超时 ({self.idle_timeout}s)，触发Fail-Over")
                    break

            # 尝试解析完整响应
            try:
                result = self._parse_response(full_response)
                return {
                    "success": True,
                    "content": result,
                    "full_response": full_response
                }
            except json.JSONDecodeError as e:
                logger.warning(f"JSON解析失败: {e}")
                return {
                    "success": False,
                    "error": "JSON_PARSE_ERROR",
                    "full_response": full_response
                }

        except (APIError, Timeout, RateLimitError) as e:
            logger.error(f"API调用失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
        except Exception as e:
            logger.error(f"未知错误: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _save_partial_response(self, file_path: str, content: str):
        """保存部分响应到文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": time.time(),
                    "content": content,
                    "is_partial": True
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存部分响应失败: {e}")

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """解析响应文本，提取最大JSON对象"""
        import re

        # 查找所有的JSON对象
        json_pattern = r'\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}'
        matches = re.findall(json_pattern, response_text, re.DOTALL)

        if not matches:
            raise json.JSONDecodeError("No JSON found", response_text, 0)

        # 选择最大的JSON对象
        largest_json = max(matches, key=len)

        try:
            return json.loads(largest_json)
        except json.JSONDecodeError:
            # 如果解析失败，尝试清理和重新解析
            cleaned = re.sub(r'[^\x20-\x7E\n\r\t]', '', largest_json)
            return json.loads(cleaned)

    def chat_with_retry(
        self,
        model: str,
        messages: List[Dict[str, str]],
        failovers: List[Dict[str, Any]] = None,
        task_type: str = "alc",  # alc, ar, rsd
        **kwargs
    ) -> Dict[str, Any]:
        """
        带重试的对话，支持Fail-Over路由

        Args:
            model: 模型名称
            messages: 消息列表
            failovers: Fail-Over配置列表
            task_type: 任务类型 (alc, ar, rsd)
            **kwargs: 其他参数

        Returns:
            响应结果
        """
        failovers = failovers or []

        # 针对AR/RSD启用DeepSeek→Gemini Fail-Over
        if task_type in ["ar", "rsd"] and not failovers:
            failovers = [{
                "provider": "gemini",
                "model": "gemini-2.5-pro",
                "reason": "deepseek_timeout"
            }]

        for attempt in range(self.max_retries):
            try:
                logger.info(f"尝试调用 {model} (第{attempt+1}次, 任务类型: {task_type})")

                result = self.stream_chat(model, messages, **kwargs)

                if result["success"]:
                    return result

                # 记录Fail-Over
                failover_info = {
                    "from": model,
                    "to": failovers[0]["provider"] if failovers else None,
                    "reason_code": result.get("error_type", "UNKNOWN"),
                    "ts": time.time(),
                    "attempt": attempt + 1,
                    "task_type": task_type
                }

                logger.warning(f"调用失败，记录Fail-Over: {failover_info}")

                # 如果有Fail-Over配置，继续尝试
                if failovers and attempt < len(failovers):
                    next_config = failovers[attempt]
                    logger.info(f"尝试Fail-Over到: {next_config}")

                    # 对于AR/RSD，实施DeepSeek→Gemini Fail-Over
                    if task_type in ["ar", "rsd"] and next_config.get("provider") == "gemini":
                        logger.info("实施AR/RSD DeepSeek→Gemini Fail-Over")
                        # 这里会由调用方处理实际的Fail-Over逻辑

                    time.sleep(2 ** attempt)  # 指数退避

            except Exception as e:
                logger.error(f"重试失败: {e}")
                time.sleep(2 ** attempt)  # 指数退避

        return {
            "success": False,
            "error": "ALL_ATTEMPTS_FAILED",
            "max_retries": self.max_retries,
            "task_type": task_type
        }

# 便捷函数
def create_streaming_client(api_key: str) -> StreamingLLMClient:
    """创建流式客户端"""
    return StreamingLLMClient(api_key)

if __name__ == "__main__":
    # 测试代码
    import sys

    if len(sys.argv) < 2:
        print("用法: python streaming_client.py <api_key>")
        sys.exit(1)

    api_key = sys.argv[1]
    client = create_streaming_client(api_key)

    # 测试消息
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello, can you help me with a simple JSON response?"}
    ]

    result = client.stream_chat("deepseek-chat", messages)
    print(f"结果: {result}")
