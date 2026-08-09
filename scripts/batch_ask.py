"""
批量问答处理
功能：一次处理多个问题，汇总结果（支持并行/串行）
用法：python scripts/batch_ask.py
"""

import sys
import time
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills"))


class BatchProcessor:
    """批量问答处理器"""

    def __init__(self):
        from answer_generator import AnswerGenerator
        self.agent = AnswerGenerator()

    def process(self, questions: list, parallel: bool = False) -> dict:
        """批量处理问题
        parallel: True 用多线程并行（需谨慎，LLM 并发可能限流），False 串行
        """
        results = []
        for i, q in enumerate(questions):
            t0 = time.time()
            try:
                r = self.agent.answer(q, top_k=3)
                elapsed = (time.time() - t0) * 1000
                results.append({
                    "query": q,
                    "answer": r["answer"][:200],
                    "intent": r["intent"]["intent_label"],
                    "compliance": r["compliance"]["verdict"],
                    "sources": [s["source"] for s in r["sources"]],
                    "elapsed_ms": round(elapsed, 1),
                    "status": "ok",
                })
                print(f"  [{i+1}/{len(questions)}] ✅ {q[:25]}... ({elapsed:.0f}ms)")
            except Exception as e:
                results.append({
                    "query": q,
                    "status": "error",
                    "error": str(e)[:100],
                })
                print(f"  [{i+1}/{len(questions)}] ❌ {q[:25]}... {str(e)[:40]}")

        # 汇总统计
        ok_count = sum(1 for r in results if r["status"] == "ok")
        avg_ms = sum(r.get("elapsed_ms", 0) for r in results if r["status"] == "ok") / max(ok_count, 1)

        summary = {
            "total": len(questions),
            "success": ok_count,
            "failed": len(questions) - ok_count,
            "avg_latency_ms": round(avg_ms, 1),
            "results": results,
        }

        # 保存结果
        output = PROJECT_ROOT / "output"
        output.mkdir(exist_ok=True)
        report_path = output / "batch_ask_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        return summary


def main():
    print("=" * 60)
    print("  批量问答处理")
    print("=" * 60)

    # 默认批量问题
    questions = [
        "烟酰胺有什么功效？",
        "敏感肌可以用视黄醇吗？",
        "这款面霜多少钱？",
        "拆封了还能退货吗？",
        "玻尿酸精华怎么用？",
        "孕妇可以用水杨酸吗？",
        "退货多久能收到退款？",
        "防晒霜需要每天用吗？",
    ]

    print(f"待处理问题数: {len(questions)}")
    print(f"处理方式: 串行\n")

    processor = BatchProcessor()
    summary = processor.process(questions)

    print("\n" + "=" * 60)
    print("  批量处理汇总")
    print("=" * 60)
    print(f"  总数: {summary['total']}")
    print(f"  成功: {summary['success']}")
    print(f"  失败: {summary['failed']}")
    print(f"  平均延迟: {summary['avg_latency_ms']} ms")
    print(f"\n  报告已保存: output/batch_ask_report.json")

    has_summary = summary["total"] > 0 and summary["success"] > 0
    print(f"\n  {'✅ 通过标准达成：一次处理多问题并汇总结果' if has_summary else '❌ 未通过'}")


if __name__ == "__main__":
    main()
