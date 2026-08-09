"""
回答导出功能（问答对收集）
功能：将会话记忆中的问答对导出为文件（JSON/CSV/Markdown）
用法：python scripts/export_qa.py
"""

import sys
import json
import csv
import time
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
OUTPUT_DIR = PROJECT_ROOT / "output"


class QAPairExporter:
    """问答对收集与导出器"""

    def __init__(self):
        from answer_generator import AnswerGenerator
        self.agent = AnswerGenerator()

    def collect(self, questions: list, session_prefix: str = "qa_collect") -> list:
        """收集问答对（每问一个会话，避免多轮干扰）"""
        qa_pairs = []
        for i, q in enumerate(questions):
            sid = f"{session_prefix}_{i}"
            result = self.agent.answer(q, session_id=sid)
            qa_pairs.append({
                "id": i + 1,
                "query": q,
                "answer": result["answer"],
                "intent": result["intent"]["intent_label"],
                "compliance": result["compliance"]["verdict"],
                "sources": [s["source"] for s in result["sources"]],
                "elapsed_ms": result["elapsed_ms"],
            })
            print(f"  [{i+1}/{len(questions)}] ✅ {q[:25]}... ({result['elapsed_ms']:.0f}ms)")
        return qa_pairs

    def export_json(self, qa_pairs: list, path: Path) -> int:
        """导出 JSON"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
        return len(qa_pairs)

    def export_csv(self, qa_pairs: list, path: Path) -> int:
        """导出 CSV"""
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "query", "answer", "intent", "compliance", "sources", "elapsed_ms"])
            writer.writeheader()
            for p in qa_pairs:
                writer.writerow({
                    "id": p["id"],
                    "query": p["query"],
                    "answer": p["answer"][:200],
                    "intent": p["intent"],
                    "compliance": p["compliance"],
                    "sources": "|".join(p["sources"]),
                    "elapsed_ms": p["elapsed_ms"],
                })
        return len(qa_pairs)

    def export_markdown(self, qa_pairs: list, path: Path) -> int:
        """导出 Markdown"""
        lines = ["# 问答对收集记录", "", f"> 导出时间：{time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
        for p in qa_pairs:
            lines.append(f"## Q{p['id']}: {p['query']}")
            lines.append("")
            lines.append(f"**回答**: {p['answer']}")
            lines.append("")
            lines.append(f"**意图**: {p['intent']} | **合规**: {p['compliance']} | **耗时**: {p['elapsed_ms']}ms")
            lines.append("")
            lines.append(f"**来源**: {', '.join(p['sources'])}")
            lines.append("")
            lines.append("---")
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return len(qa_pairs)


def main():
    parser = argparse.ArgumentParser(description="问答对收集与导出")
    parser.add_argument("--format", choices=["json", "csv", "md", "all"], default="all")
    args = parser.parse_args()

    print("=" * 60)
    print("  回答导出功能（问答对收集）")
    print("=" * 60)

    # 默认收集问题
    questions = [
        "烟酰胺有什么功效？",
        "敏感肌可以用视黄醇吗？",
        "这款面霜多少钱？",
        "拆封了还能退货吗？",
    ]

    print(f"待收集问题: {len(questions)}\n")
    exporter = QAPairExporter()
    qa_pairs = exporter.collect(questions)

    # 导出
    OUTPUT_DIR.mkdir(exist_ok=True)
    count = 0
    if args.format in ("json", "all"):
        count = exporter.export_json(qa_pairs, OUTPUT_DIR / "qa_pairs.json")
        print(f"✅ qa_pairs.json 已导出 ({count} 条)")
    if args.format in ("csv", "all"):
        count = exporter.export_csv(qa_pairs, OUTPUT_DIR / "qa_pairs.csv")
        print(f"✅ qa_pairs.csv 已导出 ({count} 条)")
    if args.format in ("md", "all"):
        count = exporter.export_markdown(qa_pairs, OUTPUT_DIR / "qa_pairs.md")
        print(f"✅ qa_pairs.md 已导出 ({count} 条)")

    ok = count > 0
    print(f"\n  {'✅ 通过标准达成：问答对可导出到文件' if ok else '❌ 未通过'}")


if __name__ == "__main__":
    main()
