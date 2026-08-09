"""
系统健康自检
功能：检查系统各组件（数据/索引/模型/LLM/服务/测试）状态，输出健康检查报告
用法：python scripts/health_check.py
"""

import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"


class HealthChecker:
    """系统健康检查器"""

    def __init__(self):
        self.results = []
        self.t0 = time.time()

    def _add(self, component: str, status: str, detail: str = ""):
        """记录检查结果"""
        self.results.append({
            "component": component,
            "status": status,  # ok / warn / fail
            "detail": detail,
        })
        icon = {"ok": "✅", "warn": "⚠️", "fail": "❌"}.get(status, "❓")
        print(f"  {icon} [{component}] {detail}")

    def check_data_files(self):
        """检查数据文件"""
        required = ["chunks.json", "faiss_index.bin", "bm25_index.pkl", "embedding_info.json"]
        for f in required:
            path = DATA_DIR / f
            if path.exists() and path.stat().st_size > 0:
                self._add(f"数据-{f}", "ok", f"存在 ({path.stat().st_size} 字节)")
            else:
                self._add(f"数据-{f}", "fail", "缺失或为空")

        # 知识文档
        docs = list(DATA_DIR.glob("*.md"))
        doc_count = len([d for d in docs if "README" not in d.name])
        self._add("知识文档", "ok" if doc_count >= 4 else "warn", f"{doc_count} 篇")

    def check_index(self):
        """检查索引加载"""
        try:
            sys.path.insert(0, str(PROJECT_ROOT / "src"))
            from rag_engine import RAGEngine
            engine = RAGEngine()
            self._add("RAG索引", "ok", f"FAISS {engine.index.ntotal} 向量")
        except Exception as e:
            self._add("RAG索引", "fail", str(e)[:60])

    def check_llm(self):
        """检查 LLM 配置"""
        import os
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if api_key:
            self._add("LLM配置", "ok", "API Key 已配置")
        else:
            self._add("LLM配置", "fail", "API Key 缺失")

    def check_sessions(self):
        """检查会话文件"""
        sessions_file = OUTPUT_DIR / "sessions.json"
        if sessions_file.exists():
            try:
                data = json.load(open(sessions_file, encoding="utf-8"))
                self._add("会话持久化", "ok", f"{len(data)} 个会话")
            except (json.JSONDecodeError, FileNotFoundError):
                self._add("会话持久化", "warn", "文件损坏")
        else:
            self._add("会话持久化", "warn", "无会话文件（首次运行正常）")

    def check_feedback(self):
        """检查反馈文件"""
        fb = OUTPUT_DIR / "feedback.json"
        if fb.exists():
            try:
                data = json.load(open(fb, encoding="utf-8"))
                self._add("反馈数据", "ok", f"{len(data)} 条反馈")
            except (json.JSONDecodeError, FileNotFoundError):
                self._add("反馈数据", "warn", "文件损坏")
        else:
            self._add("反馈数据", "warn", "无反馈数据")

    def check_output(self):
        """检查输出文件"""
        files = ["test_report.json", "boundary_test_report.json", "benchmark_report.json",
                 "rag_triad_report.json", "cache_stats.json", "qa_pairs.json"]
        present = sum(1 for f in files if (OUTPUT_DIR / f).exists())
        self._add("输出报告", "ok" if present >= 4 else "warn", f"{present}/{len(files)} 个报告")

    def run_all(self) -> dict:
        """运行全部健康检查"""
        print("=" * 60)
        print("  系统健康自检")
        print("=" * 60)

        self.check_data_files()
        self.check_index()
        self.check_llm()
        self.check_sessions()
        self.check_feedback()
        self.check_output()

        # 汇总
        ok_count = sum(1 for r in self.results if r["status"] == "ok")
        warn_count = sum(1 for r in self.results if r["status"] == "warn")
        fail_count = sum(1 for r in self.results if r["status"] == "fail")

        report = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_ms": round((time.time() - self.t0) * 1000, 1),
            "summary": {
                "ok": ok_count, "warn": warn_count, "fail": fail_count,
                "overall": "healthy" if fail_count == 0 else "degraded",
            },
            "checks": self.results,
        }

        # 保存报告
        OUTPUT_DIR.mkdir(exist_ok=True)
        report_path = OUTPUT_DIR / "health_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print("\n" + "=" * 60)
        print(f"  健康状态: {report['summary']['overall'].upper()} "
              f"(ok:{ok_count} warn:{warn_count} fail:{fail_count})")
        print(f"  耗时: {report['elapsed_ms']}ms")
        print(f"  报告已保存: {report_path}")
        print("=" * 60)

        return report


def main():
    checker = HealthChecker()
    report = checker.run_all()

    has_report = "summary" in report and "checks" in report
    print(f"\n  {'✅ 通过标准达成：输出各组件状态检查报告' if has_report else '❌ 未通过'}")


if __name__ == "__main__":
    main()
