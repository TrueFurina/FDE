# Beauty-Retail Knowledge Base & Customer-Service Collaboration System

[English](./README.md) | [中文](./README.zh.md)

> FDE Co-learning Camp capstone project | Beauty-retail AI knowledge base & customer-service assistant
> Built on RAG hybrid retrieval + intent routing + compliance guardrails + grounding anti-hallucination

## 📋 Project Overview

An AI assistant system for customer service and sales staff at beauty-retail businesses, addressing scattered knowledge, time-consuming lookups, inconsistent answers, and compliance risks.

**The real problem it targets:** cut the time to train a new agent to a veteran level from 2–4 weeks down to under 1 week, with consistent, compliant, and traceable replies.

## 🏗️ System Architecture

```
User question
  ↓
Intent recognition & routing (6 intent classes + high-risk human handoff)
  ↓
RAG hybrid retrieval (FAISS vectors + BM25 keywords + RRF fusion)
  ↓
Query rewriting + retry (auto rewrites when retrieval quality is low)
  ↓
Answer generation (DeepSeek LLM + source citations)
  ↓
Compliance guardrails (medical / promise / out-of-scope / implication detection)
  ↓
Grounding guardrail (LLM anti-hallucination verification)
  ↓
Output: answer + sources + compliance status + human-handoff flag
```

## 📁 Directory Structure

```
├── data/          # Knowledge base data (products / ingredients / usage / after-sales)
├── src/           # Core source
│   ├── rag_engine.py      # RAG hybrid retrieval engine (FAISS + BM25 + RRF)
│   ├── intent_router.py   # Intent recognition & routing (6 classes + human handoff)
│   ├── answer_generator.py # Answer generation (LLM + sources + grounding + query rewrite)
│   ├── api_server.py      # FastAPI interface layer
│   ├── app.py             # Streamlit web UI
│   └── config.py          # Unified configuration
├── skills/        # Skill definitions
│   └── compliance_check.py # Compliance guardrail skill
├── tests/         # Tests
│   ├── run_tests.py       # Full test suite (30 items)
│   └── rag_triad_eval.py  # RAG Triad evaluation
├── scripts/       # Helper scripts
│   ├── build_index.py     # Knowledge base vectorization (title-aware chunking)
│   └── upload_github.py   # GitHub upload
├── docs/          # Project documents
│   ├── SOW工作说明书.md
│   ├── 最终交付报告.md
│   └── 需求拆解与排期文档.md
└── output/        # Outputs (test reports, etc.)
```

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install faiss-cpu rank-bm25 streamlit fastapi openai sentence-transformers

# 2. Build the knowledge-base index (first run)
python scripts/build_index.py

# 3. Launch the web demo
streamlit run src/app.py

# 4. Start the API service
python src/api_server.py
# Visit http://localhost:8502/docs for the API docs

# 5. Run tests
python tests/run_tests.py
python tests/rag_triad_eval.py
```

## 📊 Test Results

| Module | Pass rate |
|--------|-----------|
| Intent recognition | 13/13 = 100% |
| Compliance guardrails | 7/7 = 100% |
| RAG retrieval | 4/5 = 80% |
| End-to-end answers | 5/5 = 100% |
| **Overall** | **96.7%** |

## 🧠 Core Capabilities

1. **Hybrid retrieval with RRF fusion**: FAISS semantic + BM25 keyword search + RRF ranking
2. **Intent recognition & routing**: 6 intent classes + automatic human handoff for high-risk cases
3. **Compliance guardrails**: medical diagnosis / absolute promises / efficacy overreach / medical implication detection
4. **Title-aware chunking**: Markdown-header-based chunks with heading-path context
5. **Query rewrite + retry**: LLM rewrites and retries when retrieval quality is low
6. **Grounding guardrail**: LLM verifies answers are grounded in retrieved material (anti-hallucination)
7. **RAG Triad evaluation**: context relevance / answer faithfulness / answer relevance
8. **API layer**: FastAPI exposes a REST API for enterprise integration

## 📝 Project Documents

- [SOW (statement of work)](docs/SOW工作说明书.md)
- [Final delivery report](docs/最终交付报告.md)
- [Requirements breakdown & schedule](docs/需求拆解与排期文档.md)

## 📄 License

MIT
