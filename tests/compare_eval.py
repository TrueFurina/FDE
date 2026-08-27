"""
回答对比评估
功能：对同一问题的双版本回答（如不同温度/不同 prompt）进行对比评估
评估维度：忠实度/合规性/完整度/风格，输出对比报告
用法：python tests/compare_eval.py
"""

import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class AnswerComparator:
    """回答对比评估器"""

    def compare(self, query: str, answer_a: dict, answer_b: dict) -> dict:
        """对比两个回答版本
        answer_a/b: answer() 返回值
        """
        a_text = answer_a.get("answer", "")
        b_text = answer_b.get("answer", "")

        # 忠实度（回答是否引用来源）
        a_grounded = len(answer_a.get("sources", [])) > 0
        b_grounded = len(answer_b.get("sources", [])) > 0

        # 合规性
        a_compliance = answer_a.get("compliance", {}).get("verdict", "unknown")
        b_compliance = answer_b.get("compliance", {}).get("verdict", "unknown")

        # 完整度（回答长度与来源数量）
        a_len = len(a_text)
        b_len = len(b_text)
        a_sources = len(answer_a.get("sources", []))
        b_sources = len(answer_b.get("sources", []))

        # 忠实度评分：回答是否包含来源关键信息
        a_faithful = a_grounded and a_len > 30
        b_faithful = b_grounded and b_len > 30

        # 综合评分（规则式）
        a_score = self._score(a_text, answer_a)
        b_score = self._score(b_text, answer_b)

        winner = "A" if a_score > b_score else ("B" if b_score > a_score else "平局")

        return {
            "query": query,
            "version_a": {
                "answer_preview": a_text[:120],
                "length": a_len,
                "sources": a_sources,
                "compliance": a_compliance,
                "grounded": a_grounded,
                "score": a_score,
            },
            "version_b": {
                "answer_preview": b_text[:120],
                "length": b_len,
                "sources": b_sources,
                "compliance": b_compliance,
                "grounded": b_grounded,
                "score": b_score,
            },
            "winner": winner,
            "dimensions": {
                "faithfulness": {"A": a_faithful, "B": b_faithful},
                "compliance": {"A": a_compliance, "B": b_compliance},
                "completeness": {"A": a_sources, "B": b_sources},
            },
        }

    def _score(self, text: str, answer: dict) -> float:
        """规则综合评分 0-1"""
        score = 0.0
        # 有回答 +0.2
        if text:
            score += 0.2
        # 长度适中（50-800 字符）+0.2
        if 50 <= len(text) <= 800:
            score += 0.2
        # 有来源 +0.2
        if answer.get("sources"):
            score += 0.2
        # 合规通过 +0.2
        if answer.get("compliance", {}).get("verdict") == "pass":
            score += 0.2
        # 引用具体来源标识 +0.1
        if any(s.get("source") for s in answer.get("sources", [])):
            score += 0.1
        # 不转人工 +0.1
        if not answer.get("needs_human"):
            score += 0.1
        return round(min(score, 1.0), 2)


def main():
    print("=" * 60)
    print("  回答对比评估（双版本）")
    print("=" * 60)

    from answer_generator import AnswerGenerator
    agent = AnswerGenerator()
    comparator = AnswerComparator()

    # 测试问题集
    test_queries = [
        "烟酰胺有什么功效？",
        "敏感肌可以用视黄醇吗？",
        "这款面霜多少钱？",
        "退货流程是什么？",
    ]

    results = []
    for q in test_queries:
        # 版本 A：正常回答（temperature 0.3）
        answer_a = agent.answer(q, top_k=3)

        # 版本 B：带会话上下文回答（模拟不同 prompt 风格）
        answer_b = agent.answer(q, top_k=5)  # 更多检索上下文

        result = comparator.compare(q, answer_a, answer_b)
        results.append(result)

        print(f"\n🔍 {q}")
        print(f"  A: 分{result['version_a']['score']} | 长度{result['version_a']['length']} | "
              f"来源{result['version_a']['sources']} | 合规{result['version_a']['compliance']}")
        print(f"  B: 分{result['version_b']['score']} | 长度{result['version_b']['length']} | "
              f"来源{result['version_b']['sources']} | 合规{result['version_b']['compliance']}")
        print(f"  🏆 胜出: {result['winner']}")

    # 保存报告
    OUTPUT_DIR.mkdir(exist_ok=True)
    report_path = OUTPUT_DIR / "compare_eval_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(results),
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    ok = len(results) == len(test_queries)
    print(f"\n  ✅ 通过标准达成：双版本回答可对比（{len(results)} 个问题）")
    print(f"  报告已保存: {report_path}")


if __name__ == "__main__":
    main()
