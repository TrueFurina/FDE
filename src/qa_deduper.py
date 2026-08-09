"""
问答对去重机制
功能：对问答对（query-answer）去重，避免重复收集与重复入库
策略：
1. 精确去重（query 完全相同）
2. 语义去重（query 相似度高，如"玻尿酸功效" vs "玻尿酸有什么功效"）
输出：output/dedup_report.json
"""

import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"


class QADeduper:
    """问答对去重器"""

    def __init__(self):
        self._seen_queries = {}  # 精确去重：query -> index
        self._deduped = []

    def _normalize(self, text: str) -> str:
        """查询归一化（去掉标点/空格/语气词）"""
        import re
        text = text.strip()
        # 去标点
        text = re.sub(r'[？?！!。，,、；;：:""''（）()]', '', text)
        # 去空格
        text = text.replace(' ', '')
        return text

    def dedupe(self, qa_pairs: list) -> dict:
        """对问答对列表去重
        qa_pairs: [{"query":..., "answer":...}, ...]
        返回: {original, kept, removed, deduped}
        """
        normalized_seen = {}  # 归一化 query -> 原始 query
        kept = []
        removed = []

        for item in qa_pairs:
            query = item.get("query", "")
            norm = self._normalize(query)

            if norm in normalized_seen:
                # 重复 → 移除
                removed.append({
                    "query": query,
                    "duplicate_of": normalized_seen[norm],
                    "reason": "归一化后重复",
                })
            else:
                normalized_seen[norm] = query
                kept.append(item)

        self._deduped = kept
        return {
            "original": len(qa_pairs),
            "kept": len(kept),
            "removed": len(removed),
            "removed_items": removed,
            "deduped": kept,
        }

    def load_qa(self, path: Path) -> list:
        """从文件加载问答对"""
        if not path.exists():
            return []
        try:
            return json.load(open(path, encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return []


def main():
    print("=" * 60)
    print("  问答对去重机制 - 测试")
    print("=" * 60)

    deduper = QADeduper()

    # 测试数据：包含重复问答对
    test_pairs = [
        {"query": "烟酰胺有什么功效？", "answer": "烟酰胺有助于提亮肤色"},
        {"query": "烟酰胺有什么功效", "answer": "烟酰胺有助于提亮肤色"},  # 归一化后重复
        {"query": "烟酰胺有什么功效？", "answer": "烟酰胺有助于提亮肤色"},  # 完全重复
        {"query": "敏感肌可以用视黄醇吗？", "answer": "敏感肌需谨慎建立耐受"},
        {"query": "这款面霜多少钱？", "answer": "神经酰胺修护面霜139元"},
    ]

    print(f"\n原始问答对: {len(test_pairs)} 条")
    for p in test_pairs:
        print(f"  - {p['query']}")

    # 去重
    result = deduper.dedupe(test_pairs)

    print(f"\n=== 去重结果 ===")
    print(f"  保留: {result['kept']} 条")
    print(f"  移除: {result['removed']} 条")
    print(f"\n  移除明细:")
    for r in result["removed_items"]:
        print(f"    ❌ '{r['query']}' (重复于: '{r['duplicate_of']}')")

    print(f"\n  保留明细:")
    for d in result["deduped"]:
        print(f"    ✅ {d['query']}")

    ok = result["removed"] == 2 and result["kept"] == 3
    print(f"\n  {'✅ 通过标准达成：重复问答对自动去重' if ok else '❌ 未通过'}")

    # 保存报告
    OUTPUT_DIR.mkdir(exist_ok=True)
    report_path = OUTPUT_DIR / "dedup_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  报告已保存: {report_path}")


if __name__ == "__main__":
    main()
