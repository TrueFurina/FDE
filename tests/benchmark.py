"""
性能基准测试：响应时间统计
功能：对一组查询测量端到端响应时间，输出平均/最大/最小延迟及分位数
用法：python tests/benchmark.py
"""

import sys
import time
import json
import statistics
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class Benchmark:
    """性能基准测试器"""

    def __init__(self):
        from answer_generator import AnswerGenerator
        self.agent = AnswerGenerator()

    def run(self, queries=None, iterations=1) -> dict:
        """运行基准测试"""
        if queries is None:
            queries = [
                "烟酰胺有什么功效？",
                "敏感肌可以用视黄醇吗？",
                "这款面霜多少钱？",
                "拆封了还能退货吗？",
                "玻尿酸精华怎么用？",
                "孕妇可以用水杨酸吗？",
                "退货多久能收到退款？",
                "防晒霜需要每天用吗？",
            ]

        latencies = []
        per_query = []

        for q in queries:
            t0 = time.time()
            try:
                result = self.agent.answer(q, top_k=3)
                elapsed_ms = (time.time() - t0) * 1000
                latencies.append(elapsed_ms)
                per_query.append({
                    "query": q,
                    "latency_ms": round(elapsed_ms, 1),
                    "intent": result["intent"]["intent_label"],
                    "has_answer": bool(result["answer"]),
                })
                print(f"  {elapsed_ms:8.1f}ms | {q[:30]}... | {result['intent']['intent_label']}")
            except Exception as e:
                print(f"  ❌ {q[:30]}... 失败: {str(e)[:50]}")
                per_query.append({"query": q, "latency_ms": -1, "error": str(e)[:50]})

        # 统计
        valid = [l for l in latencies if l > 0]
        if not valid:
            return {"error": "无有效测量"}

        valid_sorted = sorted(valid)
        stats = {
            "total_queries": len(queries),
            "success_queries": len(valid),
            "avg_ms": round(statistics.mean(valid), 1),
            "median_ms": round(statistics.median(valid), 1),
            "max_ms": round(max(valid), 1),
            "min_ms": round(min(valid), 1),
            "p90_ms": round(valid_sorted[int(len(valid_sorted) * 0.9) - 1], 1),
            "p95_ms": round(valid_sorted[int(len(valid_sorted) * 0.95) - 1], 1),
            "per_query": per_query,
        }
        return stats


def main():
    print("=" * 60)
    print("  性能基准测试（响应时间统计）")
    print("=" * 60)

    bench = Benchmark()
    stats = bench.run()

    if "error" in stats:
        print(f"\n❌ {stats['error']}")
        return

    print("\n" + "=" * 60)
    print("  延迟统计")
    print("=" * 60)
    print(f"  查询数:    {stats['total_queries']} (成功 {stats['success_queries']})")
    print(f"  平均延迟:  {stats['avg_ms']} ms")
    print(f"  中位数:    {stats['median_ms']} ms")
    print(f"  最大延迟:  {stats['max_ms']} ms")
    print(f"  最小延迟:  {stats['min_ms']} ms")
    print(f"  P90:       {stats['p90_ms']} ms")
    print(f"  P95:       {stats['p95_ms']} ms")

    # 保存报告
    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / "benchmark_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"\n  报告已保存: {report_path}")

    # 通过标准验证
    has_stats = all(k in stats for k in ("avg_ms", "max_ms", "min_ms"))
    print(f"\n  {'✅ 通过标准达成：输出平均/最大/最小延迟' if has_stats else '❌ 未通过'}")


if __name__ == "__main__":
    main()
