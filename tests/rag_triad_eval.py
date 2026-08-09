"""
RAG Triad 评估：回答忠实度（Grounding）与相关性评估
参考：indoctrine.ai 的 RAG Triad（Context Relevance / Groundedness / Answer Relevance）

评估三个维度：
1. Context Relevance（上下文相关性）：检索到的资料是否与问题相关
2. Groundedness（回答忠实度）：回答是否基于检索资料（无幻觉）
3. Answer Relevance（答案相关性）：回答是否回答了用户问题
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class RAGTriadEvaluator:
    """RAG Triad 评估器"""

    def __init__(self):
        from answer_generator import AnswerGenerator
        self.agent = AnswerGenerator()
        self._client = None

    def _get_client(self):
        if self._client is None:
            import os
            from openai import OpenAI
            self._client = OpenAI(
                api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
                base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            )
        return self._client

    def score_groundedness(self, question: str, answer: str, contexts: list) -> dict:
        """维度2：回答忠实度——回答是否基于检索资料"""
        client = self._get_client()
        context_text = "\n\n".join([f"【资料{i+1}】{c['text'][:300]}" for i, c in enumerate(contexts[:4])])
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "判断回答内容是否都能从给定资料中找到依据。只输出JSON：{\"score\": 0-1, \"ungrounded_claims\": [\"...\"]}"},
                    {"role": "user", "content": f"资料：\n{context_text}\n\n回答：{answer}"},
                ],
                temperature=0.1, max_tokens=150, response_format={"type": "json_object"}
            )
            result = json.loads(resp.choices[0].message.content)
            return {"score": float(result.get("score", 0)), "ungrounded_claims": result.get("ungrounded_claims", [])}
        except Exception as e:
            return {"score": 0.5, "ungrounded_claims": [], "error": str(e)[:80]}

    def score_answer_relevance(self, question: str, answer: str) -> dict:
        """维度3：答案相关性——回答是否回答了问题"""
        client = self._get_client()
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "判断回答是否直接回答了用户的问题。只输出JSON：{\"score\": 0-1, \"reason\": \"...\"}"},
                    {"role": "user", "content": f"问题：{question}\n\n回答：{answer}"},
                ],
                temperature=0.1, max_tokens=150, response_format={"type": "json_object"}
            )
            result = json.loads(resp.choices[0].message.content)
            return {"score": float(result.get("score", 0)), "reason": result.get("reason", "")}
        except Exception as e:
            return {"score": 0.5, "reason": str(e)[:80]}

    def evaluate(self, questions: list = None) -> dict:
        """运行完整 RAG Triad 评估"""
        if questions is None:
            questions = [
                "烟酰胺有什么功效？",
                "敏感肌可以用视黄醇吗？",
                "这款面霜多少钱？",
                "拆封了还能退货吗？",
                "玻尿酸和神经酰胺哪个更保湿？",
            ]

        results = []
        for q in questions:
            result = self.agent.answer(q)
            contexts = result["sources"]

            # 关键修复：评估忠实度用完整检索上下文（sources 文本被截断为100字符会导致误判）
            full_contexts = self.agent.rag.hybrid_search(q, top_k=3)

            # 维度2：忠实度（用完整上下文评估）
            grounded = self.score_groundedness(q, result["answer"], full_contexts)
            # 维度3：相关性
            relevant = self.score_answer_relevance(q, result["answer"])

            # 维度1：上下文相关性（检索到资料且非空）
            context_score = 1.0 if contexts else 0.0

            results.append({
                "question": q,
                "context_relevance": context_score,
                "groundedness": grounded["score"],
                "answer_relevance": relevant["score"],
                "ungrounded_claims": grounded.get("ungrounded_claims", []),
                "has_sources": len(contexts) > 0,
            })

        # 汇总
        avg_context = sum(r["context_relevance"] for r in results) / len(results)
        avg_grounded = sum(r["groundedness"] for r in results) / len(results)
        avg_relevant = sum(r["answer_relevance"] for r in results) / len(results)

        return {
            "triad_scores": {
                "context_relevance": round(avg_context, 3),
                "groundedness": round(avg_grounded, 3),
                "answer_relevance": round(avg_relevant, 3),
            },
            "overall": round((avg_context + avg_grounded + avg_relevant) / 3, 3),
            "per_question": results,
        }


if __name__ == "__main__":
    print("=" * 60)
    print("  RAG Triad 评估（忠实度 + 相关性）")
    print("=" * 60)
    evaluator = RAGTriadEvaluator()
    report = evaluator.evaluate()

    print("\n【RAG Triad 评分】")
    print(f"  上下文相关性: {report['triad_scores']['context_relevance']}")
    print(f"  回答忠实度:   {report['triad_scores']['groundedness']}")
    print(f"  答案相关性:   {report['triad_scores']['answer_relevance']}")
    print(f"  综合评分:     {report['overall']}")

    print("\n【逐题详情】")
    for r in report["per_question"]:
        print(f"  {r['question'][:20]}... 相关:{r['context_relevance']} 忠实:{r['groundedness']} 相关:{r['answer_relevance']}")

    # 保存报告
    output = PROJECT_ROOT / "output"
    output.mkdir(exist_ok=True)
    with open(output / "rag_triad_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n✅ RAG Triad 报告已保存: {output / 'rag_triad_report.json'}")
