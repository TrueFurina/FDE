"""
查询推荐扩展
功能：根据当前问题推荐 3 个相关追问问题，提升交互体验
策略：基于意图+关键词规则推荐（不额外调用 LLM，保持轻量）
集成：AnswerGenerator.answer() 返回 recommendations 字段
"""

import re

# 推荐规则：意图 -> 推荐问题模板
RECOMMENDATION_RULES = {
    "ingredient": [
        "这个成分适合什么肤质？",
        "它有什么注意事项？",
        "含这个成分的产品有哪些？",
    ],
    "product": [
        "这款产品适合什么肤质？",
        "这款产品怎么使用？",
        "这款产品有什么成分？",
    ],
    "usage": [
        "使用多久能看到效果？",
        "能和其他产品搭配吗？",
        "敏感肌可以用吗？",
    ],
    "after_sale": [
        "退款需要多长时间？",
        "质量问题怎么处理？",
        "赠品需要退回吗？",
    ],
    "general": [
        "烟酰胺有什么功效？",
        "敏感肌适合用什么产品？",
        "退换货政策是什么？",
    ],
}

# 成分关键词（用于推荐精准追问）
INGREDIENT_PATTERN = re.compile(
    r"(烟酰胺|视黄醇|水杨酸|玻尿酸|神经酰胺|积雪草|胜肽|胶原蛋白|泛醇|"
    r"角鲨烷|果酸|维生素C|咖啡因|氧化锌|尿素|茶树油|尿囊素|虾青素|熊果苷|玻色因)"
)

# 产品关键词
PRODUCT_PATTERN = re.compile(r"(洁面|精华|面霜|眼霜|防晒|身体乳|面膜|化妆水)")


class QueryRecommender:
    """查询推荐器"""

    def __init__(self):
        pass

    def recommend(self, query: str, intent: str = None) -> list:
        """根据查询和意图推荐相关问题
        返回：最多 3 个推荐问题
        """
        if intent is None:
            intent = "general"

        # 提取查询中的成分/产品词
        ingredient_match = INGREDIENT_PATTERN.search(query)
        product_match = PRODUCT_PATTERN.search(query)
        ingredient = ingredient_match.group(0) if ingredient_match else None
        product = product_match.group(0) if product_match else None

        recommendations = []

        # 1. 基于意图的通用推荐
        base_recommendations = RECOMMENDATION_RULES.get(intent, RECOMMENDATION_RULES["general"])

        # 2. 基于成分/产品的定制推荐
        if ingredient:
            recommendations.append(f"{ingredient}适合什么肤质？")
            recommendations.append(f"含{ingredient}的产品有哪些？")
        if product:
            recommendations.append(f"{product}怎么使用？")
            recommendations.append(f"{product}适合什么肤质？")

        # 3. 补足到 3 条（用意图模板）
        for rec in base_recommendations:
            if len(recommendations) >= 3:
                break
            if rec not in recommendations:
                recommendations.append(rec)

        return recommendations[:3]


if __name__ == "__main__":
    print("=" * 60)
    print("  查询推荐扩展 - 测试")
    print("=" * 60)

    recommender = QueryRecommender()

    test_cases = [
        ("烟酰胺有什么功效？", "ingredient"),
        ("这款面霜多少钱？", "product"),
        ("视黄醇精华怎么用？", "usage"),
        ("拆封了还能退货吗？", "after_sale"),
        ("玻尿酸精华适合什么肤质？", "ingredient"),
    ]

    all_ok = True
    for query, intent in test_cases:
        recs = recommender.recommend(query, intent)
        ok = len(recs) >= 1 and len(recs) <= 3
        all_ok = all_ok and ok
        print(f"\n  🔍 {query} (意图: {intent})")
        for i, r in enumerate(recs):
            print(f"     推荐{i+1}: {r}")

    print("\n" + "=" * 60)
    print(f"  {'✅ 通过标准达成：返回相关推荐问题' if all_ok else '❌ 有失败'}")
    print("=" * 60)
