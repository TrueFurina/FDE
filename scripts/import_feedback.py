"""
批量反馈导入
功能：批量导入用户反馈（从 CSV/JSON），合并到反馈库并统计
用法：python scripts/import_feedback.py <file>
"""

import sys
import json
import csv
import time
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "skills"))
OUTPUT_DIR = PROJECT_ROOT / "output"


class FeedbackImporter:
    """批量反馈导入器"""

    def __init__(self):
        from feedback import FeedbackManager
        self.manager = FeedbackManager()

    def import_csv(self, path: Path) -> dict:
        """从 CSV 导入反馈"""
        imported = 0
        errors = []
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                try:
                    feedback = row.get("feedback", "").strip()
                    if feedback not in ("up", "down", "neutral"):
                        feedback = "neutral"  # 默认中性
                    self.manager.record(
                        query=row.get("query", f"导入问题{i}"),
                        answer=row.get("answer", ""),
                        feedback=feedback,
                        session_id=row.get("session_id", "import"),
                        sources=[row.get("sources", "")] if row.get("sources") else [],
                        comment=row.get("comment", "批量导入"),
                    )
                    imported += 1
                except Exception as e:
                    errors.append({"row": i, "error": str(e)[:60]})
        return {"imported": imported, "errors": errors}

    def import_json(self, path: Path) -> dict:
        """从 JSON 导入反馈"""
        imported = 0
        errors = []
        try:
            data = json.load(open(path, encoding="utf-8"))
            if isinstance(data, dict):
                data = [data]
            for i, item in enumerate(data):
                try:
                    feedback = item.get("feedback", "neutral")
                    self.manager.record(
                        query=item.get("query", f"导入问题{i}"),
                        answer=item.get("answer", ""),
                        feedback=feedback,
                        session_id=item.get("session_id", "import"),
                        sources=item.get("sources", []),
                        comment=item.get("comment", "批量导入"),
                    )
                    imported += 1
                except Exception as e:
                    errors.append({"row": i, "error": str(e)[:60]})
        except (json.JSONDecodeError, FileNotFoundError) as e:
            return {"imported": 0, "errors": [{"error": str(e)[:80]}]}
        return {"imported": imported, "errors": errors}

    def get_stats(self) -> dict:
        """获取导入后的反馈统计"""
        return self.manager.stats()


def main():
    parser = argparse.ArgumentParser(description="批量反馈导入")
    parser.add_argument("file", help="反馈文件（CSV/JSON）")
    args = parser.parse_args()

    print("=" * 60)
    print("  批量反馈导入")
    print("=" * 60)

    path = Path(args.file)
    if not path.exists():
        print(f"  ❌ 文件不存在: {path}")
        return

    importer = FeedbackImporter()

    # 按扩展名导入
    if path.suffix.lower() == ".csv":
        result = importer.import_csv(path)
    elif path.suffix.lower() == ".json":
        result = importer.import_json(path)
    else:
        print(f"  ❌ 不支持的文件类型: {path.suffix}（仅支持 .csv/.json）")
        return

    print(f"\n  导入成功: {result['imported']} 条")
    if result["errors"]:
        print(f"  导入失败: {len(result['errors'])} 条")
        for e in result["errors"][:3]:
            print(f"    ⚠️ {e}")

    # 导入后统计
    stats = importer.get_stats()
    print(f"\n=== 导入后反馈统计 ===")
    print(f"  总反馈: {stats['total']}")
    print(f"  点赞: {stats['up']} | 点踩: {stats['down']} | 中性: {stats['neutral']}")
    print(f"  满意度: {stats['satisfaction_rate']}")

    ok = result["imported"] > 0 and stats["total"] > 0
    print(f"\n  {'✅ 通过标准达成：反馈可批量导入统计' if ok else '❌ 未通过'}")


if __name__ == "__main__":
    main()
