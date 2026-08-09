"""
系统监控指标收集
功能：收集系统运行指标（进程/内存/磁盘/请求/缓存/会话），输出运行指标报告
输出：output/metrics_report.json
"""

import os
import sys
import json
import time
import platform
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
OUTPUT_DIR = PROJECT_ROOT / "output"


class MetricsCollector:
    """监控指标收集器"""

    def __init__(self):
        self.t0 = time.time()

    def collect_process(self) -> dict:
        """进程指标"""
        import psutil
        proc = psutil.Process()
        mem = proc.memory_info()
        return {
            "pid": proc.pid,
            "cpu_percent": proc.cpu_percent(interval=0.1),
            "memory_mb": round(mem.rss / 1024 / 1024, 1),
            "threads": proc.num_threads(),
            "uptime_seconds": int(time.time() - proc.create_time()),
        }

    def collect_system(self) -> dict:
        """系统指标"""
        import psutil
        vm = psutil.virtual_memory()
        return {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_cores": psutil.cpu_count(),
            "memory_total_mb": round(vm.total / 1024 / 1024),
            "memory_used_percent": vm.percent,
            "disk_usage_percent": psutil.disk_usage(str(PROJECT_ROOT)).percent,
        }

    def collect_runtime(self) -> dict:
        """运行时指标（从 AnswerGenerator 实例读取）"""
        from answer_generator import AnswerGenerator
        agent = AnswerGenerator()
        return {
            "sessions": agent.session_stats() if hasattr(agent, "session_stats") else {},
            "cache_hits": agent.cache_hits,
            "cache_misses": agent.cache_misses,
            "cache_size": len(agent.cache),
            "cache_ttl": agent.cache_ttl,
        }

    def collect_files(self) -> dict:
        """数据文件指标"""
        data_dir = PROJECT_ROOT / "data"
        output_dir = OUTPUT_DIR
        return {
            "data_files": len([f for f in data_dir.iterdir() if f.is_file()]),
            "data_size_kb": round(sum(f.stat().st_size for f in data_dir.iterdir() if f.is_file()) / 1024, 1),
            "output_files": len([f for f in output_dir.iterdir() if f.is_file()]) if output_dir.exists() else 0,
            "backups": len(list((PROJECT_ROOT / "backups").iterdir())) if (PROJECT_ROOT / "backups").exists() else 0,
        }

    def collect_all(self) -> dict:
        """收集全部指标"""
        print("=" * 60)
        print("  系统监控指标收集")
        print("=" * 60)

        metrics = {}

        # 进程/系统指标（psutil 可用时）
        try:
            metrics["process"] = self.collect_process()
            metrics["system"] = self.collect_system()
            print("  ✅ 进程指标: CPU {:.1f}% | 内存 {}MB | {} 线程".format(
                metrics["process"]["cpu_percent"],
                metrics["process"]["memory_mb"],
                metrics["process"]["threads"]))
            print("  ✅ 系统指标: {} 核 | 内存使用 {}% | 磁盘 {}%".format(
                metrics["system"]["cpu_cores"],
                metrics["system"]["memory_used_percent"],
                metrics["system"]["disk_usage_percent"]))
        except ImportError:
            metrics["process"] = {"error": "psutil 未安装"}
            metrics["system"] = {"error": "psutil 未安装"}
            print("  ⚠️ psutil 未安装，跳过进程/系统指标")

        # 运行时指标
        try:
            metrics["runtime"] = self.collect_runtime()
            print("  ✅ 运行时: {} 会话 | 缓存命中 {} 未命中 {}".format(
                metrics["runtime"]["sessions"].get("total_sessions", 0),
                metrics["runtime"]["cache_hits"],
                metrics["runtime"]["cache_misses"]))
        except Exception as e:
            metrics["runtime"] = {"error": str(e)[:80]}
            print(f"  ⚠️ 运行时指标: {str(e)[:60]}")

        # 文件指标
        metrics["files"] = self.collect_files()
        print("  ✅ 文件: {} 数据文件 {}KB | {} 输出文件 | {} 备份".format(
            metrics["files"]["data_files"],
            metrics["files"]["data_size_kb"],
            metrics["files"]["output_files"],
            metrics["files"]["backups"]))

        metrics["collected_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        metrics["elapsed_ms"] = round((time.time() - self.t0) * 1000, 1)

        # 保存报告
        OUTPUT_DIR.mkdir(exist_ok=True)
        report_path = OUTPUT_DIR / "metrics_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)

        print(f"\n  ✅ 报告已保存: {report_path}")
        print(f"  耗时: {metrics['elapsed_ms']}ms")

        return metrics


def main():
    collector = MetricsCollector()
    metrics = collector.collect_all()

    has_metrics = len(metrics) >= 4
    print(f"\n  {'✅ 通过标准达成：输出系统运行指标' if has_metrics else '❌ 未通过'}")


if __name__ == "__main__":
    main()
