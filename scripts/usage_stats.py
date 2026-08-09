"""
知识库使用统计
功能：统计查询日志中的热门查询/高频成分/高频意图，输出热门查询排行
数据源：output/system.log（日志系统）+ output/request_trace.json（请求追踪）
输出：output/usage_stats.json
"""

import sys
import json
import time
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
sys.path.insert(0, str(PROJECT_ROOT / "skills"))


class UsageStats:
    """知识库使用统计器"""

    def collect_from_logs(self) -> dict:
        """从日志系统收集查询统计"""
        from logger import SystemLogger
        logger = SystemLogger()
        logs = logger.query_logs(log_type="query", limit=200)

        queries = []
        intents = []
        for log in logs:
            data = log.get("data", {})
            if data.get("type") == "query":
                queries.append(data.get("query", ""))
                intents.append(data.get("intent", "unknown"))

        # 热门查询排行
        query_counter = Counter(queries)
        # 高频意图
        intent_counter = Counter(intents)

        return {
            "total_queries": len(queries),
            "unique_queries": len(query_counter),
            "top_queries": query_counter.most_common(10),
            "intent_distribution": dict(intent_counter.most_common()),
        }

    def collect_from_trace(self) -> dict:
        """从请求追踪收集统计"""
        trace_file = OUTPUT_DIR / "request_trace.json"
        if not trace_file.exists():
            return {"total_requests": 0}

        try:
            traces = json.load(open(trace_file, encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {"total_requests": 0}

        paths = Counter(t.get("path", "") for t in traces)
        statuses = Counter(t.get("status_code", 0) for t in traces)
        durations = [t.get("duration_ms", 0) for t in traces]

        return {
            "total_requests": len(traces),
            "path_distribution": dict(paths.most_common()),
            "status_distribution": {str(k): v for k, v in statuses.most_common()},
            "avg_duration_ms": round(sum(durations) / len(durations), 1) if durations else 0,
        }

    def generate_report(self) -> dict:
        """生成使用统计报告"""
        print("=" * 60)
        print("  知识库使用统计")
        print("=" * 60)

        log_stats = self.collect_from_logs()
        trace_stats = self.collect_from_trace()

        report = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "queries": log_stats,
            "requests": trace_stats,
        }

        # 输出热门查询排行
        print(f"\n📊 查询统计:")
        print(f"  总查询: {log_stats.get('total_queries', 0)} | 去重: {log_stats.get('unique_queries', 0)}")

        print(f"\n🔥 热门查询排行 Top{min(5, len(log_stats.get('top_queries', [])))}:")
        for i, (q, count) in enumerate(log_stats.get("top_queries", [])[:5], 1):
            print(f"  {i}. [{count}次] {q[:40]}")

        print(f"\n🎯 意图分布:")
        for intent, count in log_stats.get("intent_distribution", {}).items():
            print(f"  {intent}: {count}次")

        if trace_stats.get("total_requests", 0) > 0:
            print(f"\n🌐 请求统计:")
            print(f"  总请求: {trace_stats['total_requests']} | 平均耗时: {trace_stats.get('avg_duration_ms', 0)}ms")

        # 保存报告
        OUTPUT_DIR.mkdir(exist_ok=True)
        report_path = OUTPUT_DIR / "usage_stats.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  报告已保存: {report_path}")

        return report


def main():
    stats = UsageStats()
    report = stats.generate_report()

    has_top = len(report.get("queries", {}).get("top_queries", [])) > 0
    print(f"\n  {'✅ 通过标准达成：输出热门查询排行' if has_top else '❌ 暂无查询数据（需先产生查询日志）'}")


if __name__ == "__main__":
    main()
