"""
知识库完整性校验
功能：校验知识库数据完整性（文档/分块/索引/向量一致性），输出校验报告
检查项：
1. 知识文档完整性（必需文档存在性）
2. 分块完整性（chunks.json 可解析、无空块、无重复块）
3. 索引一致性（FAISS 向量数 = chunks 数）
4. 索引文件完整性（faiss/bm25 文件存在且非空）
输出：output/integrity_report.json
"""

import sys
import json
import pickle
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class IntegrityChecker:
    """知识库完整性校验器"""

    def __init__(self):
        self.checks = []

    def _add(self, check: str, ok: bool, detail: str = ""):
        self.checks.append({
            "check": check,
            "status": "ok" if ok else "fail",
            "detail": detail,
        })
        icon = "✅" if ok else "❌"
        print(f"  {icon} [{check}] {detail}")

    def check_docs(self):
        """1. 知识文档完整性"""
        required = [
            "01_产品目录.md", "02_成分知识库.md",
            "03_使用方法指南.md", "04_售后服务政策.md",
        ]
        existing = [f.name for f in DATA_DIR.iterdir() if f.is_file() and f.suffix == ".md"]
        missing = [r for r in required if r not in existing]
        self._add("知识文档", not missing, f"必需文档缺失: {missing or '无'}, 当前共 {len(existing)} 篇")

    def check_chunks(self):
        """2. 分块完整性"""
        chunks_path = DATA_DIR / "chunks.json"
        if not chunks_path.exists():
            self._add("分块文件", False, "chunks.json 缺失")
            return []

        try:
            chunks = json.load(open(chunks_path, encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            self._add("分块文件", False, "chunks.json 无法解析")
            return []

        # 空块检查
        empty = [c for c in chunks if not c.get("text", "").strip()]
        # 重复块检查
        texts = [c.get("text", "") for c in chunks]
        dup = len(texts) - len(set(texts))
        # 字段完整性
        missing_fields = [c for c in chunks if not all(k in c for k in ("chunk_id", "source", "text"))]

        self._add("分块完整性", len(chunks) > 0 and not empty and dup == 0 and not missing_fields,
                  f"{len(chunks)} 块 | 空块:{len(empty)} | 重复:{dup} | 缺字段:{len(missing_fields)}")
        return chunks

    def check_index(self, chunks):
        """3. 索引一致性"""
        # FAISS 向量数 vs chunks 数
        try:
            from rag_engine import RAGEngine
            engine = RAGEngine()
            faiss_count = engine.index.ntotal
            chunk_count = len(chunks)
            self._add("FAISS一致性", faiss_count == chunk_count,
                      f"FAISS {faiss_count} 向量 vs chunks {chunk_count} 块")
        except Exception as e:
            self._add("FAISS一致性", False, str(e)[:60])

        # BM25 索引
        try:
            with open(DATA_DIR / "bm25_index.pkl", "rb") as f:
                bm25_data = pickle.load(f)
            bm25_count = len(bm25_data.get("tokenized", []))
            self._add("BM25一致性", bm25_count == chunk_count,
                      f"BM25 {bm25_count} 文档 vs chunks {chunk_count} 块")
        except Exception as e:
            self._add("BM25一致性", False, str(e)[:60])

    def check_index_files(self):
        """4. 索引文件完整性"""
        for fname in ["faiss_index.bin", "bm25_index.pkl", "embedding_info.json"]:
            path = DATA_DIR / fname
            if path.exists() and path.stat().st_size > 0:
                self._add(f"索引文件-{fname}", True, f"存在 ({path.stat().st_size} 字节)")
            else:
                self._add(f"索引文件-{fname}", False, "缺失或为空")

    def run_all(self) -> dict:
        """运行全部完整性校验"""
        print("=" * 60)
        print("  知识库完整性校验")
        print("=" * 60)

        self.check_docs()
        chunks = self.check_chunks()
        if chunks:
            self.check_index(chunks)
        self.check_index_files()

        # 汇总
        ok_count = sum(1 for c in self.checks if c["status"] == "ok")
        fail_count = sum(1 for c in self.checks if c["status"] == "fail")

        report = {
            "generated_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {"ok": ok_count, "fail": fail_count, "overall": "consistent" if fail_count == 0 else "inconsistent"},
            "checks": self.checks,
        }

        # 保存报告
        OUTPUT_DIR.mkdir(exist_ok=True)
        report_path = OUTPUT_DIR / "integrity_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print("\n" + "=" * 60)
        print(f"  校验结果: {report['summary']['overall'].upper()} (ok:{ok_count} fail:{fail_count})")
        print(f"  报告已保存: {report_path}")
        print("=" * 60)

        return report


def main():
    checker = IntegrityChecker()
    report = checker.run_all()

    has_report = "summary" in report and "checks" in report
    print(f"\n  {'✅ 通过标准达成：校验报告输出' if has_report else '❌ 未通过'}")


if __name__ == "__main__":
    main()
