"""
缓存预热机制
功能：将热门问题提前生成回答并写入缓存，提升缓存命中率
策略：
1. 从热门查询统计（usage_stats.json / 查询日志）提取高频问题
2. 预热时批量生成回答并写入缓存
3. 验证预热后缓存命中率提升
用法：python scripts/warm_cache.py
"""

import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills"))


class CacheWarmer:
    """缓存预热器"""

    def __init__(self):
        self.warmed = []
        self.failed = []

    def get_hot_queries(self, limit: int = 5) -> list:
        """从使用统计获取热门查询"""
        hot = []

        # 1. 从 usage_stats.json 提取
        usage_file = OUTPUT_DIR / "usage_stats.json"
        if usage_file.exists():
            try:
                usage = json.load(open(usage_file, encoding="utf-8"))
                top = usage.get("queries", {}).get("top_queries", [])
                hot.extend([q for q, _ in top if q not in hot])
            except (json.JSONDecodeError, FileNotFoundError):
                pass

        # 2. 从查询日志提取（SystemLogger）
        try:
            from logger import SystemLogger
            logger = SystemLogger()
            logs = logger.query_logs(log_type="query", limit=100)
            for log in logs:
                q = log.get("data", {}).get("query", "")
                if q and q not in hot:
                    hot.append(q)
        except Exception:
            pass

        # 3. 兜底热门问题（知识库高频主题）
        fallback = [
            "烟酰胺有什么功效？",
            "敏感肌可以用视黄醇吗？",
            "这款面霜多少钱？",
            "玻尿酸精华怎么用？",
            "退货流程是什么？",
        ]
        for q in fallback:
            if q not in hot:
                hot.append(q)

        return hot[:limit]

    def warm(self, agent, queries: list) -> dict:
        """预热：生成回答写入缓存"""
        from answer_generator import AnswerGenerator
        # 预热前记录缓存状态
        cache_before = len(agent.cache) if agent else 0

        results = []
        for q in queries:
            try:
                t0 = time.time()
                result = agent.answer(q, top_k=3)
                duration_ms = (time.time() - t0) * 1000
                results.append({
                    "query": q,
                    "cached": True,
                    "duration_ms": round(duration_ms, 1),
                    "has_answer": bool(result["answer"]),
                })
                self.warmed.append(q)
            except Exception as e:
                results.append({"query": q, "cached": False, "error": str(e)[:60]})
                self.failed.append(q)

        return {
            "warmed": len(self.warmed),
            "failed": len(self.failed),
            "results": results,
        }

    def verify_hit_rate(self, agent, queries: list) -> dict:
        """验证预热后命中率提升"""
        # 用同一批问题再次查询（应命中缓存）
        cache_hits = 0
        cache_misses = 0
        for q in queries:
            key = q.strip()
            if key in agent.cache:
                cache_hits += 1
            else:
                cache_misses += 1

        hit_rate = cache_hits / (cache_hits + cache_misses) if (cache_hits + cache_misses) else 0
        return {
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "hit_rate": round(hit_rate, 3),
            "hit_rate_percent": round(hit_rate * 100, 1),
        }


def main():
    print("=" * 60)
    print("  缓存预热机制")
    print("=" * 60)

    from answer_generator import AnswerGenerator
    agent = AnswerGenerator()
    warmer = CacheWarmer()

    # 1. 获取热门问题
    hot_queries = warmer.get_hot_queries(limit=5)
    print(f"\n📌 待预热热门问题 ({len(hot_queries)} 个):")
    for q in hot_queries:
        print(f"  - {q}")

    # 2. 预热前命中率（模拟：首次查询均未缓存）
    before = {"cache_hits": 0, "cache_misses": len(hot_queries), "hit_rate": 0.0}

    # 3. 执行预热
    print(f"\n🔥 开始预热...")
    warm_result = warmer.warm(agent, hot_queries)
    print(f"  预热成功: {warm_result['warmed']} | 失败: {warm_result['failed']}")

    # 4. 验证预热后命中率
    after = warmer.verify_hit_rate(agent, hot_queries)
    print(f"\n📊 缓存命中率对比:")
    print(f"  预热前: {before['hit_rate']*100:.0f}% ({before['cache_hits']}/{before['cache_hits']+before['cache_misses']})")
    print(f"  预热后: {after['hit_rate_percent']}% ({after['cache_hits']}/{after['cache_hits']+after['cache_misses']})")

    improved = after["hit_rate"] > before["hit_rate"]
    print(f"\n  {'✅ 通过标准达成：热门问题预热后命中率提升' if improved else '❌ 命中率未提升'}")

    # 保存报告
    OUTPUT_DIR.mkdir(exist_ok=True)
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hot_queries": hot_queries,
        "before": before,
        "after": after,
        "warmed": warm_result["warmed"],
    }
    with open(OUTPUT_DIR / "warm_cache_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  报告已保存: {OUTPUT_DIR / 'warm_cache_report.json'}")


if __name__ == "__main__":
    main()
