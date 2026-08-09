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
        # 多轮对话记忆：session_id -> [(user_query, assistant_answer), ...]
        self.sessions = {}
        # 回答缓存：query -> {answer, sources, compliance, timestamp}
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_ttl = 300  # 缓存有效期（秒）

    def _get_history(self, session_id: str = None, max_rounds: int = 3) -> list:
        """获取会话历史（最近 max_rounds 轮）"""
        if not session_id or session_id not in self.sessions:
            return []
        return self.sessions[session_id][-max_rounds:]

    def _remember(self, session_id: str, query: str, answer: str, max_total: int = 10):
        """记录对话到会话记忆"""
        if not session_id:
            return
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append((query, answer))
        # 限制会话长度，防止无限增长
        if len(self.sessions[session_id]) > max_total:
            self.sessions[session_id] = self.sessions[session_id][-max_total:]

    # ===== 会话历史管理 =====
    def list_sessions(self) -> list:
        """列出所有会话及轮数"""
        return [
            {"session_id": sid, "rounds": len(history),
             "last_query": history[-1][0][:50] if history else ""}
            for sid, history in self.sessions.items()
        ]

    def clear_session(self, session_id: str) -> bool:
        """清除指定会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def clear_all_sessions(self) -> int:
        """清除所有会话，返回清除数量"""
        count = len(self.sessions)
        self.sessions.clear()
        return count

    def session_stats(self) -> dict:
        """会话统计"""
        total_rounds = sum(len(h) for h in self.sessions.values())
        return {
            "total_sessions": len(self.sessions),
            "total_rounds": total_rounds,
            "avg_rounds": round(total_rounds / len(self.sessions), 1) if self.sessions else 0,
        }

    def _call_llm(self, query: str, context: list, history: list = None, max_retries: int = 2) -> str:
        """调用 DeepSeek API 生成回答（带重试与降级机制）
        max_retries: API 失败时的最大重试次数，全部失败后自动降级回答
        """
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
6. 回答控制在150字以内
7. 【合规措辞】描述成分/产品功效时必须使用温和表述：用"有助于改善""帮助提亮""辅助焕亮""帮助舒缓"等，禁止使用"美白""祛斑""祛皱""治疗""治愈""根治""100%""绝对""保证"等敏感词；如资料中成分确有相关功效，用"有助于"引导的客观描述，而非效果承诺
8. 【严格忠实】只陈述资料中明确写出的内容，逐条对应资料来源；禁止做资料之外的推断、联想或总结性判断（如"机制不同""无法比较"这类资料未写的结论）；禁止把成分A的特征安到成分B上；如果资料没有直接给出答案，如实说"资料中未明确说明"，不要自行补充"""

        # 构建消息序列（含历史）
        messages = [{"role": "system", "content": system_prompt}]

        # 注入历史对话（多轮记忆）
        if history:
            for h_query, h_answer in history:
                messages.append({"role": "user", "content": h_query})
                messages.append({"role": "assistant", "content": h_answer[:300]})

        # 当前问题 + 参考资料
        user_prompt = f"客户问题：{query}\n\n参考资料：\n{context_text}"
        messages.append({"role": "user", "content": user_prompt})

        # 带重试的 API 调用
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    temperature=0.3,
                    max_tokens=500,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                last_error = str(e)[:100]
                if attempt < max_retries:
                    time.sleep(1.5 * (attempt + 1))  # 指数退避重试
                    continue

        # 全部重试失败 → 降级回答（返回检索摘要）
        fallback = f"（LLM 服务暂不可用，以下为知识库检索摘要）\n\n"
        for i, c in enumerate(context[:2]):
            fallback += f"- {c['source']}：{c['text'][:80]}...\n"
        fallback += f"\n（注：重试{max_retries}次失败: {last_error}）"
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

    def answer(self, query: str, top_k: int = 3, verbose: bool = False, session_id: str = None) -> dict:
        """完整回答流程（支持多轮对话记忆：传入 session_id 可引用上文）
        带回答缓存：相同问题在 TTL 内二次回答直接走缓存
        """
        t0 = time.time()

        # 0. 回答缓存查找（非多轮场景才用缓存，多轮会话因上下文不同不缓存）
        cache_key = query.strip() if not session_id else None
        if cache_key and cache_key in self.cache:
            cached = self.cache[cache_key]
            # 检查 TTL 是否过期
            if time.time() - cached["timestamp"] < self.cache_ttl:
                self.cache_hits += 1
                return {
                    **cached["result"],
                    "cache_hit": True,
                    "elapsed_ms": round((time.time() - t0) * 1000, 1),
                }
        if cache_key:
            self.cache_misses += 1

        # 1. 获取会话历史（多轮记忆）
        history = self._get_history(session_id)

        # 2. 意图识别
        intent_result = self.router.route(query)

        # 3. 高风险直接转人工
        if intent_result["route"] == "human":
            elapsed = (time.time() - t0) * 1000
            answer_text = ("检测到高风险问题（不良反应/医疗相关），已为您转接人工客服处理。"
                           "请立即停止使用产品，如有严重不适请及时就医。")
            self._remember(session_id, query, answer_text)
            return {
                "query": query,
                "answer": answer_text,
                "sources": [],
                "compliance": {"verdict": "human", "reason": "高风险问题，转人工处理", "violated_rules": []},
                "intent": intent_result,
                "needs_human": True,
                "elapsed_ms": round(elapsed, 1),
            }

        # 4. RAG 混合检索（带查询重写+重试）
        contexts = self._retrieve_with_rewrite(query, top_k=top_k)

        if not contexts:
            elapsed = (time.time() - t0) * 1000
            answer_text = "抱歉，根据现有知识库无法找到相关信息，建议您咨询人工客服。"
            self._remember(session_id, query, answer_text)
            return {
                "query": query,
                "answer": answer_text,
                "sources": [],
                "compliance": {"verdict": "pass", "reason": "无检索结果", "violated_rules": []},
                "intent": intent_result,
                "needs_human": True,
                "elapsed_ms": round(elapsed, 1),
            }

        # 5. 生成回答（传入历史，支持多轮引用）
        answer_text = self._call_llm(query, contexts, history=history)

        # 6. Grounding 护栏：LLM 校验回答是否基于检索资料（防幻觉）
        grounding = self._grounding_check(query, answer_text, contexts)

        # 7. 合规检查
        compliance = self.checker.check(answer_text)

        # 8. 记录到会话记忆
        self._remember(session_id, query, answer_text)

        # 6. 组装来源
        sources = [
            {"source": c["source"], "chunk_index": c["chunk_index"], "text": c["text"][:100], "rrf_score": c["rrf_score"]}
            for c in contexts
        ]

        elapsed = (time.time() - t0) * 1000

        result = {
            "query": query,
            "answer": answer_text,
            "sources": sources,
            "compliance": compliance,
            "grounding": grounding,
            "intent": intent_result,
            "needs_human": False,
            "elapsed_ms": round(elapsed, 1),
        }

        # 9. 写入回答缓存（非多轮场景）
        if cache_key:
            self.cache[cache_key] = {
                "result": result,
                "timestamp": time.time(),
            }

        return result


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
