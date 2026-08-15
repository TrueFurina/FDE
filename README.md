# 美妆零售知识库与客服协作系统

> **版权声明 Copyright**：© 2026 All Rights Reserved. 未经作者书面许可，禁止复制、修改、分发、商用、用于各类学科竞赛。
>
> FDE 共学营大作业 | 美妆零售 AI 知识库与客服辅助系统
> 基于 RAG 混合检索 + 意图路由 + 合规风控 + Grounding 防幻觉

## 📋 项目简介

为美妆零售企业客服/导购构建 AI 辅助系统，解决知识分散、查找耗时、口径不一、合规风险等问题。

**定义的真问题：** 将新客服培养成资深员工水平的时间从 2-4 周缩短到 1 周以内，确保回复口径一致、合规、可追溯。

## 🏗️ 系统架构

```
用户咨询
  ↓
意图识别与路由（6类意图 + 高风险转人工）
  ↓
RAG 混合检索（FAISS向量 + BM25关键词 + RRF融合）
  ↓
查询重写+重试（检索质量低时自动改写）
  ↓
答案生成（DeepSeek LLM + 来源标注）
  ↓
合规风控（医疗/承诺/越界/暗示检测）
  ↓
Grounding 护栏（LLM 防幻觉校验）
  ↓
输出：答案 + 来源 + 合规状态 + 转人工标记
```

## 📁 目录结构

```
├── data/          # 知识库数据（产品/成分/用法/售后）
├── src/           # 核心源码
│   ├── rag_engine.py      # RAG 混合检索引擎（FAISS+BM25+RRF）
│   ├── intent_router.py   # 意图识别与路由（6类+转人工）
│   ├── answer_generator.py # 答案生成（LLM+来源+Grounding+查询重写）
│   ├── api_server.py      # FastAPI 接口层
│   ├── app.py             # Streamlit Web 界面
│   └── config.py          # 统一配置
├── skills/        # Skill 定义
│   └── compliance_check.py # 合规风控 Skill
├── tests/         # 测试
│   ├── run_tests.py       # 完整测试套件（30项）
│   └── rag_triad_eval.py  # RAG Triad 评估
├── scripts/       # 辅助脚本
│   ├── build_index.py     # 知识库向量化（标题感知分块）
│   └── upload_github.py   # GitHub 上传
├── docs/          # 项目文档
│   ├── SOW工作说明书.md
│   ├── 最终交付报告.md
│   └── 需求拆解与排期文档.md
└── output/        # 输出（测试报告等）
```

## 🚀 快速开始

```bash
# 1. 安装依赖
pip install faiss-cpu rank-bm25 streamlit fastapi openai sentence-transformers

# 2. 构建知识库索引（首次）
python scripts/build_index.py

# 3. 启动 Web 演示
streamlit run src/app.py

# 4. 启动 API 服务
python src/api_server.py
# 访问 http://localhost:8502/docs 查看 API 文档

# 5. 运行测试
python tests/run_tests.py
python tests/rag_triad_eval.py
```

## 📊 测试结果

| 模块 | 通过率 |
|------|--------|
| 意图识别 | 13/13 = 100% |
| 合规风控 | 7/7 = 100% |
| RAG 检索 | 4/5 = 80% |
| 端到端回答 | 5/5 = 100% |
| **总体** | **96.7%** |

## 🧠 核心能力

1. **混合检索 RRF 融合**：FAISS 语义 + BM25 关键词 + RRF 排序
2. **意图识别路由**：6 类意图 + 高风险自动转人工
3. **合规风控**：医疗诊断/绝对承诺/功效越界/医疗暗示检测
4. **标题感知分块**：按 Markdown 标题切块，带标题路径上下文
5. **查询重写+重试**：检索质量低时 LLM 改写重试
6. **Grounding 护栏**：LLM 校验回答基于检索资料（防幻觉）
7. **RAG Triad 评估**：上下文相关性/回答忠实度/答案相关性
8. **API 接口层**：FastAPI 暴露 REST API，便于企业集成

## 📝 项目文档

- [SOW 工作说明书](docs/SOW工作说明书.md)
- [最终交付报告](docs/最终交付报告.md)
- [需求拆解与排期文档](docs/需求拆解与排期文档.md)

## 📄 License

MIT
