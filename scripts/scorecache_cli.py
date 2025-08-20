#!/usr/bin/env python3
"""
Score Cache CLI - 缓存管理命令行工具
基于GPT-5指导实现的缓存管理工具
"""

import argparse
import json
import sqlite3
import time
import sys
import os
from pathlib import Path
from typing import Dict, List, Any
import logging

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

class ScoreCacheCLI:
    """评分缓存CLI管理器"""
    
    def __init__(self, db_path: str = "gemini_cache.sqlite"):
        self.db_path = db_path
        if not os.path.exists(db_path):
            print(f"⚠️  缓存数据库不存在: {db_path}")
            print("请先运行评分系统创建缓存数据库")
            sys.exit(1)
    
    def get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def stat(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            
            # 基础统计
            cur.execute("SELECT COUNT(*) FROM gemini_score_cache")
            total_entries = cur.fetchone()[0]
            
            # 有效缓存统计
            now = int(time.time() * 1000)
            cur.execute("SELECT COUNT(*) FROM gemini_score_cache WHERE expiry_at > ?", (now,))
            valid_entries = cur.fetchone()[0]
            
            # 状态统计
            cur.execute("""
                SELECT status, COUNT(*) 
                FROM gemini_score_cache 
                GROUP BY status
            """)
            status_counts = dict(cur.fetchall())
            
            # 延迟统计
            cur.execute("""
                SELECT AVG(api_latency_ms), MAX(api_latency_ms), MIN(api_latency_ms)
                FROM gemini_score_cache 
                WHERE api_latency_ms > 0
            """)
            latency_stats = cur.fetchone()
            
            # 方差统计
            cur.execute("""
                SELECT AVG(variance), MAX(variance), 
                       COUNT(CASE WHEN variance > 0.08 THEN 1 END)
                FROM gemini_score_cache 
                WHERE variance IS NOT NULL
            """)
            variance_stats = cur.fetchone()
            
            # TTL即将过期统计
            hour_from_now = now + (60 * 60 * 1000)
            cur.execute("""
                SELECT COUNT(*) FROM gemini_score_cache 
                WHERE expiry_at > ? AND expiry_at < ?
            """, (now, hour_from_now))
            expiring_soon = cur.fetchone()[0]
            
            # 模型/版本分布
            cur.execute("""
                SELECT scoring_spec, COUNT(*) 
                FROM gemini_score_cache 
                GROUP BY scoring_spec 
                ORDER BY COUNT(*) DESC
                LIMIT 10
            """)
            spec_distribution = cur.fetchall()
            
            return {
                "database_info": {
                    "db_path": self.db_path,
                    "db_size_mb": round(os.path.getsize(self.db_path) / (1024*1024), 2),
                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                },
                "cache_stats": {
                    "total_entries": total_entries,
                    "valid_entries": valid_entries,
                    "expired_entries": total_entries - valid_entries,
                    "hit_rate": round(valid_entries / max(1, total_entries), 3),
                    "expiring_in_1h": expiring_soon
                },
                "status_distribution": status_counts,
                "performance_stats": {
                    "avg_latency_ms": round(latency_stats[0] or 0, 1),
                    "max_latency_ms": latency_stats[1] or 0,
                    "min_latency_ms": latency_stats[2] or 0
                },
                "variance_stats": {
                    "avg_variance": round(variance_stats[0] or 0, 4),
                    "max_variance": round(variance_stats[1] or 0, 4),
                    "unstable_count": variance_stats[2] or 0,
                    "unstable_rate": round((variance_stats[2] or 0) / max(1, total_entries), 3)
                },
                "spec_distribution": [
                    {"spec": spec, "count": count} 
                    for spec, count in spec_distribution
                ]
            }
    
    def invalidate(self, spec_pattern: str = None, model: str = None, 
                  version: str = None, dims: str = None) -> int:
        """失效缓存项"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            
            if spec_pattern:
                # 直接按模式失效
                cur.execute("""
                    UPDATE gemini_score_cache 
                    SET expiry_at = 0 
                    WHERE scoring_spec LIKE ?
                """, (f"%{spec_pattern}%",))
                
            else:
                # 构建具体的模式
                patterns = []
                if model:
                    patterns.append(f"{model}|%")
                if version:
                    patterns.append(f"%|v={version}|%")
                if dims:
                    patterns.append(f"%|dims={dims}")
                
                if not patterns:
                    print("❌ 请提供至少一个失效条件")
                    return 0
                
                # 执行失效
                total_invalidated = 0
                for pattern in patterns:
                    cur.execute("""
                        UPDATE gemini_score_cache 
                        SET expiry_at = 0 
                        WHERE scoring_spec LIKE ?
                    """, (pattern,))
                    total_invalidated += cur.rowcount
            
            conn.commit()
            invalidated_count = cur.rowcount if spec_pattern else total_invalidated
            
            print(f"✅ 已失效 {invalidated_count} 个缓存项")
            return invalidated_count
    
    def replay_bad(self, reason: str = "unstable", limit: int = 100) -> List[Dict[str, Any]]:
        """重放问题样本"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            
            if reason == "unstable":
                # 查找高方差样本
                cur.execute("""
                    SELECT key, payload_norm, scoring_spec, variance, api_latency_ms
                    FROM gemini_score_cache
                    WHERE variance > 0.08
                    ORDER BY variance DESC
                    LIMIT ?
                """, (limit,))
                
            elif reason == "high_latency":
                # 查找高延迟样本
                cur.execute("""
                    SELECT key, payload_norm, scoring_spec, variance, api_latency_ms
                    FROM gemini_score_cache
                    WHERE api_latency_ms > 5000
                    ORDER BY api_latency_ms DESC
                    LIMIT ?
                """, (limit,))
                
            elif reason == "error":
                # 查找错误样本
                cur.execute("""
                    SELECT key, payload_norm, scoring_spec, variance, api_latency_ms
                    FROM gemini_score_cache
                    WHERE status = 'error'
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (limit,))
                
            else:
                print(f"❌ 不支持的原因: {reason}")
                print("支持的原因: unstable, high_latency, error")
                return []
            
            results = cur.fetchall()
            
            bad_samples = []
            for row in results:
                key, payload_norm, scoring_spec, variance, latency = row
                
                try:
                    payload = json.loads(payload_norm)
                    bad_samples.append({
                        "cache_key": key,
                        "dialogue": payload,
                        "scoring_spec": scoring_spec,
                        "variance": variance,
                        "latency_ms": latency,
                        "reason": reason
                    })
                except json.JSONDecodeError:
                    continue
            
            print(f"📋 找到 {len(bad_samples)} 个问题样本 (原因: {reason})")
            return bad_samples
    
    def cleanup_expired(self) -> int:
        """清理过期缓存"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            
            now = int(time.time() * 1000)
            cur.execute("""
                DELETE FROM gemini_score_cache 
                WHERE expiry_at > 0 AND expiry_at < ?
            """, (now,))
            
            deleted_count = cur.rowcount
            conn.commit()
            
            print(f"🗑️  清理了 {deleted_count} 个过期缓存项")
            return deleted_count
    
    def export_cache(self, output_file: str, spec_filter: str = None) -> int:
        """导出缓存数据"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            
            if spec_filter:
                cur.execute("""
                    SELECT * FROM gemini_score_cache 
                    WHERE scoring_spec LIKE ?
                    ORDER BY created_at
                """, (f"%{spec_filter}%",))
            else:
                cur.execute("""
                    SELECT * FROM gemini_score_cache 
                    ORDER BY created_at
                """)
            
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            
            # 转换为JSON格式
            export_data = []
            for row in rows:
                record = dict(zip(columns, row))
                
                # 解析JSON字段
                try:
                    record["payload_norm"] = json.loads(record["payload_norm"])
                    record["score_json"] = json.loads(record["score_json"])
                except json.JSONDecodeError:
                    pass
                
                export_data.append(record)
            
            # 保存文件
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            print(f"📤 导出了 {len(export_data)} 条缓存记录到: {output_file}")
            return len(export_data)
    
    def backup_database(self, backup_path: str = None) -> str:
        """备份数据库"""
        if not backup_path:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = f"backup/gemini_cache_backup_{timestamp}.sqlite"
        
        Path(backup_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 使用SQLite的备份API
        with self.get_connection() as source:
            with sqlite3.connect(backup_path) as backup:
                source.backup(backup)
        
        backup_size = os.path.getsize(backup_path)
        print(f"💾 数据库已备份到: {backup_path} ({backup_size} bytes)")
        return backup_path

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Score Cache CLI - 评分缓存管理工具")
    parser.add_argument("--db", default="gemini_cache.sqlite", help="缓存数据库路径")
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # stat命令
    stat_parser = subparsers.add_parser("stat", help="显示缓存统计信息")
    stat_parser.add_argument("--json", action="store_true", help="以JSON格式输出")
    
    # invalidate命令
    invalidate_parser = subparsers.add_parser("invalidate", help="失效缓存项")
    invalidate_parser.add_argument("--spec", help="按规范模式失效")
    invalidate_parser.add_argument("--model", help="按模型名失效")
    invalidate_parser.add_argument("--version", help="按版本失效")
    invalidate_parser.add_argument("--dims", help="按维度失效")
    
    # replay-bad命令
    replay_parser = subparsers.add_parser("replay-bad", help="重放问题样本")
    replay_parser.add_argument("--reason", choices=["unstable", "high_latency", "error"], 
                              default="unstable", help="问题原因")
    replay_parser.add_argument("--limit", type=int, default=100, help="最大样本数")
    replay_parser.add_argument("--output", help="保存到文件")
    
    # cleanup命令
    cleanup_parser = subparsers.add_parser("cleanup", help="清理过期缓存")
    
    # export命令
    export_parser = subparsers.add_parser("export", help="导出缓存数据")
    export_parser.add_argument("output_file", help="输出文件路径")
    export_parser.add_argument("--filter", help="规范过滤条件")
    
    # backup命令
    backup_parser = subparsers.add_parser("backup", help="备份数据库")
    backup_parser.add_argument("--output", help="备份文件路径")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 创建CLI实例
    cli = ScoreCacheCLI(args.db)
    
    try:
        if args.command == "stat":
            stats = cli.stat()
            if args.json:
                print(json.dumps(stats, indent=2, ensure_ascii=False))
            else:
                print("📊 缓存统计信息")
                print("=" * 50)
                print(f"📁 数据库: {stats['database_info']['db_path']} ({stats['database_info']['db_size_mb']}MB)")
                print(f"📈 总条目: {stats['cache_stats']['total_entries']}")
                print(f"✅ 有效条目: {stats['cache_stats']['valid_entries']}")
                print(f"⏰ 即将过期: {stats['cache_stats']['expiring_in_1h']}")
                print(f"🎯 命中率: {stats['cache_stats']['hit_rate']}")
                print(f"⚡ 平均延迟: {stats['performance_stats']['avg_latency_ms']}ms")
                print(f"📊 不稳定样本: {stats['variance_stats']['unstable_count']} ({stats['variance_stats']['unstable_rate']})")
        
        elif args.command == "invalidate":
            cli.invalidate(args.spec, args.model, args.version, args.dims)
        
        elif args.command == "replay-bad":
            bad_samples = cli.replay_bad(args.reason, args.limit)
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(bad_samples, f, ensure_ascii=False, indent=2)
                print(f"💾 问题样本已保存到: {args.output}")
            else:
                for i, sample in enumerate(bad_samples[:5]):  # 只显示前5个
                    print(f"\n样本 {i+1}:")
                    print(f"  原因: {sample['reason']}")
                    print(f"  方差: {sample['variance']}")
                    print(f"  延迟: {sample['latency_ms']}ms")
        
        elif args.command == "cleanup":
            cli.cleanup_expired()
        
        elif args.command == "export":
            cli.export_cache(args.output_file, args.filter)
        
        elif args.command == "backup":
            cli.backup_database(args.output)
    
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
