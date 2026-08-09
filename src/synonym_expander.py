"""
知识库同义词扩展
功能：查询时把常见同义词归一化为标准词，提升检索命中率
示例：玻尿酸→透明质酸，维C→维生素C，A醇→视黄醇，祛痘→控油
集成：RAG 引擎查询前调用 query_expand()
"""

# 同义词映射（别名 → 标准词）
SYNONYMS = {
    # 成分同义词
    "玻尿酸": "透明质酸",
    "透明质酸钠": "透明质酸",
    "维c": "维生素C",
    "维C": "维生素C",
    "vc": "维生素C",
    "VC": "维生素C",
    "a醇": "视黄醇",
    "A醇": "视黄醇",
    "维a醇": "视黄醇",
    "视黄醇棕榈酸酯": "视黄醇",
    "b5": "泛醇",
    "B5": "泛醇",
    "泛醇b5": "泛醇",
    "烟酰胺": "烟酰胺",  # 标准词，保留
    "水杨酸": "水杨酸",
    "果酸": "果酸",
    "ahа": "果酸",
    "aha": "果酸",
    "神经酰胺": "神经酰胺",
    "积雪草": "积雪草",
    "角鲨烷": "角鲨烷",
    "胜肽": "胜肽",
    "多肽": "胜肽",
    "胶原蛋白": "胶原蛋白",
    # 产品同义词
    "面霜": "面霜",
    "润肤霜": "面霜",
    "眼霜": "眼霜",
    "眼胶": "眼霜",
    "精华": "精华",
    "精华液": "精华",
    "serum": "精华",
    "防晒": "防晒",
    "防晒霜": "防晒",
    "身体乳": "身体乳",
    "润肤乳": "身体乳",
    # 功效同义词
    "祛痘": "控油",
    "去痘": "控油",
    "去黑头": "控油",
    "亮白": "提亮",
    "焕白": "提亮",
    "抗老": "抗皱",
    "抗衰": "抗皱",
    "防老": "抗皱",
    "舒缓": "舒缓",
    "镇静": "舒缓",
    "补水": "保湿",
    "滋润": "保湿",
    "修护": "修护",
    "修复": "修护",
    # 肤质同义词
    "油性肌": "油性皮肤",
    "干性肌": "干性皮肤",
    "混合肌": "混合性",
    "痘痘肌": "痘痘肌",
    "敏感皮": "敏感肌",
}


class SynonymExpander:
    """同义词扩展器"""

    def __init__(self, synonyms=None):
        self.synonyms = synonyms or SYNONYMS

    def expand(self, query: str) -> str:
        """把查询中的同义词替换为标准词（同时保留原词以提升召回）"""
        expanded = query
        # 替换为带标准词的扩展形式（保留原词）
        for alias, standard in self.synonyms.items():
            if alias in expanded and standard != alias:
                # 只替换一次，避免重复
                expanded = expanded.replace(alias, f"{alias} {standard}", 1)
        return expanded

    def normalize(self, query: str) -> str:
        """纯归一化：把同义词替换为标准词（用于检索打分）"""
        normalized = query
        for alias, standard in self.synonyms.items():
            if alias in normalized and standard != alias:
                normalized = normalized.replace(alias, standard)
        return normalized

    def expand_for_search(self, query: str) -> list:
        """返回多个查询变体（原查询 + 扩展查询 + 归一化查询），供检索融合"""
        return list(dict.fromkeys([
            query,
            self.expand(query),
            self.normalize(query),
        ]))


if __name__ == "__main__":
    print("=" * 60)
    print("  同义词扩展 - 测试")
    print("=" * 60)

    expander = SynonymExpander()

    test_queries = [
        "玻尿酸有什么功效？",
        "维C能美白吗？",
        "A醇怎么用？",
        "祛痘产品推荐",
        "油性肌适合什么精华？",
        "润肤霜多少钱？",
        "补水用什么好？",
        "抗老精华推荐",
    ]

    for q in test_queries:
        variants = expander.expand_for_search(q)
        print(f"\n  🔍 {q}")
        print(f"    变体: {variants}")

    # 验证通过标准：同义词可命中检索
    print("\n" + "=" * 60)
    print("  通过标准验证：同义词可命中检索")
    print("=" * 60)

    import sys as _sys
    _sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent / "src"))
    from rag_engine import RAGEngine
    engine = RAGEngine()

    # 用同义词查询，验证能命中标准词文档
    test_cases = [
        ("玻尿酸有什么功效", "透明质酸", "02_成分知识库.md"),
        ("A醇怎么用", "视黄醇", "03_使用方法指南.md"),
        ("祛痘产品", "控油", "01_产品目录.md"),
    ]

    all_ok = True
    for q, standard_kw, expected_src in test_cases:
        variants = expander.expand_for_search(q)
        # 对每个变体检索，看标准词文档是否命中
        hit = False
        for variant in variants:
            results = engine.hybrid_search(variant, top_k=3)
            if expected_src in [r["source"] for r in results]:
                hit = True
                break
        all_ok = all_ok and hit
        print(f"  {'✅' if hit else '❌'} [{q}] → 命中 {expected_src}")

    print(f"\n  {'✅ 通过标准达成：同义词可命中检索' if all_ok else '❌ 有失败'}")
