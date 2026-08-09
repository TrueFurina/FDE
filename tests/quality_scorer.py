"""
回答质量评分（LLM 自动评估）
功能：对回答从准确性、完整性、忠实度、合规性、可读性五个维度评分，输出 0-1 综合质量分
集成：可在 answer() 流程后调用，或独立批量评估
输出：output/quality_report.json
"""

import os
import json
import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
OUTPUT_DIR = PROJECT_ROOT / "output"


class AnswerQualityScorer:
    """回答质量评分器"""

    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def score(self, query: str, answer: str, sources: list = None) -> dict:
        """LLM 自动评估回答质量，输出 0-1 各维度分 + 综合分"""
        client = self._get_client()
        source_str = ", ".join(s.get("source", "") for s in (sources or [])) if sources else "无"

        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是回答质量评估专家。从准确性、完整性、忠实度、合规性、可读性五个维度评估客服回答，"
                                                  "每维度输出 0-1 分，并给出综合分和总体评价。"
                                                  "只输出JSON：{\"accuracy\":0-1,\"completeness\":0-1,\"faithfulness\":0-1,"
                                                  "\"compliance\":0-1,\"readability\":0-1,\"overall\":0-1,\"verdict\":\"优秀|良好|一般|较差\",\"comment\":\"...\"}"},
                    {"role": "user", "content": f"问题：{query}\n\n回答：{answer}\n\n参考资料来源：{source_str}"},
                ],
                temperature=0.1,
                max_tokens=250,
                response_format={"type": "json_object"},
            )
            result = json.loads(resp.choices[0].message.content.strip())
            return {
                "query": query,
                "answer_preview": answer[:100],
                "dimensions": {
                    "accuracy": float(result.get("accuracy", 0)),
                    "completeness": float(result.get("completeness", 0)),
                    "faithfulness": float(result.get("faithfulness", 0)),
                    "compliance": float(result.get("compliance", 0)),
                    "readability": float(result.get("readability", 0)),
                },
                "overall": float(result.get("overall", 0)),
                "verdict": result.get("verdict", "未知"),
                "comment": result.get("comment", ""),
            }
        except Exception as e:
            # 降级：基于规则粗评
            length_score = min(len(answer) / 200, 1.0)
            return {
                "query": query,
                "answer_preview": answer[:100],
                "dimensions": {
                    "accuracy": 0.5, "completeness": length_score,
                    "faithfulness": 0.5, "compliance": 0.5, "readability": length_score,
                },
                "overall": round(length_score * 0.6 + 0.4, 2),
                "verdict": "降级评估",
                "comment": f"LLM评估失败，降级为规则评估: {str(e)[:60]}",
            }


def main():
    print("=" * 60)
    print("  回答质量评分（LLM 自动评估）")
    print("=" * 60)

    from answer_generator import AnswerGenerator
    agent = AnswerGenerator()
    scorer = AnswerQualityScorer()

    # 评估 3 个示例回答
    queries = ["烟酰胺有什么功效？", "敏感肌可以用视黄醇吗？", "这款面霜多少钱？"]
    results = []

    for q in queries:
        result = agent.answer(q)
        quality = scorer.score(q, result["answer"], result["sources"])
        results.append(quality)
        print(f"\n🔍 {q}")
        print(f"  综合分: {quality['overall']} | 评级: {quality['verdict']}")
        print(f"  五维: 准确{quality['dimensions']['accuracy']} 完整{quality['dimensions']['completeness']} "
              f"忠实{quality['dimensions']['faithfulness']} 合规{quality['dimensions']['compliance']} 可读{quality['dimensions']['readability']}")
        print(f"  评价: {quality['comment'][:60]}")

    # 保存报告
    OUTPUT_DIR.mkdir(exist_ok=True)
    report_path = OUTPUT_DIR / "quality_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "items": results}, f, ensure_ascii=False, indent=2)
    print(f"\n  报告已保存: {report_path}")

    ok = all(0 <= r["overall"] <= 1 for r in results)
    print(f"\n  {'✅ 通过标准达成：输出0-1质量分' if ok else '❌ 未通过'}")


if __name__ == "__main__":
    main()
