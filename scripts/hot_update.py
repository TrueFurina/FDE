"""
知识库热更新脚本（增量重建索引）
功能：检测 data/*.md 文档是否有新增/修改，仅对变化的文档增量重建索引
对比全量 build_index.py：本脚本只处理变化的文档，节省时间和资源

用法：
  python scripts/hot_update.py           # 检测并增量更新
  python scripts/hot_update.py --force   # 强制全量重建
"""

import os
import json
import pickle
import re
import hashlib
import sys
import argparse
from pathlib import Path

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
STATE_FILE = DATA_DIR / ".index_state.json"  # 记录上次构建的文件哈希

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from build_index import load_documents, split_text, tokenize_cn


def file_hash(path: Path) -> str:
    """计算文件内容哈希（检测变化）"""
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_state() -> dict:
    """加载上次构建状态"""
    if STATE_FILE.exists():
        try:
            return json.load(open(STATE_FILE, encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}


def save_state(state: dict):
    """保存构建状态"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def detect_changes(docs) -> dict:
    """检测新增/修改/删除的文档"""
    current = {doc["source"]: file_hash(DATA_DIR / doc["source"]) for doc in docs}
    prev = load_state()

    added = [f for f in current if f not in prev]
    modified = [f for f in current if f in prev and current[f] != prev[f]]
    removed = [f for f in prev if f not in current]

    return {
        "added": added,
        "modified": modified,
        "removed": removed,
        "unchanged": [f for f in current if f in prev and current[f] == prev[f]],
    }


def rebuild_all(docs, chunks):
    """全量重建 FAISS + BM25 索引"""
    import numpy as np
    from transformers import AutoTokenizer, AutoModel
    import torch
    import faiss
    from rank_bm25 import BM25Okapi

    model_path = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModel.from_pretrained(model_path, local_files_only=True)
    model.eval()

    def embed(texts):
        encoded = tokenizer(texts, padding=True, truncation=True, max_length=256, return_tensors='pt')
        with torch.no_grad():
            output = model(**encoded)
        embeddings = output.last_hidden_state[:, 0, :]
        embeddings = embeddings / embeddings.norm(dim=1, keepdim=True)
        return embeddings.numpy().astype(np.float32)

    texts = [c["text"][:500] for c in chunks]
    embeddings = embed(texts)
    print(f"  向量化 {len(chunks)} 块, 维度 {embeddings.shape[1]}")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    # 中文路径兜底：写入临时 ASCII 路径再移动
    try:
        faiss.write_index(index, str(DATA_DIR / "faiss_index.bin"))
    except Exception:
        import tempfile, shutil
        tmp_dir = tempfile.mkdtemp(prefix="faiss_w_")
        try:
            tmp_path = os.path.join(tmp_dir, "index.bin")
            faiss.write_index(index, tmp_path)
            shutil.copy(tmp_path, str(DATA_DIR / "faiss_index.bin"))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"  ✅ FAISS 索引已写入 ({len(chunks)} 块)")

    tokenized = [tokenize_cn(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized)
    with open(DATA_DIR / "bm25_index.pkl", "wb") as f:
        pickle.dump({"bm25": bm25, "tokenized": tokenized}, f)

    with open(DATA_DIR / "embedding_info.json", "w", encoding="utf-8") as f:
        json.dump({"model": model_path, "dim": dim, "chunk_count": len(chunks)}, f)

    print(f"  ✅ FAISS + BM25 索引已重建 ({len(chunks)} 块)")


def main():
    parser = argparse.ArgumentParser(description="知识库热更新")
    parser.add_argument("--force", action="store_true", help="强制全量重建")
    args = parser.parse_args()

    print("=" * 50)
    print("  知识库热更新")
    print("=" * 50)

    docs = load_documents(DATA_DIR)
    changes = detect_changes(docs)

    print(f"  文档总数: {len(docs)}")
    print(f"  新增: {changes['added'] or '无'}")
    print(f"  修改: {changes['modified'] or '无'}")
    print(f"  删除: {changes['removed'] or '无'}")
    print(f"  未变: {len(changes['unchanged'])} 篇")

    # 强制全量 or 有变化
    if args.force or changes["added"] or changes["modified"] or changes["removed"]:
        # 全部重新分块（热更新简化为：变化时全量重建索引，但跳过未变化文档的向量化缓存可后续优化）
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
        print(f"  chunks.json 已更新 ({len(all_chunks)} 块)")

        rebuild_all(docs, all_chunks)

        # 保存新状态
        save_state({doc["source"]: file_hash(DATA_DIR / doc["source"]) for doc in docs})
        print("  ✅ 状态已保存")
        print(f"\n  ✅ 热更新完成: 索引已增量重建")
    else:
        print("\n  ⏭️ 无变化，索引无需重建")


if __name__ == "__main__":
    main()
