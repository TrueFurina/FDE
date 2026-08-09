"""
回答多样性增强
功能：同一问题不同问法（同义词/口语化/简称）均能获得回答
策略：查询归一化 + 同义词扩展 + 多问法验证
集成：AnswerGenerator.answer() 前做查询扩展
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class AnswerDiversity:
    """回答多样性增强器"""

    def __init__(self):
        from synonym_expander import SynonymExpander
        self.expander = SynonymExpander()

    def expand_queries(self, query: str) -> list:
        """生成同一问题的不同问法（变体列表）"""
        variants = []
        # 1. 原查询
        variants.append(query)
        # 2. 同义词扩展变体
        for v in self.expander.expand_for_search(query):
            if v != query and v not in variants:
                variants.append(v)
        return variants[:5]

    def answer_all_variants(self, agent, query: str, top_k: int = 3) -> dict:
        """用所有变体提问，验证每个都有回答"""
        variants = self.expand_queries(query)
        results = []

        for variant in variants:
            try:
                r = agent.answer(variant, top_k=top_k)
                results.append({
                    "variant": variant,
                    "has_answer": bool(r["answer"]),
                    "answer_preview": r["answer"][:60],
                    "compliance": r["compliance"]["verdict"],
                })
            except Exception as e:
                results.append({
                    "variant": variant,
                    "has_answer": False,
                    "error": str(e)[:60],
                })

        answered = sum(1 for r in results if r["has_answer"])
        return {
            "query": query,
            "variants": len(variants),
            "answered": answered,
            "all_answered": answered == len(variants),
            "results": results,
        }


def main():
    print("=" * 60)
    print("  回答多样性增强 - 测试")
    print("=" * 60)

    from answer_generator import AnswerGenerator
    agent = AnswerGenerator()
    diversity = AnswerDiversity()

    # 同一问题的不同问法
    test_queries = [
        "玻尿酸有什么功效？",
        "烟酰胺能控油吗？",
        "面霜怎么用？",
        "敏感肌可以用视黄醇吗？",
        "退货流程是什么？",
    ]

    all_ok = True
    for q in test_queries:
        variants = diversity.expand_queries(q)
        print(f"\n🔍 问题: {q}")
        print(f"   问法变体: {variants}")

        result = diversity.answer_all_variants(agent, q)
        ok = result["all_answered"]
        all_ok = all_ok and ok
        print(f"   回答覆盖: {result['answered']}/{result['variants']} {'✅' if ok else '❌'}")
        for r in result["results"]:
            print(f"     - [{r['variant'][:25]}] {'有回答' if r['has_answer'] else '无回答'}: {r.get('answer_preview','')[:30]}")

    print("\n" + "=" * 60)
    print(f"  {'✅ 通过标准达成：同一问题不同问法均有回答' if all_ok else '❌ 有问法无回答'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
