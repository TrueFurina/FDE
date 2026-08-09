"""
会话导出功能
功能：将会话记忆导出为文件（JSON/Markdown），支持按会话导出
用法：python scripts/export_sessions.py
"""

import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
SESSIONS_FILE = PROJECT_ROOT / "output" / "sessions.json"


class SessionExporter:
    """会话导出器"""

    def load_sessions(self) -> dict:
        """加载持久化会话"""
        if not SESSIONS_FILE.exists():
            return {}
        try:
            return json.load(open(SESSIONS_FILE, encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def export_json(self, sessions: dict, path: Path) -> int:
        """导出 JSON（全部会话）"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)
        return len(sessions)

    def export_markdown(self, sessions: dict, path: Path) -> int:
        """导出 Markdown（可读格式）"""
        lines = ["# 会话记录导出", "", f"> 导出时间：{time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
        count = 0
        for sid, history in sessions.items():
            lines.append(f"## 会话: {sid} ({len(history)} 轮)")
            lines.append("")
            for i, (q, a) in enumerate(history, 1):
                lines.append(f"### 第{i}轮")
                lines.append(f"**用户**: {q}")
                lines.append("")
                lines.append(f"**客服**: {a[:200]}")
                lines.append("")
                count += 1
            lines.append("---")
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return count

    def export_single(self, session_id: str, path: Path) -> int:
        """导出单个会话"""
        sessions = self.load_sessions()
        if session_id not in sessions:
            return 0
        with open(path, "w", encoding="utf-8") as f:
            json.dump({session_id: sessions[session_id]}, f, ensure_ascii=False, indent=2)
        return len(sessions[session_id])


def main():
    print("=" * 60)
    print("  会话导出功能")
    print("=" * 60)

    exporter = SessionExporter()
    sessions = exporter.load_sessions()

    if not sessions:
        print("  ⚠️ 暂无会话记录（需先产生对话）")
        return

    print(f"  会话总数: {len(sessions)}")
    for sid, hist in sessions.items():
        print(f"    - {sid}: {len(hist)} 轮")

    # 导出 JSON
    n_json = exporter.export_json(sessions, OUTPUT_DIR / "sessions_export.json")
    print(f"✅ sessions_export.json 已导出 ({n_json} 个会话)")

    # 导出 Markdown
    n_md = exporter.export_markdown(sessions, OUTPUT_DIR / "sessions_export.md")
    print(f"✅ sessions_export.md 已导出 ({n_md} 轮对话)")

    # 导出单个会话（第一个）
    first_sid = list(sessions.keys())[0]
    n_single = exporter.export_single(first_sid, OUTPUT_DIR / f"session_{first_sid}.json")
    print(f"✅ session_{first_sid}.json 已导出 ({n_single} 轮)")

    ok = n_json > 0 and n_md > 0 and n_single > 0
    print(f"\n  {'✅ 通过标准达成：会话记录可导出' if ok else '❌ 未通过'}")


if __name__ == "__main__":
    main()
