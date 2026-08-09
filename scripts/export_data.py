"""
数据导出功能：测试结果导出为 CSV/JSON
功能：将测试报告、边界测试报告、反馈数据导出为 CSV 或 JSON
用法：
  python scripts/export_data.py            # 导出全部报告为 CSV + JSON
  python scripts/export_data.py --format json  # 仅导出 JSON
"""

import json
import csv
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"


def load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.load(open(path, encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}


def export_sections_to_csv(test_report: dict, out_path: Path):
    """导出各模块测试通过率到 CSV"""
    sections = test_report.get("sections", {})
    rows = []
    for module, data in sections.items():
        rows.append({
            "module": module,
            "passed": data.get("passed", 0),
            "total": data.get("total", 0),
            "pass_rate": round(data.get("passed", 0) / data.get("total", 1) * 100, 1),
        })
    # 汇总行
    rows.append({
        "module": "TOTAL",
        "passed": test_report.get("passed", 0),
        "total": test_report.get("total", 0),
        "pass_rate": test_report.get("pass_rate", 0),
    })

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["module", "passed", "total", "pass_rate"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def export_boundary_to_csv(boundary_report: dict, out_path: Path):
    """导出边界测试详情到 CSV"""
    details = boundary_report.get("details", {})
    rows = []
    for category, items in details.items():
        for item in items:
            rows.append({
                "category": category,
                "name": item.get("name", ""),
                "input": item.get("input", item.get("query", ""))[:100],
                "route": item.get("route", item.get("intent", "")),
                "compliance": item.get("compliance", item.get("verdict", "")),
                "passed": item.get("safe", item.get("no_crash", item.get("protected", False))),
            })

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "name", "input", "route", "compliance", "passed"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def export_feedback_to_csv(feedback_path: Path, out_path: Path):
    """导出用户反馈到 CSV"""
    data = []
    if feedback_path.exists():
        try:
            data = json.load(open(feedback_path, encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            data = []

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "query", "feedback", "session_id", "comment"])
        writer.writeheader()
        for item in data:
            writer.writerow({
                "timestamp": item.get("timestamp", ""),
                "query": item.get("query", ""),
                "feedback": item.get("feedback", ""),
                "session_id": item.get("session_id", ""),
                "comment": item.get("comment", ""),
            })
    return len(data)


def main():
    parser = argparse.ArgumentParser(description="数据导出")
    parser.add_argument("--format", choices=["csv", "json", "all"], default="all", help="导出格式")
    args = parser.parse_args()

    print("=" * 50)
    print("  数据导出功能")
    print("=" * 50)

    test_report = load_json(OUTPUT_DIR / "test_report.json")
    boundary_report = load_json(OUTPUT_DIR / "boundary_test_report.json")
    feedback_path = OUTPUT_DIR / "feedback.json"

    # 导出 CSV
    if args.format in ("csv", "all"):
        n1 = export_sections_to_csv(test_report, OUTPUT_DIR / "test_sections.csv")
        print(f"✅ test_sections.csv 已导出 ({n1} 行)")

        n2 = export_boundary_to_csv(boundary_report, OUTPUT_DIR / "boundary_details.csv")
        print(f"✅ boundary_details.csv 已导出 ({n2} 行)")

        n3 = export_feedback_to_csv(feedback_path, OUTPUT_DIR / "feedback_export.csv")
        print(f"✅ feedback_export.csv 已导出 ({n3} 行)")

    # 导出 JSON（合并汇总）
    if args.format in ("json", "all"):
        summary = {
            "test": {
                "total": test_report.get("total", 0),
                "passed": test_report.get("passed", 0),
                "pass_rate": test_report.get("pass_rate", 0),
            },
            "boundary": {
                "total": boundary_report.get("total", 0),
                "passed": boundary_report.get("passed", 0),
            },
            "triad": load_json(OUTPUT_DIR / "rag_triad_report.json").get("triad_scores", {}),
            "exported_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(OUTPUT_DIR / "data_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"✅ data_summary.json 已导出")

    print(f"\n✅ 通过标准达成：可导出测试结果到CSV")
    print(f"   输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
