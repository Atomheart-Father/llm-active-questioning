#!/usr/bin/env python3
"""
评分凭证日志系统
记录每次真实API调用的凭证信息
"""

import json
import time
import os
from pathlib import Path
from typing import Dict, Any

class ScoringLedger:
    def __init__(self, ledger_file: str = "reports/rc1/scoring_ledger.jsonl"):
        self.ledger_file = Path(ledger_file)
        self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log_scoring_call(self, provider: str, http_status: int, 
                        billable_tokens: int, latency_ms: float,
                        sample_id: str = None, task: str = None):
        """记录一次评分调用"""
        entry = {
            "timestamp": time.time(),
            "iso_time": time.strftime('%Y-%m-%d %H:%M:%S'),
            "provider": provider,
            "http_status": http_status,
            "billable_tokens": billable_tokens,
            "latency_ms": latency_ms,
            "sample_id": sample_id,
            "task": task,
            "session_id": os.getenv("SESSION_ID", "unknown")
        }
        
        with open(self.ledger_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def get_recent_stats(self, hours: int = 1) -> Dict[str, Any]:
        """获取最近N小时的统计"""
        if not self.ledger_file.exists():
            return {"total_calls": 0, "billable_calls": 0, "avg_latency": 0}
        
        cutoff_time = time.time() - (hours * 3600)
        total_calls = 0
        billable_calls = 0
        latencies = []
        
        with open(self.ledger_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("timestamp", 0) >= cutoff_time:
                        total_calls += 1
                        if entry.get("billable_tokens", 0) > 0:
                            billable_calls += 1
                        if entry.get("latency_ms", 0) > 0:
                            latencies.append(entry["latency_ms"])
                except:
                    continue
        
        return {
            "total_calls": total_calls,
            "billable_calls": billable_calls,
            "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
            "cache_hit_rate": (total_calls - billable_calls) / total_calls if total_calls > 0 else 0
        }

# 全局实例
ledger = ScoringLedger()

def log_api_call(provider: str, http_status: int, billable_tokens: int, 
                latency_ms: float, sample_id: str = None, task: str = None):
    """便捷函数：记录API调用"""
    ledger.log_scoring_call(provider, http_status, billable_tokens, 
                           latency_ms, sample_id, task)

if __name__ == "__main__":
    # 测试
    log_api_call("deepseek_r1", 200, 1500, 850.5, "test_sample", "math")
    print("✅ 测试日志记录完成")
    
    stats = ledger.get_recent_stats(1)
    print(f"📊 最近1小时统计: {stats}")
