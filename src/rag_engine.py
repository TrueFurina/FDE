"""
RAG 混合检索引擎
功能：FAISS 向量检索 + BM25 关键词检索 + RRF 融合排序
输入：查询文本
输出：Top-K 相关文本块（含来源标注）
"""

import json
import pickle
import re
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import faiss
from rank_bm25 import BM25Okapi

# 离线加载嵌入模型（模型已缓存）
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'


class RAGEngine:
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = str(Path(__file__).parent.parent / "data")
        self.data_dir = Path(data_dir)

        # 1. 加载 chunks 元数据
        with open(self.data_dir / "chunks.json", encoding="utf-8") as f:
            self.chunks = json.load(f)
        self.chunk_texts = [c["text"] for c in self.chunks]

        # 2. 加载 FAISS 索引（Windows 中文路径兼容）
        self.index = self._load_faiss_index()

        # 3. 加载 BM25 索引
        with open(self.data_dir / "bm25_index.pkl", "rb") as f:
            bm25_data = pickle.load(f)
        self.bm25 = bm25_data["bm25"]
        self.bm25_tokenized = bm25_data["tokenized"]

        # 4. 加载嵌入模型（延迟初始化）
        self._embedder = None

    def _load_faiss_index(self):
        """加载 FAISS 索引，处理 Windows 中文路径问题"""
        index_path = self.data_dir / "faiss_index.bin"
        try:
            # 直接读取（ASCII 路径下有效）
            return faiss.read_index(str(index_path))
        except Exception:
            # 中文路径 fallback：复制到临时 ASCII 路径再读
            tmp_dir = tempfile.mkdtemp(prefix="faiss_")
            try:
                tmp_path = os.path.join(tmp_dir, "index.bin")
                shutil.copy(str(index_path), tmp_path)
                return faiss.read_index(tmp_path)
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def _get_embedder(self):
        """延迟加载嵌入模型"""
        if self._embedder is None:
            from transformers import AutoTokenizer, AutoModel
            import torch
            model_path = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            self._tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
            self._model = AutoModel.from_pretrained(model_path, local_files_only=True)
            self._model.eval()
            self._torch = torch
            self._embedder = "loaded"
        return self._embedder

    def _embed(self, texts):
        """文本向量化"""
        self._get_embedder()
        import torch
        encoded = self._tokenizer(texts, padding=True, truncation=True, max_length=256, return_tensors='pt')
        with torch.no_grad():
            output = self._model(**encoded)
        embeddings = output.last_hidden_state[:, 0, :]
        embeddings = embeddings / embeddings.norm(dim=1, keepdim=True)
        return embeddings.numpy().astype(np.float32)

    def _tokenize(self, text):
        """中文分词：成分感知（优先词库词）+ 单字/2-gram/3-gram 兜底"""
        # 使用成分词库分词器（领域词典优先）
        try:
            from ingredient_dict import IngredientTokenizer
            tk = IngredientTokenizer()
            return tk.tokenize(text)
        except ImportError:
            # 兜底：单字 + 2-gram + 3-gram
            return self._tokenize_fallback(text)

    @staticmethod
    def _tokenize_fallback(text):
        """兜底分词：单字 + 2-gram + 3-gram"""
        words = re.findall(r'[a-zA-Z0-9]+', text.lower())
        chinese_runs = re.findall(r'[\u4e00-\u9fff]+', text)
        tokens = words
        for run in chinese_runs:
            tokens.extend(list(run))
            tokens.extend(run[i:i+2] for i in range(len(run) - 1))
            tokens.extend(run[i:i+3] for i in range(len(run) - 2))
        return tokens

    def _vector_search(self, query, top_k=10):
        """FAISS 向量检索"""
        q_emb = self._embed([query])
        scores, indices = self.index.search(q_emb, top_k)
        return indices[0], scores[0]

    def _bm25_search(self, query, top_k=10):
        """BM25 关键词检索"""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return np.array([], dtype=int), np.array([])
        scores = self.bm25.get_scores(query_tokens)
        top_indices = np.argsort(scores)[::-1][:top_k]
        top_scores = scores[top_indices]
        return top_indices, top_scores

    @staticmethod
    def _rrf_score_weighted(ranks_dict, k_dict=None):
        """RRF 融合排序（支持每路不同权重，k 越小权重越高）"""
        if k_dict is None:
            k_dict = {src: 60 for src in ranks_dict}
        score = {}
        for source, ranks in ranks_dict.items():
            k = k_dict.get(source, 60)
            for i, doc_idx in enumerate(ranks):
                if doc_idx not in score:
                    score[doc_idx] = 0
                score[doc_idx] += 1.0 / (k + i + 1)
        return sorted(score.items(), key=lambda x: -x[1])

    @staticmethod
    def _rrf_score(ranks_dict, k=60):
        """RRF 融合排序（默认权重）"""
        return RAGEngine._rrf_score_weighted(ranks_dict, {src: k for src in ranks_dict})

    def hybrid_search(self, query, top_k=5, vector_top=10, bm25_top=10, vec_threshold=0.5):
        """混合检索：向量 + BM25 + RRF
        vec_threshold: 向量检索相似度阈值，低于此值的向量结果不参与 RRF（过滤噪声）
        BM25 权重显著更高（k=20），因为关键词精确匹配对成分/产品名更可靠
        """
        # 1. 两个检索器并行
        vec_indices, vec_scores = self._vector_search(query, vector_top)
        bm25_indices, bm25_scores = self._bm25_search(query, bm25_top)

        # 2. 过滤低分向量结果（避免噪声干扰 RRF 融合）
        valid_vec = [
            idx for idx, sc in zip(vec_indices, vec_scores)
            if sc >= vec_threshold
        ]

        # 2.5 向量结果按来源文档去重（每文档只保留最高分 chunk，防止同文档噪声在 RRF 累计）
        seen_sources = set()
        dedup_vec = []
        for idx in valid_vec:
            src = self.chunks[idx]["source"]
            if src not in seen_sources:
                seen_sources.add(src)
                dedup_vec.append(idx)
        valid_vec = dedup_vec

        # 3. RRF 融合（BM25 权重更高：k=20；向量 k=60）
        ranks_dict = {
            "vector": valid_vec,
            "bm25": list(bm25_indices),
        }
        fused = self._rrf_score_weighted(ranks_dict, {"vector": 60, "bm25": 20})

        # 4. 取 Top-K，附加来源信息
        results = []
        for doc_idx, rrf_score in fused[:top_k]:
            if doc_idx >= len(self.chunks):
                continue
            chunk = self.chunks[doc_idx]
            results.append({
                "chunk_id": chunk["chunk_id"],
                "source": chunk["source"],
                "chunk_index": chunk["chunk_index"],
                "text": chunk["text"],
                "rrf_score": round(float(rrf_score), 4),
                # 各检索器贡献（诊断用）
                "vec_rank": int(np.where(vec_indices == doc_idx)[0][0]) + 1 if doc_idx in vec_indices else None,
                "bm25_rank": int(np.where(bm25_indices == doc_idx)[0][0]) + 1 if doc_idx in bm25_indices else None,
            })
        return results

    def search_with_details(self, query, top_k=5):
        """返回检索结果及两种检索器单独结果（用于评估）"""
        vec_indices, vec_scores = self._vector_search(query, top_k)
        bm25_indices, bm25_scores = self._bm25_search(query, top_k)

        vector_results = []
        for idx, score in zip(vec_indices, vec_scores):
            if idx < len(self.chunks):
                vector_results.append({
                    "source": self.chunks[idx]["source"],
                    "text": self.chunks[idx]["text"][:60],
                    "score": round(float(score), 4)
                })

        bm25_results = []
        for idx, score in zip(bm25_indices, bm25_scores):
            if idx < len(self.chunks):
                bm25_results.append({
                    "source": self.chunks[idx]["source"],
                    "text": self.chunks[idx]["text"][:60],
                    "score": round(float(score), 4)
                })

        return {
            "query": query,
            "vector": vector_results,
            "bm25": bm25_results,
            "hybrid": self.hybrid_search(query, top_k)
        }


if __name__ == "__main__":
    print("=" * 50)
    print("  RAG 混合检索引擎 - 自测")
    print("=" * 50)
    engine = RAGEngine()

    test_queries = [
        "烟酰胺有什么功效？",
        "这款面霜多少钱？",
        "敏感肌可以用视黄醇吗？",
        "拆封了还能退吗？",
        "这款产品可以治疗痘痘吗？"
    ]

    for q in test_queries:
        print(f"\n🔍 查询: {q}")
        results = engine.hybrid_search(q, top_k=3)
        for r in results:
            print(f"  [{r['source']}#{r['chunk_index']}] {r['text'][:50]}... (rrf={r['rrf_score']})")

    print("\n" + "=" * 50)
    print("  ✅ RAG 引擎自测完成")
    print("=" * 50)
