#!/usr/bin/env python3
"""
异步命令执行器
基于GPT-5技术方案实现的高并发、容错、监控一体化的命令执行框架
"""

import asyncio
import time
import json
import hashlib
import os
import signal
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class ExecutionResult:
    """命令执行结果"""
    cmd: str
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    latency_ms: int
    tries: int

class AsyncCommandExecutor:
    """异步命令执行器
    
    特性:
    - 并发执行多个命令
    - 自动重试和超时控制
    - 实时进度监控
    - 详细日志记录
    - 优雅的中断处理
    """
    
    def __init__(self, max_concurrent=5, timeout_s=180, retries=2, log_dir="logs"):
        self.sem = asyncio.Semaphore(max_concurrent)
        self.timeout_s = timeout_s
        self.retries = retries
        self.log_dir = log_dir
        
        # 确保日志目录存在
        os.makedirs(log_dir, exist_ok=True)
        
        # 执行统计
        self._running = 0
        self._done = 0
        self._failed = 0
        self._lat_hist = []
        self._start_time = time.time()
        
        # 子进程管理
        self._active_processes = set()
        
        # 设置信号处理
        self._setup_signal_handlers()
        
        logger.info(f"AsyncCommandExecutor initialized: max_concurrent={max_concurrent}, timeout={timeout_s}s")
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except ValueError:
            # 在某些环境下可能无法设置信号处理器
            logger.warning("无法设置信号处理器，中断处理可能不完整")
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"收到信号 {signum}，开始优雅关闭...")
        asyncio.create_task(self._cleanup_processes())
    
    async def _cleanup_processes(self):
        """清理所有活动进程"""
        if self._active_processes:
            logger.info(f"正在终止 {len(self._active_processes)} 个活动进程...")
            for proc in list(self._active_processes):
                try:
                    proc.terminate()
                    await asyncio.sleep(0.1)
                    if proc.returncode is None:
                        proc.kill()
                except Exception as e:
                    logger.error(f"终止进程失败: {e}")
            self._active_processes.clear()
    
    async def _run_one(self, cmd: str) -> ExecutionResult:
        """执行单个命令"""
        tries, start = 0, time.time()
        last_err, stdout, stderr, code = None, "", "", -1
        
        while tries <= self.retries:
            tries += 1
            proc = None
            
            try:
                async with self.sem:
                    # 创建子进程
                    proc = await asyncio.create_subprocess_shell(
                        cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    self._active_processes.add(proc)
                    self._running += 1
                    
                    # 等待执行完成，支持超时
                    out, err = await asyncio.wait_for(
                        proc.communicate(), 
                        timeout=self.timeout_s
                    )
                    
                    code = proc.returncode
                    stdout = out.decode(errors="ignore") if out else ""
                    stderr = err.decode(errors="ignore") if err else ""
                    
                    # 从活动进程中移除
                    self._active_processes.discard(proc)
                    self._running -= 1
                    
                    ok = (code == 0)
                    if ok:
                        break
                    
                    last_err = f"exit={code} {stderr[-200:]}"
                    
            except asyncio.TimeoutError:
                last_err = f"timeout>{self.timeout_s}s"
                if proc:
                    try:
                        proc.kill()
                        self._active_processes.discard(proc)
                    except:
                        pass
                self._running -= 1
                
            except Exception as e:
                last_err = repr(e)
                if proc:
                    self._active_processes.discard(proc)
                self._running -= 1
            
            # 指数退避重试
            if tries <= self.retries:
                wait_time = min(2**tries, 8) + (time.time() % 1) * 0.3  # 添加抖动
                await asyncio.sleep(wait_time)
        
        # 计算执行时间
        latency_ms = int((time.time() - start) * 1000)
        
        # 更新统计
        self._done += 1
        if code != 0:
            self._failed += 1
        
        self._lat_hist.append(latency_ms)
        
        # 记录事件
        self._emit_event(cmd, code, latency_ms, tries, stdout, stderr, last_err)
        
        return ExecutionResult(cmd, code == 0, code, stdout, stderr, latency_ms, tries)
    
    def _emit_event(self, cmd: str, code: int, latency_ms: int, tries: int, 
                   stdout: str, stderr: str, error: str = None):
        """记录执行事件"""
        evt = {
            "ts": int(time.time() * 1000),
            "cmd": cmd[:100] + "..." if len(cmd) > 100 else cmd,  # 截断长命令
            "exit": code,
            "latency_ms": latency_ms,
            "tries": tries,
            "ok": code == 0
        }
        
        if error:
            evt["error"] = error
        
        if code != 0:
            evt["stderr"] = stderr[-500:] if stderr else ""  # 保留错误信息
        
        # 写入事件日志
        events_file = os.path.join(self.log_dir, "executor_events.jsonl")
        try:
            with open(events_file, "a", encoding='utf-8') as f:
                f.write(json.dumps(evt, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"写入事件日志失败: {e}")
        
        # 更新状态
        self._write_status()
        
        # 日志输出
        if code == 0:
            logger.debug(f"命令执行成功: {cmd[:50]}... ({latency_ms}ms, {tries} tries)")
        else:
            logger.warning(f"命令执行失败: {cmd[:50]}... (exit={code}, {tries} tries)")
    
    def _write_status(self):
        """写入状态文件"""
        elapsed = time.time() - self._start_time
        qps = self._done / max(elapsed, 1)
        
        status = {
            "ts": int(time.time() * 1000),
            "batch_id": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "running": self._running,
            "done": self._done,
            "failed": self._failed,
            "total_elapsed_s": int(elapsed),
            "qps": round(qps, 2),
            "avg_latency_ms": int(sum(self._lat_hist) / max(1, len(self._lat_hist))),
            "success_rate": round((self._done - self._failed) / max(1, self._done), 3)
        }
        
        status_file = os.path.join(self.log_dir, "executor_status.json")
        try:
            with open(status_file, "w", encoding='utf-8') as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"写入状态文件失败: {e}")
    
    async def execute_batch(self, commands: List[str]) -> List[ExecutionResult]:
        """并行执行命令批次"""
        if not commands:
            return []
        
        logger.info(f"开始执行 {len(commands)} 个命令...")
        
        # 重置统计
        self._running = 0
        self._done = 0
        self._failed = 0
        self._lat_hist = []
        self._start_time = time.time()
        
        # 创建并执行任务
        tasks = [asyncio.create_task(self._run_one(cmd)) for cmd in commands]
        
        try:
            results = await asyncio.gather(*tasks)
            
            # 最终统计
            success_count = sum(1 for r in results if r.ok)
            total_time = time.time() - self._start_time
            
            logger.info(f"批次执行完成: {success_count}/{len(commands)} 成功, "
                       f"总耗时 {total_time:.1f}s, "
                       f"平均 {total_time/len(commands):.1f}s/命令")
            
            return results
            
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在取消执行...")
            
            # 取消所有任务
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # 等待取消完成
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # 清理进程
            await self._cleanup_processes()
            
            raise
    
    def monitor_progress(self) -> Dict[str, Any]:
        """获取当前执行进度"""
        status_file = os.path.join(self.log_dir, "executor_status.json")
        try:
            with open(status_file, "r", encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "ts": int(time.time() * 1000),
                "running": 0,
                "done": 0,
                "failed": 0,
                "qps": 0.0,
                "avg_latency_ms": 0
            }
        except Exception as e:
            logger.error(f"读取状态文件失败: {e}")
            return {"error": str(e)}
    
    def handle_interruption(self) -> bool:
        """处理中断信号"""
        try:
            # 创建清理任务
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._cleanup_processes())
            else:
                loop.run_until_complete(self._cleanup_processes())
            
            logger.info("中断处理完成")
            return True
            
        except Exception as e:
            logger.error(f"中断处理失败: {e}")
            return False
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        events_file = os.path.join(self.log_dir, "executor_events.jsonl")
        
        summary = {
            "total_commands": 0,
            "successful": 0,
            "failed": 0,
            "avg_latency_ms": 0,
            "max_latency_ms": 0,
            "retry_rate": 0,
            "error_types": {}
        }
        
        try:
            with open(events_file, "r", encoding='utf-8') as f:
                events = [json.loads(line) for line in f if line.strip()]
            
            if not events:
                return summary
            
            summary["total_commands"] = len(events)
            summary["successful"] = sum(1 for e in events if e.get("ok", False))
            summary["failed"] = summary["total_commands"] - summary["successful"]
            
            latencies = [e.get("latency_ms", 0) for e in events]
            summary["avg_latency_ms"] = int(sum(latencies) / len(latencies))
            summary["max_latency_ms"] = max(latencies)
            
            retries = [e.get("tries", 1) for e in events]
            summary["retry_rate"] = round(sum(1 for r in retries if r > 1) / len(retries), 3)
            
            # 统计错误类型
            for event in events:
                if not event.get("ok", False) and "error" in event:
                    error_type = event["error"].split(":")[0]
                    summary["error_types"][error_type] = summary["error_types"].get(error_type, 0) + 1
            
        except Exception as e:
            logger.error(f"生成执行摘要失败: {e}")
            summary["error"] = str(e)
        
        return summary

# 便捷函数
async def run_commands(commands: List[str], **kwargs) -> List[ExecutionResult]:
    """便捷函数：执行命令列表"""
    executor = AsyncCommandExecutor(**kwargs)
    return await executor.execute_batch(commands)

async def run_command(command: str, **kwargs) -> ExecutionResult:
    """便捷函数：执行单个命令"""
    results = await run_commands([command], **kwargs)
    return results[0] if results else ExecutionResult(command, False, -1, "", "No result", 0, 0)

def main():
    """测试函数"""
    async def test():
        # 测试命令
        commands = [
            "echo 'Hello World'",
            "sleep 2 && echo 'After sleep'",
            "python -c 'print(\"Python test\")'",
            "ls -la",
            "date"
        ]
        
        executor = AsyncCommandExecutor(max_concurrent=3, timeout_s=10)
        
        print("开始测试异步命令执行...")
        results = await executor.execute_batch(commands)
        
        print(f"\n执行结果:")
        for i, result in enumerate(results):
            status = "✅" if result.ok else "❌"
            print(f"{status} 命令 {i+1}: {result.cmd[:50]}...")
            print(f"   状态: {'成功' if result.ok else '失败'} (exit={result.exit_code})")
            print(f"   耗时: {result.latency_ms}ms, 重试: {result.tries}次")
            if result.stdout:
                print(f"   输出: {result.stdout.strip()[:100]}")
            if result.stderr:
                print(f"   错误: {result.stderr.strip()[:100]}")
            print()
        
        # 显示摘要
        summary = executor.get_execution_summary()
        print("执行摘要:")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    asyncio.run(test())

if __name__ == "__main__":
    main()
