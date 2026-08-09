"""
多语言支持
功能：支持英文/中文问法检索知识库，中英文混合查询归一化
策略：英文关键词映射到中文知识库词（成分/产品），查询翻译后再检索
输出：output/multilang_report.json
"""

import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

# 英文 → 中文 关键词映射（成分/产品/肤质/功效）
EN_TO_CN = {
    # 成分
    "niacinamide": "烟酰胺",
    "retinol": "视黄醇",
    "salicylic": "水杨酸",
    "hyaluronic": "玻尿酸",
    "ceramide": "神经酰胺",
    "centella": "积雪草",
    "peptide": "胜肽",
    "collagen": "胶原蛋白",
    "panthenol": "泛醇",
    "squalane": "角鲨烷",
    "aha": "果酸",
    "vitamin c": "维生素C",
    "caffeine": "咖啡因",
    "zinc oxide": "氧化锌",
    "urea": "尿素",
    # 产品
    "cleanser": "洁面",
    "essence": "精华",
    "cream": "面霜",
    "eye cream": "眼霜",
    "sunscreen": "防晒",
    "body lotion": "身体乳",
    "serum": "精华",
    # 肤质
    "sensitive": "敏感肌",
    "oily": "油性",
    "dry": "干性",
    "combination": "混合性",
    # 功效
    "moisturizing": "保湿",
    "whitening": "美白",
    "anti-aging": "抗皱",
    "repair": "修护",
    "soothing": "舒缓",
    # 其他
    "price": "多少钱",
    "how to use": "怎么用",
    "return": "退货",
    "refund": "退款",
}


class MultilangSupport:
    """多语言支持器"""

    def translate_query(self, query: str) -> dict:
        """英文问法翻译为中文检索查询
        返回: {"original":..., "translated":..., "matched":[...], "is_english": bool}
        """
        lower = query.lower()
        # 检测是否含英文关键词
        matched = []
        translated = query  # 默认保持原文

        for en, cn in EN_TO_CN.items():
            if en in lower:
                matched.append((en, cn))
                # 替换为中文（保留英文原词以提升召回）
                translated = translated.replace(en, f"{cn}", 1)

        # 判断是否为英文问法（含英文关键词）
        is_english = len(matched) > 0 and any(c.isalpha() and ord(c) < 128 for c in query)

        return {
            "original": query,
            "translated": translated,
            "matched": matched,
            "is_english": is_english,
        }

    def search(self, engine, query: str, top_k: int = 3) -> dict:
        """多语言检索：英文问法自动翻译后检索"""
        trans = self.translate_query(query)

        # 用翻译后的查询检索
        if trans["is_english"] and trans["translated"] != query:
            results = engine.hybrid_search(trans["translated"], top_k=top_k)
            # 补充原查询检索（保险）
            if not results:
                results = engine.hybrid_search(query, top_k=top_k)
            return {**trans, "results": results}
        else:
            return {**trans, "results": engine.hybrid_search(query, top_k=top_k)}


def main():
    print("=" * 60)
    print("  多语言支持 - 测试")
    print("=" * 60)

    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from rag_engine import RAGEngine
    engine = RAGEngine()
    ml = MultilangSupport()

    # 英文问法测试
    test_queries = [
        "What is niacinamide good for?",
        "Is retinol suitable for sensitive skin?",
        "How much is this cream?",
        "Can I use salicylic acid?",
        "What does hyaluronic acid do?",
    ]

    all_ok = True
    for q in test_queries:
        result = ml.search(engine, q)
        trans = result["translated"]
        matched = result["matched"]
        sources = [r["source"] for r in result["results"]]

        ok = bool(sources)
        all_ok = all_ok and ok
        print(f"\n🔍 EN: {q}")
        print(f"   翻译: {trans}")
        print(f"   命中词: {[c for _, c in matched]}")
        print(f"   检索结果: {'✅ ' + str(sources[:2]) if ok else '❌ 无结果'}")

    print("\n" + "=" * 60)
    print(f"  {'✅ 通过标准达成：英文问法可检索' if all_ok else '❌ 有英文问法无结果'}")
    print("=" * 60)

    # 保存报告
    OUTPUT_DIR.mkdir(exist_ok=True)
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "en_to_cn_mapping_count": len(EN_TO_CN),
        "test_results": [{"query": q, "translated": ml.translate_query(q)["translated"]} for q in test_queries],
    }
    with open(OUTPUT_DIR / "multilang_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  报告已保存: {OUTPUT_DIR / 'multilang_report.json'}")


if __name__ == "__main__":
    main()
