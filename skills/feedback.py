"""
用户反馈闭环：点赞/点踩记录
功能：记录用户对回答的反馈（up/down），用于后续优化与评估
存储：output/feedback.json（追加式记录）
增强：点踩（down）的问答对自动记录到知识库待优化区（output/pending_optimization.json）
"""

import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
FEEDBACK_FILE = PROJECT_ROOT / "output" / "feedback.json"
PENDING_FILE = PROJECT_ROOT / "output" / "pending_optimization.json"


class FeedbackManager:
    """用户反馈管理器"""

    def __init__(self, feedback_file=None):
        self.feedback_file = Path(feedback_file) if feedback_file else FEEDBACK_FILE
        self.feedback_file.parent.mkdir(exist_ok=True)

    def _load(self) -> list:
        """加载已有反馈"""
        if not self.feedback_file.exists():
            return []
        try:
            with open(self.feedback_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save(self, data: list):
        """保存反馈"""
        with open(self.feedback_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record(self, query: str, answer: str, feedback: str,
               session_id: str = None, sources: list = None, comment: str = "") -> dict:
        """记录一条反馈
        feedback: 'up'（点赞）| 'down'（点踩）| 'neutral'（中性）
        点踩（down）的问答对自动记录到知识库待优化区
        """
        if feedback not in ("up", "down", "neutral"):
            raise ValueError("feedback 必须是 up/down/neutral")

        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "query": query,
            "answer": answer[:200],
            "feedback": feedback,
            "session_id": session_id,
            "sources": sources or [],
            "comment": comment,
        }

        data = self._load()
        data.append(entry)
        self._save(data)

        # 点踩 → 自动记录到知识库待优化区
        if feedback == "down":
            self._add_to_pending(entry)

        return entry

    # ===== 待优化区（知识库回馈）=====

    def _load_pending(self) -> list:
        """加载待优化记录"""
        if not PENDING_FILE.exists():
            return []
        try:
            with open(PENDING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_pending(self, data: list):
        """保存待优化记录"""
        PENDING_FILE.parent.mkdir(exist_ok=True)
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _add_to_pending(self, entry: dict):
        """把点踩问答对加入待优化区（去重）"""
        pending = self._load_pending()
        # 去重：相同 query 已存在则更新，否则追加
        exists = any(p["query"] == entry["query"] for p in pending)
        if not exists:
            pending.append({
                "query": entry["query"],
                "answer": entry["answer"],
                "sources": entry["sources"],
                "comment": entry.get("comment", ""),
                "downvoted_at": entry["timestamp"],
            })
            self._save_pending(pending)

    def pending_stats(self) -> dict:
        """待优化区统计"""
        pending = self._load_pending()
        return {
            "pending_count": len(pending),
            "queries": [p["query"] for p in pending],
        }

    def stats(self) -> dict:
        """反馈统计"""
        data = self._load()
        up = sum(1 for d in data if d.get("feedback") == "up")
        down = sum(1 for d in data if d.get("feedback") == "down")
        neutral = sum(1 for d in data if d.get("feedback") == "neutral")
        total = len(data)
        return {
            "total": total,
            "up": up,
            "down": down,
            "neutral": neutral,
            "satisfaction_rate": round(up / total, 2) if total else 0,
        }


if __name__ == "__main__":
    print("=" * 50)
    print("  用户反馈闭环 - 自测")
    print("=" * 50)

    fm = FeedbackManager()

    # 记录 3 条测试反馈
    fm.record("烟酰胺有什么功效？", "烟酰胺有助于提亮肤色...", "up", session_id="s1")
    fm.record("这款面霜多少钱？", "神经酰胺修护面霜139元...", "up", session_id="s2")
    fm.record("敏感肌可以用视黄醇吗？", "建议先做局部测试...", "down", session_id="s3", comment="回答太保守")

    stats = fm.stats()
    print(f"✅ 反馈记录数: {stats['total']}")
    print(f"   点赞: {stats['up']}, 点踩: {stats['down']}, 中性: {stats['neutral']}")
    print(f"   满意度: {stats['satisfaction_rate']}")

    # 验证文件存在且可读
    if FEEDBACK_FILE.exists():
        data = json.load(open(FEEDBACK_FILE, encoding="utf-8"))
        print(f"✅ feedback.json 已创建 ({len(data)} 条)")
        print(f"   文件: {FEEDBACK_FILE}")
        print(f"\n✅ 通过标准达成：反馈可记录到 output/feedback.json")
    else:
        print("❌ feedback.json 未创建")
