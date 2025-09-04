#!/usr/bin/env python3
"""
测试流式客户端的空闲心跳检测
"""

import time
import pytest
from unittest.mock import Mock, patch
from streaming_client import StreamingLLMClient


def test_idle_timeout_detection():
    """测试空闲超时检测"""
    client = StreamingLLMClient("test_key")

    # 模拟流式响应
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].delta = Mock()
    mock_response.choices[0].delta.content = None  # 模拟空内容

    with patch.object(client.client.chat.completions, 'create') as mock_create:
        mock_create.return_value = iter([mock_response])

        # 设置较短的空闲超时
        client.idle_timeout = 1  # 1秒超时

        start_time = time.time()

        result = client.stream_chat("test-model", [{"role": "user", "content": "test"}])

        elapsed = time.time() - start_time

        # 应该在1秒内超时
        assert elapsed < 2, f"空闲超时检测失败，耗时: {elapsed}秒"

        # 应该检测到空闲超时
        assert not result["success"], "应该检测到空闲超时"


def test_streaming_with_content():
    """测试正常流式响应"""
    client = StreamingLLMClient("test_key")

    # 模拟正常响应
    responses = []
    for i in range(3):
        mock_resp = Mock()
        mock_resp.choices = [Mock()]
        mock_resp.choices[0].delta = Mock()
        mock_resp.choices[0].delta.content = f"chunk_{i}"
        responses.append(mock_resp)

    with patch.object(client.client.chat.completions, 'create') as mock_create:
        mock_create.return_value = iter(responses)

        result = client.stream_chat("test-model", [{"role": "user", "content": "test"}])

        # 应该成功
        assert result["success"], "正常流式响应应该成功"

        # 检查内容
        expected_content = "chunk_0chunk_1chunk_2"
        assert result["full_response"] == expected_content, f"内容拼接错误: {result['full_response']}"


def test_failover_for_ar_rsd():
    """测试AR/RSD的Fail-Over逻辑"""
    client = StreamingLLMClient("test_key")

    # 测试AR任务的Fail-Over配置
    result = client.chat_with_retry(
        "deepseek-reasoner",
        [{"role": "user", "content": "test"}],
        task_type="ar"
    )

    # 应该自动配置Fail-Over
    assert len(client.failovers) > 0, "AR任务应该自动配置Fail-Over"
    assert client.failovers[0]["provider"] == "gemini", "应该Fail-Over到Gemini"


if __name__ == "__main__":
    test_idle_timeout_detection()
    test_streaming_with_content()
    test_failover_for_ar_rsd()
    print("所有测试通过!")
