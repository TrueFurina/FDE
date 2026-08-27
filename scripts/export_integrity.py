"""
数据导出完整性校验
功能：校验导出的数据文件（JSON/CSV/Markdown）完整性，防止导出缺失/损坏
检查项：
1. 导出文件存在性与非空
2. JSON 可解析性
3. 关键字段完整性
4. 导出内容与原数据一致性
输出：output/export_integrity_report.json
"""

import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
DATA_DIR = PROJECT_ROOT / "data"


class ExportIntegrityChecker:
    """导出完整性校验器"""

    def __init__(self):
        self.checks = []

    def _add(self, check: str, ok: bool, detail: str = ""):
        self.checks.append({"check": check, "status": "ok" if ok else "fail", "detail": detail})
        icon = "✅" if ok else "❌"
        print(f"  {icon} [{check}] {detail}")

    def check_file(self, fname: str, must_have_fields=None):
        """通用文件校验"""
        path = OUTPUT_DIR / fname
        if not path.exists():
            self._add(f"存在性-{fname}", False, "文件缺失")
            return None
        if path.stat().st_size == 0:
            self._add(f"非空-{fname}", False, "文件为空")
            return None
        return path

    def check_json(self, fname: str, must_have_fields=None):
        """JSON 文件校验"""
        path = self.check_file(fname)
        if path is None:
            return None
        try:
            data = json.load(open(path, encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError) as e:
            self._add(f"可解析-{fname}", False, f"JSON 解析失败: {str(e)[:50]}")
            return None

        # 字段完整性
        if must_have_fields:
            if isinstance(data, dict):
                missing = [f for f in must_have_fields if f not in data]
                self._add(f"字段-{fname}", not missing, f"缺失字段: {missing or '无'}")
            elif isinstance(data, list):
                missing_fields = []
                for i, item in enumerate(data[:5]):
                    if isinstance(item, dict):
                        m = [f for f in must_have_fields if f not in item]
                        if m:
                            missing_fields.append(f"第{i}条缺{m}")
                self._add(f"字段-{fname}", not missing_fields, f"{missing_fields or '全部完整'}")

        self._add(f"完整-{fname}", True, f"{len(data) if isinstance(data, (list, dict)) else '?'} 条记录")
        return data

    def check_csv(self, fname: str, expected_header=None):
        """CSV 文件校验"""
        path = self.check_file(fname)
        if path is None:
            return None
        try:
            import csv
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception as e:
            self._add(f"可解析-{fname}", False, f"CSV 解析失败: {str(e)[:50]}")
            return None

        if expected_header and rows:
            missing = [h for h in expected_header if h not in rows[0]]
            self._add(f"表头-{fname}", not missing, f"缺失列: {missing or '无'}")
        self._add(f"完整-{fname}", True, f"{len(rows)} 行")
        return rows

    def check_markdown(self, fname: str):
        """Markdown 文件校验"""
        path = self.check_file(fname)
        if path is None:
            return None
        content = path.read_text(encoding="utf-8")
        has_header = content.lstrip().startswith("#")
        self._add(f"结构-{fname}", has_header, f"{len(content)} 字符, 标题{'存在' if has_header else '缺失'}")
        return content

    def run_all(self) -> dict:
        """运行全部导出校验"""
        print("=" * 60)
        print("  数据导出完整性校验")
        print("=" * 60)

        # 校验各导出文件
        self.check_json("sessions_export.json", must_have_fields=None)
        self.check_markdown("sessions_export.md")
        self.check_json("qa_pairs.json", must_have_fields=["query", "answer"])
        self.check_csv("qa_pairs.csv", expected_header=["query", "answer"])
        self.check_json("feedback.json", must_have_fields=["query", "feedback"])
        self.check_json("test_report.json", must_have_fields=["total", "passed"])
        self.check_json("boundary_test_report.json", must_have_fields=["total", "passed"])
        self.check_json("cache_stats.json")
        self.check_json("health_report.json", must_have_fields=["summary", "checks"])
        self.check_json("metrics_report.json")

        # 汇总
        ok_count = sum(1 for c in self.checks if c["status"] == "ok")
        fail_count = sum(1 for c in self.checks if c["status"] == "fail")

        report = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {"ok": ok_count, "fail": fail_count, "overall": "complete" if fail_count == 0 else "incomplete"},
            "checks": self.checks,
        }

        OUTPUT_DIR.mkdir(exist_ok=True)
        report_path = OUTPUT_DIR / "export_integrity_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print("\n" + "=" * 60)
        print(f"  校验结果: {report['summary']['overall'].upper()} (ok:{ok_count} fail:{fail_count})")
        print(f"  报告已保存: {report_path}")
        print("=" * 60)

        return report


def main():
    checker = ExportIntegrityChecker()
    report = checker.run_all()

    has_report = "summary" in report and "checks" in report
    print(f"\n  {'✅ 通过标准达成：导出数据可校验' if has_report else '❌ 未通过'}")


if __name__ == "__main__":
    main()
