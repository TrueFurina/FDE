"""
知识库向量化脚本
功能：读取 data/*.md 知识文档 → 分块 → 向量化 → 保存 FAISS 索引 + BM25 索引
输出：
- data/faiss_index.bin       - FAISS 向量索引
- data/chunks.json           - 文本块及元数据
- data/bm25_index.pkl        - BM25 索引
"""

import os
import json
import pickle
import re
import hashlib
import numpy as np
from pathlib import Path

# ============ 配置 ============
DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = DATA_DIR
CHUNK_SIZE = 300      # 字符数
CHUNK_OVERLAP = 50    # 重叠字符数

# ============ 文档加载 ============
def load_documents(data_dir: Path):
    """读取 data 目录下所有 .md 文档"""
    docs = []
    for f in sorted(data_dir.glob("*.md")):
        if "README" in f.name:
            continue
        text = f.read_text(encoding="utf-8")
        # 跳过空文件
        if len(text.strip()) < 50:
            continue
        docs.append({"source": f.name, "text": text})
    print(f"加载 {len(docs)} 篇知识文档")
    return docs

# ============ 文本分块（标题感知）============
def split_by_headings(text: str):
    """按 Markdown 标题切分文档，返回 (标题路径, 内容) 列表"""
    lines = text.split("\n")
    sections = []
    current_headers = []  # 标题路径栈
    current_content = []
    current_header = ""

    for line in lines:
        # 检测标题行
        if line.strip().startswith("#"):
            # 保存上一个 section
            if current_header or current_content:
                sections.append((current_header, "\n".join(current_content).strip()))
            # 提取标题级别和文本
            match = re.match(r'^(#{1,4})\s+(.*)', line.strip())
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                # 维护标题路径栈
                current_headers = current_headers[:level-1]
                while len(current_headers) < level - 1:
                    current_headers.append("")
                current_headers.append(title)
                current_header = " > ".join([h for h in current_headers if h])
            else:
                current_header = line.strip()
            current_content = []
        else:
            current_content.append(line)

    # 最后一个 section
    if current_header or current_content:
        sections.append((current_header, "\n".join(current_content).strip()))

    # 过滤空 section
    return [(h, c) for h, c in sections if c.strip()]

def split_text(text: str, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """标题感知分块：优先按标题切，超长标题下再按字符切，保留标题上下文"""
    sections = split_by_headings(text)
    chunks = []

    for header, content in sections:
        # 短内容：直接作为一个块（带标题前缀）
        if len(content) <= chunk_size * 1.5:
            chunk = f"{header}\n{content}" if header else content
            if chunk.strip():
                chunks.append(chunk.strip())
            continue

        # 长内容：按行再切，但保持表格行完整
        lines = content.split("\n")
        current = []
        current_len = 0
        for line in lines:
            line_len = len(line)
            if current_len + line_len > chunk_size and current:
                chunk = f"{header}\n" + "\n".join(current)
                chunks.append(chunk.strip())
                current = [line]
                current_len = line_len
            else:
                current.append(line)
                current_len += line_len
        if current:
            chunk = f"{header}\n" + "\n".join(current)
            chunks.append(chunk.strip())

    return [c for c in chunks if c.strip()]

def build_chunks(docs):
    """为所有文档生成文本块"""
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
                # 定位信息：文档内大致位置
                "char_offset": doc["text"].find(chunk) if chunk in doc["text"] else -1
            })
    print(f"共生成 {len(all_chunks)} 个文本块")
    return all_chunks

# ============ 向量化 ============
def get_embeddings(chunks, model_name="paraphrase-multilingual-MiniLM-L12-v2"):
    """使用 sentence-transformers 生成嵌入向量"""
    print(f"加载嵌入模型: {model_name}...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)
    
    texts = [c["text"][:500] for c in chunks]  # 截断过长文本
    print(f"向量化 {len(texts)} 个文本块...")
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    print(f"嵌入维度: {embeddings.shape[1]}")
    return np.array(embeddings, dtype=np.float32)

# ============ 保存索引 ============
def build_faiss_index(embeddings, output_dir):
    """构建并保存 FAISS 索引"""
    import faiss
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # 内积相似度（归一化后 = 余弦相似度）
    index.add(embeddings)
    faiss.write_index(index, str(output_dir / "faiss_index.bin"))
    print(f"FAISS 索引已保存: {output_dir / 'faiss_index.bin'}")

def tokenize_cn(text):
    """中文分词：单字 + 2-gram + 3-gram 组合（与 rag_engine._tokenize 一致）"""
    words = re.findall(r'[a-zA-Z0-9]+', text.lower())
    chinese_runs = re.findall(r'[\u4e00-\u9fff]+', text)
    tokens = words
    for run in chinese_runs:
        tokens.extend(list(run))
        tokens.extend(run[i:i+2] for i in range(len(run) - 1))
        tokens.extend(run[i:i+3] for i in range(len(run) - 2))
    return tokens

def build_bm25_index(chunks, output_dir):
    """构建并保存 BM25 索引"""
    from rank_bm25 import BM25Okapi
    # 中文分词：单字+2-gram+3-gram
    tokenized = [tokenize_cn(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized)
    with open(output_dir / "bm25_index.pkl", "wb") as f:
        pickle.dump({"bm25": bm25, "tokenized": tokenized}, f)
    print(f"BM25 索引已保存: {output_dir / 'bm25_index.pkl'}")

def main():
    print("=" * 50)
    print("  知识库向量化脚本")
    print("=" * 50)
    
    # 1. 加载文档
    docs = load_documents(DATA_DIR)
    if not docs:
        print("❌ 未找到知识文档！")
        return
    
    # 2. 分块
    chunks = build_chunks(docs)
    
    # 3. 保存 chunks 元数据
    with open(OUTPUT_DIR / "chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"chunks.json 已保存（{len(chunks)} 块）")
    
    # 4. 向量化
    embeddings = get_embeddings(chunks)
    
    # 5. 构建 FAISS + BM25
    build_faiss_index(embeddings, OUTPUT_DIR)
    build_bm25_index(chunks, OUTPUT_DIR)
    
    print("=" * 50)
    print("  ✅ 向量化完成！")
    print(f"  知识文档: {len(docs)} 篇")
    print(f"  文本块: {len(chunks)} 块")
    print(f"  嵌入维度: {embeddings.shape[1]}")
    print("=" * 50)

if __name__ == "__main__":
    main()
