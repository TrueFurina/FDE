"""
合规风控检查 Skill
功能：检查美妆客服回答是否涉及医疗诊断、绝对承诺、功效越界等违规内容
输入：回答文本
输出：{ verdict, reason, violated_rules }
规则：医疗诊断拦截 / 绝对承诺拦截 / 功效越界转人工
"""

import json

# 规则定义
RULES = {
    "medical_diagnosis": {
        "keywords": ["治疗", "治愈", "处方", "药物", "疗程", "根治", "临床证明"],
        "level": "block",
        "label": "医疗诊断",
        "message": "不得使用医疗术语，建议修改为改善、缓解等表述",
    },
    "absolute_promise": {
        "keywords": ["100%", "绝对", "保证", "百分百", "无效退款", "一定有效", "包治"],
        "level": "block",
        "label": "绝对承诺",
        "message": "不得使用绝对化承诺用语",
    },
    "efficacy_overreach": {
        "keywords": ["美白", "抗衰老", "祛斑", "祛皱", "缩毛孔", "减肥", "增高", "祛痘印"],
        "level": "human",  # 需要人工确认
        "label": "功效越界",
        "message": "涉及功效宣称，需确认产品是否有相关备案",
    },
    "medical_implication": {
        "keywords": ["医院", "医生推荐", "药用", "疗效", "患者", "处方药"],
        "level": "human",
        "label": "医疗暗示",
        "message": "涉及医疗场景暗示，需人工确认",
    },
}


class ComplianceChecker:
    """合规风控检查器"""

    def __init__(self):
        self.rules = RULES

    def check(self, text: str) -> dict:
        """检查文本是否合规"""
        if not text or not text.strip():
            return {
                "verdict": "pass",
                "reason": "无内容无需检查",
                "violated_rules": [],
            }

        violations = []
        lower = text.lower()

        for rule_name, rule in self.rules.items():
            for kw in rule["keywords"]:
                if kw.lower() in lower:
                    violations.append({
                        "rule": rule_name,
                        "label": rule["label"],
                        "keyword": kw,
                        "level": rule["level"],
                        "message": rule["message"],
                    })
                    break  # 每个规则只记录一次

        if not violations:
            return {
                "verdict": "pass",
                "reason": "未检测到违规内容",
                "violated_rules": [],
            }

        # 判断最高级别
        levels = [v["level"] for v in violations]
        if "block" in levels:
            final_verdict = "block"
        elif "human" in levels:
            final_verdict = "human"
        else:
            final_verdict = "pass"

        return {
            "verdict": final_verdict,
            "reason": f"触发{len(violations)}条规则：{', '.join([v['label'] for v in violations])}",
            "violated_rules": violations,
        }

    def check_generated_answer(self, answer: str, query: str = "") -> dict:
        """检查生成的答案（含查询上下文）"""
        result = self.check(answer)
        # 附加查询意图上下文
        result["query_context"] = query
        return result

    def to_json(self, result: dict) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(result, ensure_ascii=False, indent=2)


# Skill 定义元数据（供 Skill 系统识别）
SKILL_META = {
    "name": "compliance-check",
    "description": "美妆客服回答合规风控检查：医疗诊断/绝对承诺/功效越界检测",
    "input": "待检查的文本回答（字符串）",
    "output": "判决结果 JSON：{verdict, reason, violated_rules}",
    "rules": [
        "医疗诊断关键词 → block（拦截）",
        "绝对承诺关键词 → block（拦截）",
        "功效越界关键词 → human（转人工确认）",
        "医疗暗示关键词 → human（转人工确认）",
    ],
    "boundaries": [
        "空输入 → pass（无内容无需检查）",
        "纯英文 → 不触发中文关键词规则",
        "仅判断文本合规性，不做产品推荐",
    ],
}


if __name__ == "__main__":
    checker = ComplianceChecker()

    print("=" * 60)
    print("  合规风控检查 Skill - 测试报告")
    print("=" * 60)

    test_cases = [
        ("正常流程", "这款面霜含有烟酰胺和神经酰胺，适合干性皮肤使用，能够帮助保湿滋润。", "pass"),
        ("边界-医疗词", "本产品可以治疗痘痘肌，效果显著，建议连续使用一个疗程。", "block"),
        ("边界-功效越界", "坚持使用可以美白淡斑，让肌肤焕然一新，绝对让你的皮肤变好。", "block"),
        ("边界-医疗暗示", "这款精华医院也在用，医生推荐给很多患者。", "human"),
        ("空文本", "", "pass"),
        ("纯英文", "This product contains niacinamide for daily skincare.", "pass"),
    ]

    all_pass = True
    for name, text, expected in test_cases:
        result = checker.check(text)
        ok = result["verdict"] == expected
        all_pass = all_pass and ok
        print(f"\n【{name}】 {'✅' if ok else '❌'}")
        print(f"  输入: {text[:50]}...")
        print(f"  判决: {result['verdict'].upper()} (期望: {expected})")
        print(f"  原因: {result['reason']}")
        for v in result["violated_rules"]:
            print(f"    → [{v['label']}] \"{v['keyword']}\" → {v['message']}")

    print("\n" + "=" * 60)
    print(f"  {'✅ 全部测试通过！' if all_pass else '❌ 有测试未通过'}")
    print("=" * 60)
