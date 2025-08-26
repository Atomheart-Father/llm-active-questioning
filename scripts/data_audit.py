#!/usr/bin/env python3
"""
数据源体检脚本 - 只读检查，快速暴露数据源失效/fallback问题
"""

import os
import json
import glob
import re
from pathlib import Path
from urllib.parse import urlparse

def scan_config_files():
    """扫描配置文件，收集数据源信息"""
    sources = []
    
    # 扫描 configs/**/*.json
    config_files = glob.glob("configs/**/*.json", recursive=True)
    for config_file in config_files:
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 递归查找数据源配置
            def extract_sources(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        if key in ["data", "dataset", "source"] and isinstance(value, dict):
                            if "name" in value or "url" in value or "path" in value:
                                sources.append({
                                    "config_file": config_file,
                                    "config_path": current_path,
                                    "name": value.get("name", "unnamed"),
                                    "url": value.get("url", ""),
                                    "path": value.get("path", ""),
                                    "type": "config"
                                })
                        elif isinstance(value, (dict, list)):
                            extract_sources(value, current_path)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        extract_sources(item, f"{path}[{i}]")
            
            extract_sources(config)
            
        except Exception as e:
            print(f"⚠️ 解析配置文件失败 {config_file}: {e}")
    
    return sources

def scan_data_directory():
    """扫描data目录，收集数据文件信息"""
    sources = []
    data_dir = Path("data")
    
    if not data_dir.exists():
        return sources
    
    # 扫描常见数据文件
    data_files = []
    for pattern in ["*.jsonl", "*.json", "*.csv", "*.txt"]:
        data_files.extend(data_dir.glob(pattern))
    
    for data_file in data_files:
        try:
            # 尝试读取第一行判断格式
            with open(data_file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line:
                    try:
                        sample = json.loads(first_line)
                        if isinstance(sample, dict):
                            sources.append({
                                "config_file": "data/",
                                "config_path": "data_file",
                                "name": data_file.name,
                                "url": sample.get("url", ""),
                                "path": str(data_file),
                                "type": "data_file"
                            })
                    except json.JSONDecodeError:
                        # 非JSON格式，记录基本信息
                        sources.append({
                            "config_file": "data/",
                            "config_path": "data_file",
                            "name": data_file.name,
                            "url": "",
                            "path": str(data_file),
                            "type": "data_file"
                        })
        except Exception as e:
            print(f"⚠️ 读取数据文件失败 {data_file}: {e}")
    
    return sources

def check_local_paths(sources):
    """检查本地路径是否存在"""
    issues = []
    
    for source in sources:
        path = source.get("path", "")
        if path and not path.startswith(("http://", "https://")):
            if not os.path.exists(path):
                issues.append(f"❌ 本地路径不存在: {path} (来自 {source['config_file']})")
                source["local_exists"] = False
            else:
                source["local_exists"] = True
        else:
            source["local_exists"] = None  # URL类型
    
    return issues

def validate_urls(sources):
    """验证URL格式"""
    issues = []
    
    for source in sources:
        url = source.get("url", "")
        if url:
            try:
                parsed = urlparse(url)
                if not parsed.scheme or not parsed.netloc:
                    issues.append(f"❌ 无效URL格式: {url} (来自 {source['config_file']})")
                    source["url_valid"] = False
                else:
                    source["url_valid"] = True
            except Exception:
                issues.append(f"❌ URL解析失败: {url} (来自 {source['config_file']})")
                source["url_valid"] = False
        else:
            source["url_valid"] = None
    
    return issues

def check_fallback_usage():
    """检查fallback使用情况"""
    fallback_stats = {}
    
    # 查找最新的shadow_eval文件
    shadow_files = glob.glob("data/shadow_eval_*.jsonl")
    if not shadow_files:
        return fallback_stats
    
    latest_file = max(shadow_files, key=os.path.getctime)
    print(f"🔍 检查fallback使用: {latest_file}")
    
    try:
        total_lines = 0
        fallback_lines = 0
        synthetic_lines = 0
        gen_lines = 0
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                total_lines += 1
                
                # 检查各种fallback标记
                if '"fallback":true' in line or '"fallback": true' in line:
                    fallback_lines += 1
                if '"source":"synthetic"' in line:
                    synthetic_lines += 1
                if '"source":"gen"' in line:
                    gen_lines += 1
        
        fallback_stats = {
            "file": latest_file,
            "total_lines": total_lines,
            "fallback_lines": fallback_lines,
            "synthetic_lines": synthetic_lines,
            "gen_lines": gen_lines,
            "fallback_pct": (fallback_lines / total_lines * 100) if total_lines > 0 else 0,
            "synthetic_pct": (synthetic_lines / total_lines * 100) if total_lines > 0 else 0,
            "gen_pct": (gen_lines / total_lines * 100) if total_lines > 0 else 0
        }
        
    except Exception as e:
        print(f"⚠️ 检查fallback失败: {e}")
    
    return fallback_stats

def main():
    """主体检流程"""
    print("🔍 数据源体检开始")
    print("=" * 50)
    
    # 1. 扫描配置和数据文件
    print("📋 扫描数据源...")
    config_sources = scan_config_files()
    data_sources = scan_data_directory()
    all_sources = config_sources + data_sources
    
    print(f"  发现 {len(all_sources)} 个数据源")
    
    # 2. 检查本地路径
    print("\n📁 检查本地路径...")
    path_issues = check_local_paths(all_sources)
    for issue in path_issues:
        print(issue)
    
    # 3. 验证URL
    print("\n🌐 验证URL格式...")
    url_issues = validate_urls(all_sources)
    for issue in url_issues:
        print(issue)
    
    # 4. 检查fallback使用
    print("\n⚠️ 检查fallback使用...")
    fallback_stats = check_fallback_usage()
    
    if fallback_stats:
        print(f"  文件: {fallback_stats['file']}")
        print(f"  总行数: {fallback_stats['total_lines']}")
        print(f"  fallback标记: {fallback_stats['fallback_lines']} ({fallback_stats['fallback_pct']:.1f}%)")
        print(f"  synthetic标记: {fallback_stats['synthetic_lines']} ({fallback_stats['synthetic_pct']:.1f}%)")
        print(f"  gen标记: {fallback_stats['gen_lines']} ({fallback_stats['gen_pct']:.1f}%)")
    
    # 5. 汇总报告
    print("\n📊 汇总报告")
    print("=" * 50)
    
    local_missing = len([s for s in all_sources if s.get("local_exists") == False])
    url_invalid = len([s for s in all_sources if s.get("url_valid") == False])
    has_fallback = fallback_stats.get("fallback_pct", 0) > 0 if fallback_stats else False
    
    print(f"本地路径缺失: {local_missing}")
    print(f"URL格式无效: {url_invalid}")
    print(f"存在fallback: {'是' if has_fallback else '否'}")
    
    # 6. 退出码判断
    if local_missing > 0 or url_invalid > 0 or has_fallback:
        print("\n❌ 体检发现问题，退出码: 1")
        return 1
    else:
        print("\n✅ 体检通过，退出码: 0")
        return 0

if __name__ == "__main__":
    exit(main())
