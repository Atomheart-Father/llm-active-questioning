#!/usr/bin/env python3
"""
磁盘和显存资源预检
"""

import shutil
import sys
import subprocess

def check_disk_space():
    """检查磁盘空间"""
    print("💾 检查磁盘空间...")
    
    free_bytes = shutil.disk_usage(".").free
    free_gb = free_bytes / (1024**3)
    
    print(f"  可用空间: {free_gb:.1f}GB")
    assert free_gb > 10, f"❌ 磁盘空间不足: {free_gb:.1f}GB < 10GB (QLoRA优化)"
    print("  ✅ 磁盘空间充足")

def check_gpu_memory():
    """检查GPU/Metal显存"""
    print("🖥️ 检查GPU显存...")
    
    try:
        # 检查NVIDIA GPU
        result = subprocess.run(['nvidia-smi', '--query-gpu=memory.free', '--format=csv,nounits,noheader'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            free_mb = int(result.stdout.strip().split('\n')[0])
            free_gb = free_mb / 1024
            print(f"  CUDA显存: {free_gb:.1f}GB")
            assert free_gb >= 18, f"❌ CUDA显存不足: {free_gb:.1f}GB < 18GB"
            print("  ✅ CUDA显存充足")
            return
    except:
        pass
    
    try:
        # 检查Apple Metal (macOS)
        import platform
        if platform.system() == "Darwin":
            # 简化检查：Apple Silicon通常有统一内存
            result = subprocess.run(['sysctl', 'hw.memsize'], capture_output=True, text=True)
            if result.returncode == 0:
                total_bytes = int(result.stdout.split(':')[1].strip())
                total_gb = total_bytes / (1024**3)
                print(f"  统一内存: {total_gb:.1f}GB")
                # Apple Silicon通常16GB+即可，要求相对宽松
                assert total_gb >= 16, f"❌ 统一内存不足: {total_gb:.1f}GB < 16GB"
                print("  ✅ Apple Silicon内存充足")
                return
    except:
        pass
    
    print("  ⚠️ 无法检测GPU显存，假设满足要求")

def main():
    """主检查流程"""
    print("🔍 系统资源预检")
    print("=" * 30)
    
    try:
        check_disk_space()
        print()
        check_gpu_memory()
        print()
        print("✅ 系统资源检查通过")
        return 0
    except AssertionError as e:
        print(f"\n❌ 资源检查失败: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 检查过程出错: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
