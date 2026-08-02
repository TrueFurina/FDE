"""
意图识别与路由 Agent
功能：识别用户咨询的问题类型，路由到对应处理流程
问题类型：
- product   : 产品咨询（价格/规格/功效）
- ingredient: 成分功效（成分作用/适用肤质）
- usage     : 使用方法（步骤/频率/搭配）
- after_sale: 售后规则（退换货/退款/物流）
- risk      : 高风险（不良反应/过敏/医疗）
- general   : 通用咨询
"""

import re
from enum import Enum


class Intent(str, Enum):
    PRODUCT = "product"
    INGREDIENT = "ingredient"
    USAGE = "usage"
    AFTER_SALE = "after_sale"
    RISK = "risk"
    GENERAL = "general"


# 关键词规则（按优先级从高到低）
RISK_KEYWORDS = [
    "过敏", "刺痛", "发红", "红肿", "起疹", "瘙痒", "痒", "肿", "呼吸困难",
    "治疗", "治愈", "处方", "医院", "医生", "药用", "疗程", "患者", "就医",
    "不良反应", "副作用", "烂脸", "毁容",
    # 特殊人群（儿童/哺乳期高危；孕妇走成分检索+安全提示）
    "哺乳期", "产妇", "儿童", "小孩", "婴儿", "婴幼儿",
    "3岁", "三岁", "宝宝",
    # 医疗功效暗示
    "变白", "去疤", "祛疤", "治痘", "消炎", "杀菌", "抗炎",
]

# 孕妇相关（单独处理：走成分检索但需安全提示）
PREGNANCY_KEYWORDS = ["孕妇", "孕期", "怀孕"]

AFTER_SALE_KEYWORDS = [
    "退货", "退款", "退换", "售后", "物流", "快递", "发货", "签收",
    "拆封", "保质期", "过期", "维修", "补偿", "赔偿", "发票",
]

INGREDIENT_KEYWORDS = [
    "成分", "烟酰胺", "视黄醇", "A醇", "水杨酸", "玻尿酸", "神经酰胺",
    "积雪草", "胜肽", "胶原蛋白", "泛醇", "角鲨烷", "果酸", "维生素C",
    "VC", "功效", "浓度", "孕妇", "孕期", "禁忌", "搭配", "不耐受",
    "建立耐受", "美白", "控油", "保湿", "抗皱", "修护", "舒缓",
    "玻色因", "传明酸", "熊果苷", "虾青素", "曲酸", "二裂酵母", "氨基酸",
    "金盏花", "洋甘菊", "尿囊素", "维生素E", "维E", "维C", "透明质酸",
    "维生素B5", "B5", "烟酰胺5%", "作用", "成份",
]

# 强使用意图词：明确指向使用方法的问题，优先级高于成分词
USAGE_STRONG_KEYWORDS = [
    "怎么用", "如何使用", "用法", "使用步骤", "每天几次", "用多久",
    "早晚", "用量", "涂抹", "频率", "用几次", "什么时候用",
]

USAGE_KEYWORDS = [
    "怎么用", "如何使用", "用法", "使用步骤", "每天几次", "用多久",
    "早晚", "顺序", "搭配使用", "用量", "涂抹", "按摩", "频率",
]

PRODUCT_KEYWORDS = [
    "多少钱", "价格", "规格", "ml", "ml", "g", "瓶", "支", "盒",
    "有没有", "还有货", "库存", "在哪买", "怎么买", "链接", "版本",
    "适合", "油皮", "干皮", "敏感肌", "混合性", "油性", "干性",
]

SKIN_TYPE_KEYWORDS = [
    "油皮", "干皮", "敏感肌", "混合性", "油性", "干性", "痘痘肌",
    "油性皮肤", "干性皮肤", "敏感皮肤",
]


class IntentRouter:
    """意图识别与路由器"""

    def __init__(self):
        pass

    def classify(self, query: str) -> dict:
        """识别意图，返回分类结果和命中关键词"""
        # 统一处理
        text = query.strip()
        lower = text.lower()

        hits = {}

        # 1. 高风险优先（不良反应/医疗）
        risk_kw = [kw for kw in RISK_KEYWORDS if kw.lower() in lower]
        if risk_kw:
            hits["risk"] = risk_kw

        # 2. 售后规则
        after_sale_kw = [kw for kw in AFTER_SALE_KEYWORDS if kw.lower() in lower]
        if after_sale_kw:
            hits["after_sale"] = after_sale_kw

        # 3. 成分功效
        ingredient_kw = [kw for kw in INGREDIENT_KEYWORDS if kw.lower() in lower]
        if ingredient_kw:
            hits["ingredient"] = ingredient_kw

        # 4. 使用方法
        usage_kw = [kw for kw in USAGE_KEYWORDS if kw.lower() in lower]
        if usage_kw:
            hits["usage"] = usage_kw

        # 5. 产品咨询
        product_kw = [kw for kw in PRODUCT_KEYWORDS if kw.lower() in lower]
        if product_kw:
            hits["product"] = product_kw

        # 判断最终意图（优先级：risk > 强使用词 > after_sale > ingredient > usage > product > general）
        usage_strong_kw = [kw for kw in USAGE_STRONG_KEYWORDS if kw.lower() in lower]
        if "risk" in hits:
            intent = Intent.RISK
        elif usage_strong_kw:
            intent = Intent.USAGE
            hits["usage_strong"] = usage_strong_kw
        elif "after_sale" in hits:
            intent = Intent.AFTER_SALE
        elif "ingredient" in hits:
            intent = Intent.INGREDIENT
        elif "usage" in hits:
            intent = Intent.USAGE
        elif "product" in hits:
            intent = Intent.PRODUCT
        else:
            intent = Intent.GENERAL

        # 判断是否涉及肤质问题（辅助信息）
        skin_type_kw = [kw for kw in SKIN_TYPE_KEYWORDS if kw.lower() in lower]

        # 判断是否涉及孕妇（安全提示，不直接转人工，走成分检索）
        pregnancy_kw = [kw for kw in PREGNANCY_KEYWORDS if kw.lower() in lower]

        return {
            "intent": intent.value,
            "intent_label": {
                "product": "产品咨询",
                "ingredient": "成分功效",
                "usage": "使用方法",
                "after_sale": "售后规则",
                "risk": "高风险/不良反应",
                "general": "通用咨询",
            }[intent.value],
            "keyword_hits": hits,
            "skin_type": skin_type_kw,
            "needs_human": intent == Intent.RISK,
        }

    def route(self, query: str):
        """路由决策：返回处理路径"""
        result = self.classify(query)

        # 路由策略
        if result["needs_human"]:
            return {
                **result,
                "route": "human",
                "message": "检测到高风险关键词，直接转人工处理",
            }
        elif result["intent"] == "general":
            return {
                **result,
                "route": "rag_general",
                "message": "通用咨询，走 RAG 检索+LLM 生成",
            }
        else:
            return {
                **result,
                "route": "rag_specialized",
                "message": f"识别为{result['intent_label']}，走专项 RAG 检索",
            }


if __name__ == "__main__":
    router = IntentRouter()

    test_queries = [
        "这款面霜多少钱？",
        "烟酰胺有什么功效？",
        "敏感肌可以用视黄醇吗？",
        "拆封了还能退货吗？",
        "用了之后过敏了怎么办？",
        "你好，在吗？",
        "这个精华怎么用？",
    ]

    print("=" * 60)
    print("  意图识别与路由 Agent - 自测")
    print("=" * 60)
    for q in test_queries:
        result = router.route(q)
        print(f"\n🔍 {q}")
        print(f"  意图: {result['intent_label']} ({result['intent']})")
        print(f"  路由: {result['route']}")
        print(f"  命中: {result['keyword_hits']}")
        if result.get("needs_human"):
            print(f"  ⚠️ 需要转人工!")

    print("\n" + "=" * 60)
    print("  ✅ 意图识别 Agent 自测完成")
    print("=" * 60)
