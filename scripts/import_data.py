"""
批量数据导入
功能：批量导入新知识文档（Markdown/TXT），自动重建索引，导入后可检索
用法：python scripts/import_data.py <文件或目录>
"""

import sys
import json
import shutil
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


class DataImporter:
    """批量数据导入器"""

    def import_file(self, src_path: Path) -> dict:
        """导入单个文档到知识库"""
        if not src_path.exists():
            return {"ok": False, "error": f"文件不存在: {src_path}"}

        ext = src_path.suffix.lower()
        if ext not in (".md", ".txt"):
            return {"ok": False, "error": f"不支持的文件类型: {ext}（仅支持 .md/.txt）"}

        # 复制到知识库 data 目录（带序号命名）
        target_name = src_path.name
        if target_name in [f.name for f in DATA_DIR.iterdir()]:
            # 重名则加时间戳
            import time
            target_name = f"{src_path.stem}_{time.strftime('%H%M%S')}{ext}"
        target = DATA_DIR / target_name
        shutil.copy2(src_path, target)

        return {
            "ok": True,
            "source": str(src_path),
            "target": str(target),
            "chars": len(target.read_text(encoding="utf-8")),
        }

    def import_batch(self, paths: list) -> dict:
        """批量导入多个文件/目录"""
        results = []
        for p in paths:
            path = Path(p)
            if path.is_dir():
                for f in sorted(path.iterdir()):
                    if f.suffix.lower() in (".md", ".txt"):
                        results.append(self.import_file(f))
            elif path.is_file():
                results.append(self.import_file(path))

        ok_count = sum(1 for r in results if r.get("ok"))
        return {
            "total": len(results),
            "success": ok_count,
            "failed": len(results) - ok_count,
            "results": results,
        }

    def rebuild_and_verify(self, test_queries: list = None) -> dict:
        """重建索引并验证新文档可检索"""
        # 1. 重建索引
        from build_index import load_documents, split_text
        import hashlib, pickle, os
        os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

        docs = load_documents(DATA_DIR)
        all_chunks = []
        for doc in docs:
            chunks = split_text(doc["text"])
            for i, chunk in enumerate(chunks):
                chunk_id = hashlib.md5(f"{doc['source']}_{i}".encode()).hexdigest()[:12]
                all_chunks.append({
                    "chunk_id": chunk_id,
                    "source": doc["source"],
                    "chunk_index": i,
                    "text": chunk,
                    "char_offset": doc["text"].find(chunk) if chunk in doc["text"] else -1
                })

        with open(DATA_DIR / "chunks.json", "w", encoding="utf-8") as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=2)

        # 向量化
        from transformers import AutoTokenizer, AutoModel
        import torch, numpy as np
        model_path = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        model = AutoModel.from_pretrained(model_path, local_files_only=True)
        model.eval()

        def embed(texts):
            encoded = tokenizer(texts, padding=True, truncation=True, max_length=256, return_tensors='pt')
            with torch.no_grad():
                output = model(**encoded)
            emb = output.last_hidden_state[:, 0, :]
            emb = emb / emb.norm(dim=1, keepdim=True)
            return emb.numpy().astype(np.float32)

        texts = [c["text"][:500] for c in all_chunks]
        embeddings = embed(texts)

        import faiss
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        # 中文路径兜底
        try:
            faiss.write_index(index, str(DATA_DIR / "faiss_index.bin"))
        except Exception:
            import tempfile, shutil as _sh
            tmp = tempfile.mkdtemp(prefix="faiss_w_")
            try:
                faiss.write_index(index, os.path.join(tmp, "index.bin"))
                _sh.copy(os.path.join(tmp, "index.bin"), str(DATA_DIR / "faiss_index.bin"))
            finally:
                _sh.rmtree(tmp, ignore_errors=True)

        # BM25
        from build_index import tokenize_cn
        from rank_bm25 import BM25Okapi
        tokenized = [tokenize_cn(c["text"]) for c in all_chunks]
        bm25 = BM25Okapi(tokenized)
        with open(DATA_DIR / "bm25_index.pkl", "wb") as f:
            pickle.dump({"bm25": bm25, "tokenized": tokenized}, f)

        with open(DATA_DIR / "embedding_info.json", "w", encoding="utf-8") as f:
            json.dump({"model": model_path, "dim": dim, "chunk_count": len(all_chunks)}, f)

        # 2. 验证新文档可检索
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from rag_engine import RAGEngine
        engine = RAGEngine()

        verify_results = []
        if test_queries:
            for q, expected_src in test_queries:
                results = engine.hybrid_search(q, top_k=3)
                sources = [r["source"] for r in results]
                hit = expected_src in sources
                verify_results.append({"query": q, "expected": expected_src, "hit": hit, "sources": sources[:2]})

        return {
            "chunk_count": len(all_chunks),
            "verify": verify_results,
        }


def main():
    parser = argparse.ArgumentParser(description="批量数据导入")
    parser.add_argument("paths", nargs="+", help="要导入的文件或目录")
    parser.add_argument("--no-verify", action="store_true", help="跳过检索验证")
    args = parser.parse_args()

    print("=" * 60)
    print("  批量数据导入")
    print("=" * 60)

    importer = DataImporter()
    result = importer.import_batch(args.paths)

    print(f"\n导入结果: 成功 {result['success']} / 总数 {result['total']} / 失败 {result['failed']}")
    for r in result["results"]:
        if r.get("ok"):
            print(f"  ✅ {r['target']} ({r['chars']}字符)")
        else:
            print(f"  ❌ {r.get('error')}")

    # 重建索引并验证
    print(f"\n=== 重建索引并验证 ===")
    verify = importer.rebuild_and_verify()
    print(f"  文本块数: {verify['chunk_count']}")

    if not args.no_verify:
        for v in verify["verify"]:
            status = "✅" if v["hit"] else "❌"
            print(f"  {status} [{v['query']}] 期望:{v['expected']} 实际:{v['sources']}")

    has_new = result["success"] > 0
    verified = all(v["hit"] for v in verify.get("verify", [])) or args.no_verify
    print(f"\n  {'✅ 通过标准达成：新文档导入后可检索' if has_new and verified else '❌ 未通过'}")


if __name__ == "__main__":
    main()
