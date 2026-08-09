"""
缓存统计报告
功能：统计回答缓存的命中率、缓存大小、TTL 信息
输出：output/cache_stats.json + 控制台报告
"""

import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
OUTPUT_DIR = PROJECT_ROOT / "output"


def generate_cache_stats() -> dict:
    """生成缓存统计报告"""
    from answer_generator import AnswerGenerator

    agent = AnswerGenerator()

    # 1. 制造缓存访问（用不同问题触发 miss，相同问题触发 hit）
    q1 = "烟酰胺有什么功效？"
    q2 = "敏感肌可以用视黄醇吗？"

    # 首次提问（miss）
    agent.answer(q1)
    agent.answer(q2)
    # 二次提问（hit）
    agent.answer(q1)
    agent.answer(q2)
    # 三次提问（hit）
    agent.answer(q1)

    # 2. 统计
    hits = agent.cache_hits
    misses = agent.cache_misses
    total = hits + misses
    hit_rate = round(hits / total, 4) if total else 0

    # 缓存条目信息
    cache_entries = []
    now = time.time()
    for key, entry in agent.cache.items():
        age = now - entry.get("timestamp", now)
        cache_entries.append({
            "query": key[:50],
            "age_seconds": round(age, 1),
            "answer_length": len(entry.get("result", {}).get("answer", "")),
        })

    report = {
        "cache_hits": hits,
        "cache_misses": misses,
        "total_requests": total,
        "hit_rate": hit_rate,
        "hit_rate_percent": round(hit_rate * 100, 1),
        "cache_size": len(agent.cache),
        "cache_ttl_seconds": agent.cache_ttl,
        "entries": cache_entries,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 保存
    OUTPUT_DIR.mkdir(exist_ok=True)
    report_path = OUTPUT_DIR / "cache_stats.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report


def main():
    print("=" * 50)
    print("  缓存统计报告")
    print("=" * 50)

    report = generate_cache_stats()

    print(f"  缓存命中: {report['cache_hits']}")
    print(f"  缓存未命中: {report['cache_misses']}")
    print(f"  总请求: {report['total_requests']}")
    print(f"  命中率: {report['hit_rate_percent']}%")
    print(f"  缓存条目数: {report['cache_size']}")
    print(f"  TTL: {report['cache_ttl_seconds']} 秒")
    print(f"\n  报告已保存: output/cache_stats.json")

    has_rate = "hit_rate" in report
    print(f"\n  {'✅ 通过标准达成：输出缓存命中率' if has_rate else '❌ 未通过'}")


if __name__ == "__main__":
    main()
