# -*- coding: utf-8 -*-
import os, time, hashlib, threading
from collections import deque
from dataclasses import dataclass, field

def _hid(key: str) -> str:
    # 不泄露明文：仅记录 sha256 后 8 位
    return hashlib.sha256(key.encode()).hexdigest()[-8:]

@dataclass
class KeyState:
    key: str
    hid: str
    rpm: int = 9                   # 每个 key 每分钟请求上限（可由 env 覆盖）
    window_s: int = 60
    tokens: float = 9.0
    last_refill: float = field(default_factory=time.time)
    cooldown_until: float = 0.0    # 429/5xx 进入冷却
    daily_cap: int = 240           # 可选：每日软上限（安全值）
    used_today: int = 0

    def allow(self) -> bool:
        now = time.time()
        # 令牌桶续杯
        elapsed = now - self.last_refill
        self.tokens = min(self.rpm, self.tokens + elapsed * (self.rpm / self.window_s))
        self.last_refill = now
        return (self.tokens >= 1.0) and (now >= self.cooldown_until) and (self.used_today < self.daily_cap)

    def consume(self):
        self.tokens -= 1.0
        self.used_today += 1

    def backoff(self, seconds=90):
        self.cooldown_until = max(self.cooldown_until, time.time() + seconds)

class GeminiKeyRotator:
    def __init__(self):
        # 读取所有 GEMINI_API_KEY* 环境变量
        ks = []
        for i in range(10):  # 支持最多10个key
            k = os.getenv(f"GEMINI_API_KEY{i}") if i > 0 else os.getenv("GEMINI_API_KEY")
            if k:
                ks.append(k)

        if not ks:
            raise RuntimeError("No GEMINI_API_KEY provided")

        rpm = int(os.getenv("RATE_LIMIT_RPM_PER_KEY", "9"))
        self.keys = deque([KeyState(key=k, hid=_hid(k), rpm=rpm) for k in ks])
        self._lock = threading.Lock()
        self.strategy = os.getenv("GEMINI_KEYS_STRATEGY", "round_robin")

    def snapshot(self):
        return {
            "gemini_api_keys_set": len(self.keys),
            "key_hids": [k.hid for k in self.keys],
            "rpm_per_key": self.keys[0].rpm if self.keys else None,
            "strategy": self.strategy,
        }

    def acquire(self):
        with self._lock:
            for _ in range(len(self.keys)):
                k = self.keys[0]
                self.keys.rotate(-1)  # round robin
                if k.allow():
                    k.consume()
                    return k
        # 若都不可用，阻塞式等待一个最短冷却
        time.sleep(2.0)
        return self.acquire()

    def report_error(self, key_state: KeyState, status_code: int):
        # 429/5xx → 进入冷却并降速
        if status_code == 429 or (500 <= status_code < 600):
            key_state.backoff(90)
