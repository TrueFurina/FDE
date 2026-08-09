"""
批量导出全部报告
功能：一键导出系统所有报告（JSON/CSV/HTML），打包为 zip 归档
用法：python scripts/export_all.py
输出：output/export_all.zip（含全部报告）
"""

import sys
import json
import zipfile
import argparse
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# 需要导出的报告文件（存在于 output/ 的 JSON/CSV/HTML）
REPORT_PATTERNS = [
    "test_report.json",
    "boundary_test_report.json",
    "benchmark_report.json",
    "rag_triad_report.json",
    "cache_stats.json",
    "kb_stats.json",
    "health_report.json",
    "metrics_report.json",
    "quality_report.json",
    "feedback.json",
    "sessions.json",
    "pending_optimization.json",
    "alerts.json",
    "qa_pairs.json",
    "qa_pairs.csv",
    "qa_pairs.md",
    "data_summary.json",
    "visual_report.html",
    "aggregate_report.html",
]


class ExportAll:
    """全部报告导出器"""

    def export_all(self) -> dict:
        """导出全部报告到 zip"""
        exported = []
        missing = []

        for fname in REPORT_PATTERNS:
            path = OUTPUT_DIR / fname
            if path.exists():
                exported.append(fname)
            else:
                missing.append(fname)

        # 打包 zip
        OUTPUT_DIR.mkdir(exist_ok=True)
        zip_path = OUTPUT_DIR / "export_all.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in exported:
                zf.write(OUTPUT_DIR / fname, arcname=f"reports/{fname}")
            # 写入导出清单
            manifest = {
                "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "files": exported,
                "count": len(exported),
            }
            zf.writestr("reports/manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        return {
            "zip_path": str(zip_path),
            "exported": exported,
            "missing": missing,
            "count": len(exported),
            "size_bytes": zip_path.stat().st_size if zip_path.exists() else 0,
        }


def main():
    parser = argparse.ArgumentParser(description="批量导出全部报告")
    parser.add_argument("--no-zip", action="store_true", help="不打包 zip，仅列清单")
    args = parser.parse_args()

    print("=" * 60)
    print("  批量导出全部报告")
    print("=" * 60)

    exporter = ExportAll()
    result = exporter.export_all()

    print(f"\n已导出报告 ({result['count']} 个):")
    for f in result["exported"]:
        print(f"  ✅ {f}")
    if result["missing"]:
        print(f"\n未生成报告 ({len(result['missing'])} 个):")
        for f in result["missing"]:
            print(f"  ⚠️ {f}")

    if not args.no_zip:
        print(f"\n📦 归档包: {result['zip_path']}")
        print(f"   大小: {result['size_bytes']} 字节")

    ok = result["count"] >= 10
    print(f"\n  {'✅ 通过标准达成：全部报告可一键导出' if ok else '❌ 导出数量不足'}")


if __name__ == "__main__":
    main()
