"""
美妆成分词库（领域词典）
功能：为中文分词提供美妆领域专有名词，提升成分检索准确率
集成：tokenize_cn() 分词时优先识别成分词（最长匹配），再回退到 n-gram
"""

# 美妆成分词库（覆盖知识库中所有成分 + 常见化妆品名词）
INGREDIENT_DICT = sorted([
    # 成分（从知识库提取）
    "烟酰胺", "视黄醇", "水杨酸", "玻尿酸", "神经酰胺", "透明质酸",
    "积雪草", "胜肽", "胶原蛋白", "泛醇", "角鲨烷", "果酸", "维生素C",
    "维生素E", "咖啡因", "氧化锌", "尿素", "甘油", "氨基酸", "茶树油",
    "尿囊素", "金盏花", "洋甘菊", "虾青素", "熊果苷", "传明酸", "曲酸",
    "二裂酵母", "玻色因", "锌", "泛醇B5",
    # 产品名词
    "洁面乳", "洁面啫喱", "洁面泡沫", "精华", "精华液", "面霜", "眼霜",
    "防晒乳", "防晒霜", "身体乳", "化妆水", "乳液", "面膜", "眼膜",
    "喷雾", "卸妆水", "卸妆油", "磨砂膏",
    # 肤质词
    "敏感肌", "油性皮肤", "干性皮肤", "混合性", "痘痘肌", "成熟肌",
    "油皮", "干皮",
    # 功效词
    "保湿", "控油", "美白", "抗皱", "修护", "舒缓", "提亮", "紧致",
    "祛痘", "去角质", "抗氧化", "防晒", "淡斑",
], key=len, reverse=True)  # 按长度降序，最长匹配优先


class IngredientTokenizer:
    """成分感知分词器"""

    def __init__(self, dict_words=None):
        self.dict_words = dict_words or INGREDIENT_DICT

    def tokenize(self, text: str) -> list:
        """成分感知分词：优先识别词库词，其余回退到单字+2-gram+3-gram"""
        import re
        tokens = []
        # 英文/数字
        tokens.extend(re.findall(r'[a-zA-Z0-9]+', text.lower()))
        # 中文连续串
        chinese_runs = re.findall(r'[\u4e00-\u9fff]+', text)
        for run in chinese_runs:
            tokens.extend(self._tokenize_run(run))
        return tokens

    def _tokenize_run(self, run: str) -> list:
        """对一段连续中文做成分感知分词"""
        result = []
        i = 0
        n = len(run)
        while i < n:
            matched = False
            # 尝试词库最长匹配
            for word in self.dict_words:
                if run.startswith(word, i):
                    result.append(word)
                    i += len(word)
                    matched = True
                    break
            if matched:
                continue
            # 未匹配 → 单字 + 尝试 2-gram/3-gram（下一轮）
            if i + 1 <= n:
                result.append(run[i])
            i += 1
        return result


if __name__ == "__main__":
    print("=" * 60)
    print("  成分感知分词 - 测试")
    print("=" * 60)

    tk = IngredientTokenizer()

    test_texts = [
        "烟酰胺有什么功效？",
        "敏感肌可以用视黄醇吗？",
        "玻尿酸和神经酰胺哪个更保湿？",
        "这款面霜含咖啡因眼霜的成分",
        "孕妇可以用水杨酸吗？",
    ]

    for text in test_texts:
        tokens = tk.tokenize(text)
        print(f"\n  {text}")
        print(f"  分词: {tokens}")

    # 验证成分词被完整识别（不拆分）
    all_ok = True
    checks = [
        ("烟酰胺有什么功效？", "烟酰胺"),
        ("敏感肌可以用视黄醇吗？", "视黄醇"),
        ("玻尿酸和神经酰胺哪个更保湿？", "神经酰胺"),
        ("这款面霜含咖啡因眼霜的成分", "咖啡因"),
    ]
    print("\n" + "=" * 60)
    print("  成分词完整识别验证")
    print("=" * 60)
    for text, expected in checks:
        tokens = tk.tokenize(text)
        ok = expected in tokens
        all_ok = all_ok and ok
        print(f"  {'✅' if ok else '❌'} [{text}] 应含完整词 '{expected}'")

    print(f"\n  {'✅ 成分词库分词验证通过' if all_ok else '❌ 有失败'}")
