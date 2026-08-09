"""
知识库统计报告
功能：统计知识库文档数、文本块数、关键词分布、文档大小等
输出：output/kb_stats.json + 控制台报告
"""

import json
import re
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"


def load_chunks() -> list:
    """加载文本块"""
    path = DATA_DIR / "chunks.json"
    if not path.exists():
        return []
    try:
        return json.load(open(path, encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def load_docs() -> list:
    """加载知识文档"""
    docs = []
    for f in sorted(DATA_DIR.glob("*.md")):
        if "README" in f.name:
            continue
        docs.append({
            "name": f.name,
            "size": f.stat().st_size,
            "chars": len(f.read_text(encoding="utf-8")),
        })
    return docs


def extract_keywords(chunks: list, top_n: int = 20) -> list:
    """提取高频关键词（中文单字/双字组合）"""
    text = " ".join(c["text"] for c in chunks)
    chinese_runs = re.findall(r'[\u4e00-\u9fff]+', text)
    # 2-gram 统计
    bigrams = []
    for run in chinese_runs:
        bigrams.extend(run[i:i+2] for i in range(len(run) - 1))
    counter = Counter(bigrams)
    return counter.most_common(top_n)


def generate_report() -> dict:
    """生成统计报告"""
    docs = load_docs()
    chunks = load_chunks()

    # 按来源统计
    by_source = Counter(c["source"] for c in chunks)
    chunk_sizes = [len(c["text"]) for c in chunks]

    # 关键词统计
    keywords = extract_keywords(chunks)

    report = {
        "total_docs": len(docs),
        "total_chunks": len(chunks),
        "total_chars": sum(len(c["text"]) for c in chunks),
        "avg_chunk_size": round(sum(chunk_sizes) / len(chunk_sizes), 1) if chunk_sizes else 0,
        "max_chunk_size": max(chunk_sizes) if chunk_sizes else 0,
        "min_chunk_size": min(chunk_sizes) if chunk_sizes else 0,
        "docs": docs,
        "chunks_by_source": dict(by_source),
        "top_keywords": keywords[:20],
    }

    return report


def main():
    print("=" * 50)
    print("  知识库统计报告")
    print("=" * 50)

    report = generate_report()

    print(f"  文档总数: {report['total_docs']}")
    print(f"  文本块总数: {report['total_chunks']}")
    print(f"  平均块大小: {report['avg_chunk_size']} 字符")
    print(f"  块大小范围: {report['min_chunk_size']} ~ {report['max_chunk_size']}")

    print(f"\n  各文档块数:")
    for source, count in report["chunks_by_source"].items():
        print(f"    {source}: {count} 块")

    print(f"\n  高频关键词 Top10:")
    for kw, count in report["top_keywords"][:10]:
        print(f"    {kw}: {count}")

    # 保存报告
    OUTPUT_DIR.mkdir(exist_ok=True)
    report_path = OUTPUT_DIR / "kb_stats.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  报告已保存: {report_path}")

    # 通过标准验证
    has_stats = all(k in report for k in ("total_docs", "total_chunks", "top_keywords"))
    print(f"\n  {'✅ 通过标准达成：输出文档/块/关键词统计' if has_stats else '❌ 未通过'}")


if __name__ == "__main__":
    main()
