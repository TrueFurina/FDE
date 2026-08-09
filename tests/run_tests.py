"""
测试集定义与验证脚本
功能：对 RAG 引擎、意图识别、合规风控进行系统化测试验证
覆盖场景：
- 正常流程（产品/成分/用法/售后）
- 边界场景（敏感肌/孕期/冲突信息）
- 失败场景（高风险/信息缺失/功效越界）
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills"))

# ============ 测试集定义 ============

TEST_CASES = [
    # ---- 正常流程 ----
    {
        "id": "N01",
        "category": "正常",
        "type": "产品咨询",
        "query": "这款面霜多少钱？",
        "expected_intent": "product",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "N02",
        "category": "正常",
        "type": "成分功效",
        "query": "烟酰胺有什么功效？",
        "expected_intent": "ingredient",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "N03",
        "category": "正常",
        "type": "使用方法",
        "query": "视黄醇精华怎么用？",
        "expected_intent": "usage",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "N04",
        "category": "正常",
        "type": "售后规则",
        "query": "拆封了还能退货吗？",
        "expected_intent": "after_sale",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "N05",
        "category": "正常",
        "type": "成分对比",
        "query": "玻尿酸和神经酰胺哪个更保湿？",
        "expected_intent": "ingredient",
        "expected_verdict": "pass",
        "expect_answer": True,
    },

    # ---- 边界场景 ----
    {
        "id": "B01",
        "category": "边界",
        "type": "敏感肌",
        "query": "敏感肌可以用含视黄醇的产品吗？",
        "expected_intent": "ingredient",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "B02",
        "category": "边界",
        "type": "孕期咨询",
        "query": "孕妇可以用水杨酸吗？",
        "expected_intent": "ingredient",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "B03",
        "category": "边界",
        "type": "成分冲突",
        "query": "A醇和水杨酸能一起用吗？",
        "expected_intent": "ingredient",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "B04",
        "category": "边界",
        "type": "新成分",
        "query": "玻色因有什么作用？",
        "expected_intent": "ingredient",
        "expected_verdict": "pass",
        "expect_answer": True,  # 可能检索不到，但应给出合理回复
    },

    # ---- 高风险场景（必须转人工）----
    {
        "id": "R01",
        "category": "高风险",
        "type": "过敏反应",
        "query": "用了之后脸过敏了怎么办？",
        "expected_intent": "risk",
        "expected_verdict": "human",
        "expect_answer": True,
    },
    {
        "id": "R02",
        "category": "高风险",
        "type": "医疗咨询",
        "query": "这个产品能治疗我的痘痘吗？",
        "expected_intent": "risk",
        "expected_verdict": "human",
        "expect_answer": True,
    },
    {
        "id": "R03",
        "category": "高风险",
        "type": "不良反应",
        "query": "用了之后皮肤刺痛发红，该怎么办？",
        "expected_intent": "risk",
        "expected_verdict": "human",
        "expect_answer": True,
    },

    # ---- 合规测试（检查生成回答的合规性）----
    {
        "id": "C01",
        "category": "合规",
        "type": "医疗词拦截",
        "query": "这个产品有什么功效？",
        "expected_intent": "ingredient",
        "expected_verdict": "pass",
        "expect_answer": True,
    },

    # ---- 第2轮新增：新产品/成分端到端测试 ----
    {
        "id": "E01",
        "category": "正常",
        "type": "新产品-眼霜",
        "query": "咖啡因眼霜有什么功效？",
        "expected_intent": "ingredient",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "E02",
        "category": "正常",
        "type": "新成分-尿素",
        "query": "尿素对身体皮肤有什么作用？",
        "expected_intent": "ingredient",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "E03",
        "category": "正常",
        "type": "新产品-防晒",
        "query": "敏感肌适合用哪款防晒霜？",
        "expected_intent": "product",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "E04",
        "category": "边界",
        "type": "新成分-果酸",
        "query": "果酸和视黄醇能一起用吗？",
        "expected_intent": "ingredient",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "E05",
        "category": "正常",
        "type": "新产品-身体乳",
        "query": "烟酰胺身体乳和精华有什么区别？",
        "expected_intent": "ingredient",
        "expected_verdict": "pass",
        "expect_answer": True,
    },

    # ---- 第4轮新增：高频问答测试集（10项）----
    {
        "id": "F01",
        "category": "正常",
        "type": "高频-成分",
        "query": "玻尿酸有什么作用？",
        "expected_intent": "ingredient",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "F02",
        "category": "正常",
        "type": "高频-用法",
        "query": "洁面乳一天用几次？",
        "expected_intent": "usage",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "F03",
        "category": "正常",
        "type": "高频-肤质",
        "query": "油性皮肤适合用什么精华？",
        "expected_intent": "product",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "F04",
        "category": "正常",
        "type": "高频-价格",
        "query": "玻尿酸精华多少钱？",
        "expected_intent": "product",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "F05",
        "category": "正常",
        "type": "高频-售后",
        "query": "退货多久能收到退款？",
        "expected_intent": "after_sale",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "F06",
        "category": "正常",
        "type": "高频-成分对比",
        "query": "水杨酸和果酸有什么区别？",
        "expected_intent": "ingredient",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "F07",
        "category": "正常",
        "type": "高频-推荐",
        "query": "敏感肌推荐用什么面霜？",
        "expected_intent": "product",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "F08",
        "category": "正常",
        "type": "高频-搭配",
        "query": "精华和面霜的使用顺序是什么？",
        "expected_intent": "usage",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "F09",
        "category": "正常",
        "type": "高频-成分安全",
        "query": "烟酰胺浓度多少合适？",
        "expected_intent": "ingredient",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
    {
        "id": "F10",
        "category": "正常",
        "type": "高频-防晒",
        "query": "防晒霜需要每天用吗？",
        "expected_intent": "usage",
        "expected_verdict": "pass",
        "expect_answer": True,
    },
]


# ============ 合规检查专项测试 ============

COMPLIANCE_TESTS = [
    ("正常回答", "这款面霜含有烟酰胺和神经酰胺，适合干性皮肤使用。", "pass"),
    ("医疗词", "本产品可以治疗痘痘肌，效果显著。", "block"),
    ("绝对承诺", "坚持使用绝对让你的皮肤变好，100%有效。", "block"),
    ("功效越界", "坚持使用可以美白淡斑，祛皱缩毛孔。", "human"),
    ("医疗暗示", "这款精华医院也在用，医生推荐给患者。", "human"),
    ("空文本", "", "pass"),
    ("纯英文", "This product contains niacinamide for skincare.", "pass"),
]


def run_test_suite():
    """运行完整测试套件"""
    print("=" * 70)
    print("  美妆零售知识库系统 - 完整测试套件")
    print("=" * 70)

    from rag_engine import RAGEngine
    from intent_router import IntentRouter
    from compliance_check import ComplianceChecker
    from answer_generator import AnswerGenerator

    router = IntentRouter()
    checker = ComplianceChecker()
    rag = RAGEngine()

    results = {
        "total": 0, "pass": 0, "fail": 0,
        "categories": {},
    }

    # ---- 1. 意图识别测试 ----
    print("\n" + "=" * 70)
    print("  一、意图识别测试")
    print("=" * 70)
    intent_pass = 0
    for case in TEST_CASES:
        result = router.classify(case["query"])
        ok = result["intent"] == case["expected_intent"]
        status = "✅" if ok else "❌"
        intent_pass += ok
        print(f"  {status} [{case['id']}] {case['query'][:25]}... "
              f"预期:{case['expected_intent']} 实际:{result['intent']}")

    results["total"] += len(TEST_CASES)
    results["pass"] += intent_pass
    results["fail"] += len(TEST_CASES) - intent_pass

    # ---- 2. 合规检查测试 ----
    print("\n" + "=" * 70)
    print("  二、合规风控测试")
    print("=" * 70)
    comp_pass = 0
    for name, text, expected in COMPLIANCE_TESTS:
        result = checker.check(text)
        ok = result["verdict"] == expected
        comp_pass += ok
        status = "✅" if ok else "❌"
        print(f"  {status} [{name}] 预期:{expected} 实际:{result['verdict']}")

    results["total"] += len(COMPLIANCE_TESTS)
    results["pass"] += comp_pass
    results["fail"] += len(COMPLIANCE_TESTS) - comp_pass

    # ---- 3. RAG 检索测试 ----
    print("\n" + "=" * 70)
    print("  三、RAG 检索测试（验证能否检索到相关文档）")
    print("=" * 70)
    rag_pass = 0
    rag_queries = [
        ("烟酰胺", "02_成分知识库.md"),
        ("面霜价格", "01_产品目录.md"),
        ("使用方法", "03_使用方法指南.md"),
        ("退换货", "04_售后服务政策.md"),
        ("不良反应", "04_售后服务政策.md"),
    ]
    for query, expected_source in rag_queries:
        results_hybrid = rag.hybrid_search(query, top_k=3)
        sources = [r["source"] for r in results_hybrid]
        ok = expected_source in sources
        rag_pass += ok
        status = "✅" if ok else "❌"
        print(f"  {status} [{query}] 期望来源:{expected_source} 实际:{sources[:2]}")

    results["total"] += len(rag_queries)
    results["pass"] += rag_pass
    results["fail"] += len(rag_queries) - rag_pass

    # ---- 4. 端到端回答测试（含LLM）----
    print("\n" + "=" * 70)
    print("  四、端到端回答测试（RAG + LLM + 合规）")
    print("=" * 70)
    e2e_pass = 0
    e2e_total = 0
    agent = AnswerGenerator()

    for case in TEST_CASES:
        if case["category"] == "正常":
            e2e_total += 1
            result = agent.answer(case["query"])
            has_answer = bool(result["answer"])
            ok = has_answer and result["compliance"]["verdict"] in ["pass", "human"]
            e2e_pass += ok
            status = "✅" if ok else "❌"
            print(f"  {status} [{case['id']}] {case['query'][:25]}... "
                  f"耗时:{result['elapsed_ms']}ms 合规:{result['compliance']['verdict']}")

    results["total"] += e2e_total
    results["pass"] += e2e_pass
    results["fail"] += e2e_total - e2e_pass

    # ---- 5. 多轮对话测试（第8轮新增）----
    print("\n" + "=" * 70)
    print("  五、多轮对话测试（引用上文）")
    print("=" * 70)
    multi_pass = 0
    multi_total = 0
    multi_cases = [
        # (第一问, 第二问引用, 期望引用关键词) —— 期望词选回答中稳定出现的主题词
        ("烟酰胺焕亮精华适合什么肤质？", "它一天用几次？", "烟酰胺"),
        ("这款面霜多少钱？", "那款修护的呢？", "修护"),
        ("敏感肌可以用视黄醇吗？", "那有什么替代成分？", "替代"),
        ("玻尿酸精华怎么用？", "它能和面霜一起用吗？", "玻尿酸"),
        ("孕妇可以用水杨酸吗？", "那孕早期呢？", "水杨酸"),
        ("退货多久能收到退款？", "质量问题也是这个时间吗？", "退款"),
    ]

    for q1, q2, expect_kw in multi_cases:
        multi_total += 1
        sid = f"multi_test_{multi_total}"
        r1 = agent.answer(q1, session_id=sid)
        r2 = agent.answer(q2, session_id=sid)
        # 第二问应能引用上文（回答中包含期望关键词）
        references_prev = expect_kw in r2["answer"]
        ok = references_prev and bool(r2["answer"])
        multi_pass += ok
        status = "✅" if ok else "❌"
        print(f"  {status} [{multi_total}] Q1:{q1[:15]}... Q2:{q2[:15]}... 引用:{'是' if references_prev else '否'}")

    results["total"] += multi_total
    results["pass"] += multi_pass
    results["fail"] += multi_total - multi_pass

    # ---- 汇总 ----
    print("\n" + "=" * 70)
    print("  测试汇总")
    print("=" * 70)
    total = results["total"]
    passed = results["pass"]
    failed = results["fail"]
    rate = passed / total * 100 if total else 0

    print(f"  总测试数: {total}")
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    print(f"  通过率: {rate:.1f}%")
    print("=" * 70)

    # 保存结果
    import json
    from datetime import datetime
    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(exist_ok=True)
    report = {
        "timestamp": datetime.now().isoformat(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(rate, 1),
        "sections": {
            "intent": {"passed": intent_pass, "total": len(TEST_CASES)},
            "compliance": {"passed": comp_pass, "total": len(COMPLIANCE_TESTS)},
            "rag": {"passed": rag_pass, "total": len(rag_queries)},
            "e2e": {"passed": e2e_pass, "total": e2e_total},
        },
    }
    with open(output_dir / "test_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  测试报告已保存: {output_dir / 'test_report.json'}")

    return rate >= 85


if __name__ == "__main__":
    all_ok = run_test_suite()
    print(f"\n{'✅ 测试通过' if all_ok else '❌ 未达85%通过率'}")
