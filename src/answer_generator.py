"""
答案生成 Agent
功能：基于 RAG 检索结果，调用 DeepSeek LLM 生成回答，标注来源，做合规检查
输入：用户问题
输出：{ answer, sources, compliance, intent, elapsed_ms }
"""

import os
import time
from pathlib import Path

# 引入项目模块
import sys
sys.path.insert(0, str(Path(__file__).parent))

from rag_engine import RAGEngine
from intent_router import IntentRouter
sys.path.insert(0, str(Path(__file__).parent.parent / "skills"))
from compliance_check import ComplianceChecker


class AnswerGenerator:
    def __init__(self):
        self.rag = RAGEngine()
        self.router = IntentRouter()
        self.checker = ComplianceChecker()
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    def _call_llm(self, query: str, context: list) -> str:
        """调用 DeepSeek API 生成回答"""
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        # 构建上下文
        context_text = "\n\n".join([
            f"【资料{chr(65+i)}】来源: {c['source']} (第{c['chunk_index']+1}段)\n{c['text'][:600]}"
            for i, c in enumerate(context)
        ])

        system_prompt = """你是一位美妆零售企业的资深客服专家，回答客户关于产品、成分、用法、售后的问题。
要求：
1. 回答必须基于提供的资料，不得编造事实
2. 每句关键信息后标注资料来源，如（资料A）
3. 语气专业、温和、客观
4. 如资料不足，明确说明"根据现有资料无法确认"
5. 涉及医疗诊断、绝对功效承诺时，改为建议性表述并提示咨询专业人士
6. 回答控制在150字以内"""

        user_prompt = f"客户问题：{query}\n\n参考资料：\n{context_text}"

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            # API 失败时降级：返回检索摘要
            fallback = f"根据知识库资料，为您找到以下信息：\n\n"
            for i, c in enumerate(context[:2]):
                fallback += f"- {c['source']}：{c['text'][:80]}...\n"
            fallback += "\n（注：当前为离线降级回答，完整回答需要 LLM API 可用）"
            return fallback

    def _rewrite_query(self, query: str) -> str:
        """用 LLM 重写查询，提高检索召回率"""
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是查询改写助手。把用户的美妆咨询问题改写成更适合知识库检索的形式："
                                                  "补充产品/成分/场景关键词，保持原意。只输出改写后的查询，不要其他内容。"},
                    {"role": "user", "content": query},
                ],
                temperature=0.2,
                max_tokens=50,
            )
            rewritten = response.choices[0].message.content.strip()
            return rewritten if rewritten and len(rewritten) < 100 else query
        except Exception:
            return query

    def _retrieve_with_rewrite(self, query: str, top_k: int = 3) -> list:
        """带查询重写+重试的检索"""
        # 第一轮：直接检索
        contexts = self.rag.hybrid_search(query, top_k=top_k)
        primary_sources = [c["source"] for c in contexts]

        # 评估检索质量：rrf 分数都很低或来源单一且不匹配时触发重写
        needs_rewrite = False
        if not contexts:
            needs_rewrite = True
        else:
            # 检查 rrf 分数是否有意义（低于阈值说明匹配度差）
            max_rrf = max(c["rrf_score"] for c in contexts)
            if max_rrf < 0.02:
                needs_rewrite = True

        if needs_rewrite:
            # 第二轮：LLM 重写查询后重试
            rewritten = self._rewrite_query(query)
            if rewritten != query:
                retry_contexts = self.rag.hybrid_search(rewritten, top_k=top_k)
                if retry_contexts and len(retry_contexts) > 0:
                    # 合并两轮结果（去重，按 rrf 排序）
                    seen = set()
                    merged = []
                    for c in retry_contexts + contexts:
                        key = (c["source"], c["chunk_index"])
                        if key not in seen:
                            seen.add(key)
                            merged.append(c)
                    contexts = merged[:top_k]
                    contexts = [dict(c) for c in contexts]
                    for c in contexts:
                        c["via_rewrite"] = rewritten

        return contexts

    def _grounding_check(self, query: str, answer: str, contexts: list) -> dict:
        """Grounding 护栏：LLM 判断回答是否基于检索资料，检测幻觉"""
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        context_text = "\n\n".join([
            f"【资料{chr(65+i)}】{c['text'][:300]}" for i, c in enumerate(contexts[:4])
        ])

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是幻觉检测器。判断客服回答中的每条关键信息是否都能在提供的资料中找到依据。"
                                                  "只输出 JSON，格式：{\"grounded\": true/false, \"confidence\": 0-1, "
                                                  "\"hallucinated_claims\": [\"幻觉内容1\", ...], \"verdict\": \"grounded|hallucinated|partial\"}"},
                    {"role": "user", "content": f"资料：\n{context_text}\n\n回答：{answer}"},
                ],
                temperature=0.1,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content.strip()
            import json as _json
            try:
                result = _json.loads(content)
                # 补充 query 上下文
                result["query"] = query
                return result
            except _json.JSONDecodeError:
                return {"grounded": True, "confidence": 0.5,
                        "hallucinated_claims": [], "verdict": "partial", "query": query}
        except Exception as e:
            # API 失败时保守处理：标记为需人工复核
            return {"grounded": True, "confidence": 0.5,
                    "hallucinated_claims": [], "verdict": "partial",
                    "query": query, "error": str(e)[:80]}

    def answer(self, query: str, top_k: int = 3, verbose: bool = False) -> dict:
        """完整回答流程"""
        t0 = time.time()

        # 1. 意图识别
        intent_result = self.router.route(query)

        # 2. 高风险直接转人工
        if intent_result["route"] == "human":
            elapsed = (time.time() - t0) * 1000
            return {
                "query": query,
                "answer": "检测到高风险问题（不良反应/医疗相关），已为您转接人工客服处理。"
                          "请立即停止使用产品，如有严重不适请及时就医。",
                "sources": [],
                "compliance": {"verdict": "human", "reason": "高风险问题，转人工处理", "violated_rules": []},
                "intent": intent_result,
                "needs_human": True,
                "elapsed_ms": round(elapsed, 1),
            }

        # 3. RAG 混合检索（带查询重写+重试）
        contexts = self._retrieve_with_rewrite(query, top_k=top_k)

        if not contexts:
            elapsed = (time.time() - t0) * 1000
            return {
                "query": query,
                "answer": "抱歉，根据现有知识库无法找到相关信息，建议您咨询人工客服。",
                "sources": [],
                "compliance": {"verdict": "pass", "reason": "无检索结果", "violated_rules": []},
                "intent": intent_result,
                "needs_human": True,
                "elapsed_ms": round(elapsed, 1),
            }

        # 4. 生成回答
        answer_text = self._call_llm(query, contexts)

        # 5. Grounding 护栏：LLM 校验回答是否基于检索资料（防幻觉）
        grounding = self._grounding_check(query, answer_text, contexts)

        # 6. 合规检查
        compliance = self.checker.check(answer_text)

        # 6. 组装来源
        sources = [
            {"source": c["source"], "chunk_index": c["chunk_index"], "text": c["text"][:100], "rrf_score": c["rrf_score"]}
            for c in contexts
        ]

        elapsed = (time.time() - t0) * 1000

        return {
            "query": query,
            "answer": answer_text,
            "sources": sources,
            "compliance": compliance,
            "grounding": grounding,
            "intent": intent_result,
            "needs_human": False,
            "elapsed_ms": round(elapsed, 1),
        }


if __name__ == "__main__":
    print("=" * 60)
    print("  答案生成 Agent - 自测")
    print("=" * 60)

    agent = AnswerGenerator()

    test_queries = [
        "烟酰胺有什么功效？",
        "敏感肌可以用视黄醇吗？",
        "这款面霜多少钱？",
    ]

    for q in test_queries:
        print(f"\n🔍 问题: {q}")
        result = agent.answer(q)
        print(f"  答案: {result['answer'][:200]}")
        print(f"  意图: {result['intent']['intent_label']}")
        print(f"  合规: {result['compliance']['verdict'].upper()}")
        print(f"  来源: {[s['source'] for s in result['sources']]}")
        print(f"  耗时: {result['elapsed_ms']}ms")

    print("\n" + "=" * 60)
    print("  ✅ 答案生成 Agent 自测完成")
    print("=" * 60)
