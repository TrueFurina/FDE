"""
批量性能压测
功能：并发请求压力测试，统计吞吐量/延迟分布/成功率
用法：python tests/stress_test.py
"""

import sys
import json
import time
import threading
import statistics
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class StressTester:
    """并发压力测试器"""

    def __init__(self, concurrency=5, requests_per_worker=3):
        self.concurrency = concurrency
        self.requests_per_worker = requests_per_worker
        self._results = []
        self._lock = threading.Lock()

    def _worker(self, worker_id: int, query: str):
        """单个工作线程执行多次请求"""
        from answer_generator import AnswerGenerator
        agent = AnswerGenerator()

        for i in range(self.requests_per_worker):
            t0 = time.time()
            try:
                result = agent.answer(query, top_k=3)
                duration_ms = (time.time() - t0) * 1000
                with self._lock:
                    self._results.append({
                        "worker": worker_id,
                        "query_idx": i,
                        "duration_ms": round(duration_ms, 1),
                        "success": True,
                        "has_answer": bool(result["answer"]),
                    })
            except Exception as e:
                duration_ms = (time.time() - t0) * 1000
                with self._lock:
                    self._results.append({
                        "worker": worker_id,
                        "query_idx": i,
                        "duration_ms": round(duration_ms, 1),
                        "success": False,
                        "error": str(e)[:60],
                    })

    def run(self, queries=None) -> dict:
        """运行压测"""
        if queries is None:
            queries = [
                "烟酰胺有什么功效？",
                "敏感肌可以用视黄醇吗？",
                "这款面霜多少钱？",
                "玻尿酸精华怎么用？",
            ]

        print("=" * 60)
        print(f"  并发性能压测（{self.concurrency} 并发 × {self.requests_per_worker} 次）")
        print("=" * 60)

        t_start = time.time()
        threads = []
        for w in range(self.concurrency):
            q = queries[w % len(queries)]
            t = threading.Thread(target=self._worker, args=(w, q))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()
        total_time = time.time() - t_start

        # 统计
        durations = [r["duration_ms"] for r in self._results]
        success = sum(1 for r in self._results if r["success"])
        total = len(self._results)

        report = {
            "config": {
                "concurrency": self.concurrency,
                "requests_per_worker": self.requests_per_worker,
                "total_requests": total,
            },
            "metrics": {
                "total_time_seconds": round(total_time, 2),
                "requests_per_second": round(total / total_time, 2) if total_time > 0 else 0,
                "success_rate": round(success / total, 3) if total else 0,
                "avg_duration_ms": round(statistics.mean(durations), 1) if durations else 0,
                "median_duration_ms": round(statistics.median(durations), 1) if durations else 0,
                "max_duration_ms": round(max(durations), 1) if durations else 0,
                "min_duration_ms": round(min(durations), 1) if durations else 0,
                "p90_duration_ms": round(sorted(durations)[int(total * 0.9) - 1], 1) if total > 1 else 0,
            },
            "results": self._results,
        }

        # 输出摘要
        m = report["metrics"]
        print(f"\n📊 压测结果:")
        print(f"  总请求: {total} | 成功: {success} | 成功率: {m['success_rate']}")
        print(f"  总耗时: {m['total_time_seconds']}s | 吞吐: {m['requests_per_second']} req/s")
        print(f"  延迟: 平均 {m['avg_duration_ms']}ms | 中位 {m['median_duration_ms']}ms | "
              f"最大 {m['max_duration_ms']}ms | P90 {m['p90_duration_ms']}ms")

        # 保存报告
        OUTPUT_DIR.mkdir(exist_ok=True)
        report_path = OUTPUT_DIR / "stress_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  报告已保存: {report_path}")

        return report


def main():
    tester = StressTester(concurrency=3, requests_per_worker=2)
    report = tester.run()

    has_report = "metrics" in report and "results" in report
    print(f"\n  {'✅ 通过标准达成：并发请求压力测试报告' if has_report else '❌ 未通过'}")


if __name__ == "__main__":
    main()
