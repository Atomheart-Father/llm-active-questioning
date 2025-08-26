"""
用途：验证 telemetry 兼容包装接受 status/status_code，不抛异常。
预期：运行时打印 OK；若异常，测试失败。
"""
from src.evaluation.advanced_reward_system import log_api_call

def test_log_status_arg_does_not_crash(capsys):
    # 不要求后端落库；只验证不会 TypeError
    log_api_call(provider="gemini", model="2.5-pro",
                 latency_ms=123, ok=True, status=200, meta={"canary": True})
    print("OK")
    out, _ = capsys.readouterr()
    assert "OK" in out
