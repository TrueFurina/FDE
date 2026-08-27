"""
数据校验器（输入输出 Schema 校验）
功能：对系统输入（查询）和输出（回答）进行 Schema 校验，拦截非法数据
校验项：
1. 输入校验：查询类型/长度/字符集
2. 输出校验：回答类型/长度/来源字段完整性
输出：output/validation_report.json
"""

import sys
import json
import time
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"


class SchemaValidator:
    """数据 Schema 校验器"""

    # ===== 输入校验 =====
    def validate_input(self, query: str) -> dict:
        """校验输入查询
        返回: {"valid": bool, "errors": [...]}
        """
        errors = []

        # 1. 类型校验
        if not isinstance(query, str):
            errors.append(f"查询必须是字符串，实际为 {type(query).__name__}")

        # 2. 长度校验
        if isinstance(query, str):
            if len(query) == 0:
                errors.append("查询不能为空")
            elif len(query) > 500:
                errors.append(f"查询超长（{len(query)} > 500 字符）")

        # 3. 字符集校验（只允许常见可见字符）
        if isinstance(query, str) and query:
            invalid_chars = re.findall(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', query)
            if invalid_chars:
                errors.append(f"包含非法控制字符: {[hex(ord(c)) for c in invalid_chars]}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "input_type": "query",
        }

    # ===== 输出校验 =====
    def validate_output(self, result: dict) -> dict:
        """校验输出结果（answer() 返回值）
        返回: {"valid": bool, "errors": [...]}
        """
        errors = []

        # 必需字段
        required_fields = ["query", "answer", "sources", "compliance", "intent"]
        for field in required_fields:
            if field not in result:
                errors.append(f"缺少必需字段: {field}")

        # answer 类型与长度
        if "answer" in result:
            if not isinstance(result["answer"], str):
                errors.append(f"answer 必须是字符串，实际为 {type(result['answer']).__name__}")
            elif len(result["answer"]) == 0:
                errors.append("answer 为空")

        # sources 结构
        if "sources" in result:
            if not isinstance(result["sources"], list):
                errors.append("sources 必须是列表")
            else:
                for i, s in enumerate(result["sources"]):
                    if not isinstance(s, dict) or "source" not in s:
                        errors.append(f"sources[{i}] 缺少 source 字段")

        # compliance 结构
        if "compliance" in result:
            comp = result["compliance"]
            if not isinstance(comp, dict) or "verdict" not in comp:
                errors.append("compliance 缺少 verdict 字段")
            elif comp.get("verdict") not in ("pass", "block", "human"):
                errors.append(f"compliance.verdict 非法值: {comp.get('verdict')}")

        # intent 结构
        if "intent" in result:
            intent = result["intent"]
            if not isinstance(intent, dict) or "intent" not in intent:
                errors.append("intent 缺少 intent 字段")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "output_type": "answer_result",
        }

    # ===== 完整校验 =====
    def validate_full(self, query: str, result: dict) -> dict:
        """完整校验（输入 + 输出）"""
        input_check = self.validate_input(query)
        output_check = self.validate_output(result)
        return {
            "input": input_check,
            "output": output_check,
            "overall_valid": input_check["valid"] and output_check["valid"],
        }


def main():
    print("=" * 60)
    print("  数据校验器（Schema 校验）- 测试")
    print("=" * 60)

    validator = SchemaValidator()

    # ===== 1. 输入校验测试 =====
    print("\n=== 输入校验 ===")
    test_inputs = [
        ("正常查询", "烟酰胺有什么功效？"),
        ("空字符串", ""),
        ("超长查询", "请推荐" * 200),
        ("非字符串", 12345),
        ("含控制字符", "测试\x00查询"),
    ]

    input_ok = True
    for name, query in test_inputs:
        r = validator.validate_input(query)
        ok = r["valid"]
        if name == "正常查询":
            input_ok = input_ok and ok
        else:
            input_ok = input_ok and not ok  # 非法输入应被拦截
        print(f"  {'✅' if ok else '❌拦截'} [{name}] {r['errors'][:1]}")

    # ===== 2. 输出校验测试 =====
    print("\n=== 输出校验 ===")
    valid_result = {
        "query": "烟酰胺有什么功效？",
        "answer": "烟酰胺有助于提亮肤色",
        "sources": [{"source": "02_成分知识库.md", "chunk_index": 0}],
        "compliance": {"verdict": "pass", "reason": "合规"},
        "intent": {"intent": "ingredient", "intent_label": "成分功效"},
        "needs_human": False,
        "elapsed_ms": 100,
    }
    invalid_result = {
        "query": "测试",
        "answer": "",  # 空回答
        "sources": "not-a-list",  # 错误类型
        "compliance": {"verdict": "invalid_verdict"},  # 非法值
        # 缺少 intent
    }

    r_ok = validator.validate_output(valid_result)
    r_bad = validator.validate_output(invalid_result)
    print(f"  {'✅' if r_ok['valid'] else '❌'} [正常结果] 校验通过")
    print(f"  {'✅拦截' if not r_bad['valid'] else '❌'} [非法结果] 拦截: {r_bad['errors']}")

    output_ok = r_ok["valid"] and not r_bad["valid"]

    # ===== 3. 完整校验 =====
    print("\n=== 完整校验 ===")
    full = validator.validate_full("烟酰胺有什么功效？", valid_result)
    print(f"  总体有效: {full['overall_valid']}")

    ok = input_ok and output_ok and full["overall_valid"]
    print(f"\n  {'✅ 通过标准达成：非法输入被拦截' if ok else '❌ 未通过'}")

    # 保存报告
    OUTPUT_DIR.mkdir(exist_ok=True)
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "input_valid": input_ok,
        "output_valid": output_ok,
        "full_valid": full["overall_valid"],
    }
    with open(OUTPUT_DIR / "validation_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  报告已保存: {OUTPUT_DIR / 'validation_report.json'}")


if __name__ == "__main__":
    main()
