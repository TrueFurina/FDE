"""
FastAPI 接口层
功能：将知识库系统暴露为 REST API，便于集成到企业系统
运行：python src/api_server.py 或 uvicorn src.api_server:app --port 8000
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from answer_generator import AnswerGenerator

app = FastAPI(
    title="美妆零售知识库 API",
    description="美妆零售知识库与客服协作系统 - FDE 大作业交付",
    version="1.0.0",
)

# CORS（允许 Web 前端跨域调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局 Agent 实例（懒加载）
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = AnswerGenerator()
    return _agent


# ============ 请求/响应模型 ============

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="用户问题")
    top_k: int = Field(3, ge=1, le=10, description="检索返回条数")


class ComplianceRequest(BaseModel):
    text: str = Field(..., min_length=1, description="待检查文本")


# ============ API 端点 ============

@app.get("/")
def root():
    return {
        "service": "美妆零售知识库",
        "version": "1.0.0",
        "endpoints": [
            "GET  /health",
            "POST /api/answer",
            "POST /api/compliance",
        ]
    }


@app.get("/health")
def health():
    return {"status": "ok", "time": time.time()}


@app.post("/api/answer")
def answer(req: QueryRequest):
    """核心问答接口：意图识别 → 检索 → 生成 → 合规 → Grounding"""
    try:
        agent = get_agent()
        result = agent.answer(req.query, top_k=req.top_k)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@app.post("/api/compliance")
def compliance_check(req: ComplianceRequest):
    """合规风控检查接口"""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "skills"))
        from compliance_check import ComplianceChecker
        checker = ComplianceChecker()
        return checker.check(req.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查失败: {str(e)}")


@app.get("/api/intent")
def intent_route(query: str = "烟酰胺有什么功效"):
    """意图识别接口"""
    try:
        from intent_router import IntentRouter
        router = IntentRouter()
        return router.route(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


@app.get("/api/search")
def search(query: str = "烟酰胺", top_k: int = 3):
    """纯检索接口（调试用）"""
    try:
        from rag_engine import RAGEngine
        rag = RAGEngine()
        return {"query": query, "results": rag.hybrid_search(query, top_k=top_k)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  美妆零售知识库 API 服务")
    print("  文档: http://localhost:8000/docs")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
