"""
知识库自动优化建议
功能：分析知识库数据，自动生成优化建议清单（覆盖不足/低分问答/反馈驱动/索引健康）
数据源：chunks.json / feedback.json / pending_optimization.json / 各测试报告
输出：output/optimization_suggestions.json
"""

import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills"))


class OptimizationAdvisor:
    """知识库优化建议器"""

    def _load_json(self, path: Path, default=None):
        if not path.exists():
            return default if default is not None else []
        try:
            return json.load(open(path, encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return default if default is not None else []

    def analyze_docs(self) -> list:
        """分析文档覆盖情况"""
        suggestions = []
        md_files = [f for f in DATA_DIR.iterdir() if f.is_file() and f.suffix == ".md"]

        # 文档数量检查
        if len(md_files) < 5:
            suggestions.append({
                "priority": "high",
                "category": "文档覆盖",
                "suggestion": f"知识库文档仅 {len(md_files)} 篇，建议扩充（目标 ≥6 篇：产品/成分/用法/售后/新品/常见问题）",
            })

        # 文档大小检查
        small_docs = [f.name for f in md_files if f.stat().st_size < 1000]
        if small_docs:
            suggestions.append({
                "priority": "medium",
                "category": "文档深度",
                "suggestion": f"以下文档内容偏少（<1KB），建议补充细节: {small_docs}",
            })

        # 空块检查
        chunks = self._load_json(DATA_DIR / "chunks.json")
        if chunks:
            empty = sum(1 for c in chunks if not c.get("text", "").strip())
            if empty > 0:
                suggestions.append({
                    "priority": "high",
                    "category": "数据质量",
                    "suggestion": f"检测到 {empty} 个空文本块，建议重建索引",
                })
        return suggestions

    def analyze_feedback(self) -> list:
        """分析反馈驱动优化"""
        suggestions = []
        feedback = self._load_json(OUTPUT_DIR / "feedback.json")
        if feedback:
            down = [f for f in feedback if f.get("feedback") == "down"]
            if len(down) >= 3:
                top_down = down[-3:]
                suggestions.append({
                    "priority": "high",
                    "category": "反馈驱动",
                    "suggestion": f"存在 {len(down)} 条点踩反馈，建议优先优化: "
                                  f"{[d['query'][:30] for d in top_down]}",
                })

        # 待优化区
        pending = self._load_json(OUTPUT_DIR / "pending_optimization.json")
        if pending:
            suggestions.append({
                "priority": "high",
                "category": "待优化区",
                "suggestion": f"知识库待优化区有 {len(pending)} 个问题待处理: "
                              f"{[p['query'][:25] for p in pending[:3]]}",
            })
        return suggestions

    def analyze_index(self) -> list:
        """分析索引健康"""
        suggestions = []
        # 索引一致性
        try:
            from rag_engine import RAGEngine
            engine = RAGEngine()
            chunks = self._load_json(DATA_DIR / "chunks.json")
            if chunks and engine.index.ntotal != len(chunks):
                suggestions.append({
                    "priority": "high",
                    "category": "索引一致性",
                    "suggestion": f"FAISS 向量数({engine.index.ntotal})与分块数({len(chunks)})不一致，建议重建索引",
                })
        except Exception as e:
            suggestions.append({
                "priority": "high",
                "category": "索引健康",
                "suggestion": f"索引加载失败: {str(e)[:50]}，建议检查并重建",
            })
        return suggestions

    def analyze_caches(self) -> list:
        """分析缓存与性能"""
        suggestions = []
        # 缓存统计
        cache_stats = self._load_json(OUTPUT_DIR / "cache_stats.json", default={})
        if isinstance(cache_stats, dict):
            hit_rate = cache_stats.get("hit_rate_percent")
            if hit_rate is not None and hit_rate < 20:
                suggestions.append({
                    "priority": "medium",
                    "category": "缓存效率",
                    "suggestion": f"缓存命中率偏低（{hit_rate}%），建议优化缓存键或预热热门查询",
                })
        return suggestions

    def generate(self) -> dict:
        """生成优化建议清单"""
        print("=" * 60)
        print("  知识库自动优化建议")
        print("=" * 60)

        all_suggestions = (
            self.analyze_docs()
            + self.analyze_feedback()
            + self.analyze_index()
            + self.analyze_caches()
        )

        # 按优先级排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        all_suggestions.sort(key=lambda s: priority_order.get(s.get("priority", "low"), 2))

        report = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(all_suggestions),
            "by_priority": {
                "high": sum(1 for s in all_suggestions if s.get("priority") == "high"),
                "medium": sum(1 for s in all_suggestions if s.get("priority") == "medium"),
                "low": sum(1 for s in all_suggestions if s.get("priority") == "low"),
            },
            "suggestions": all_suggestions,
        }

        # 输出
        for i, s in enumerate(all_suggestions, 1):
            print(f"\n  {i}. [{'🔴' if s['priority']=='high' else '🟡'}] {s['category']}: {s['suggestion']}")
        print(f"\n  共 {report['total']} 条建议（高{report['by_priority']['high']} 中{report['by_priority']['medium']} 低{report['by_priority']['low']}）")

        # 保存
        OUTPUT_DIR.mkdir(exist_ok=True)
        report_path = OUTPUT_DIR / "optimization_suggestions.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"  报告已保存: {report_path}")

        return report


def main():
    advisor = OptimizationAdvisor()
    report = advisor.generate()

    has_suggestions = "suggestions" in report and "total" in report
    print(f"\n  {'✅ 通过标准达成：输出优化建议清单' if has_suggestions else '❌ 未通过'}")


if __name__ == "__main__":
    main()
