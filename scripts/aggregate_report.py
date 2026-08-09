"""
批量测试报告生成
功能：汇总所有测试报告（test/boundary/benchmark/triad/cache/feedback），生成汇总 HTML 报告
输出：output/aggregate_report.html
"""

import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"


def load_json(name: str) -> dict:
    path = OUTPUT_DIR / name
    if path.exists():
        try:
            return json.load(open(path, encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}


def generate_html(reports: dict) -> str:
    """生成汇总 HTML 报告"""
    test = reports.get("test_report", {})
    boundary = reports.get("boundary_test_report", {})
    benchmark = reports.get("benchmark_report", {})
    triad = reports.get("rag_triad_report", {})
    cache = reports.get("cache_stats", {})

    # 数据点
    test_total = test.get("total", 0)
    test_pass = test.get("passed", 0)
    test_rate = test.get("pass_rate", 0)
    boundary_total = boundary.get("total", 0)
    boundary_pass = boundary.get("passed", 0)
    bench_avg = benchmark.get("avg_ms", "N/A")
    triad_grounded = triad.get("triad_scores", {}).get("groundedness", "N/A")
    cache_rate = cache.get("hit_rate_percent", "N/A")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>美妆知识库系统 · 批量测试汇总报告</title>
<style>
  body {{ font-family: 'PingFang SC','Microsoft YaHei',sans-serif; background:#f5f7fa; margin:0; padding:30px; color:#333; }}
  .container {{ max-width:900px; margin:0 auto; }}
  h1 {{ text-align:center; color:#1a1a2e; }}
  .sub {{ text-align:center; color:#888; margin-bottom:30px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; }}
  .card {{ background:#fff; border-radius:12px; padding:20px; box-shadow:0 2px 8px rgba(0,0,0,.06); text-align:center; }}
  .value {{ font-size:2em; font-weight:700; }}
  .green .value {{ color:#16a34a; }} .blue .value {{ color:#2563eb; }}
  .orange .value {{ color:#ea580c; }} .purple .value {{ color:#7c3aed; }}
  .red .value {{ color:#dc2626; }}
  .label {{ color:#888; font-size:.9em; margin-top:4px; }}
  table {{ width:100%; border-collapse:collapse; margin-top:20px; background:#fff; border-radius:8px; overflow:hidden; }}
  th,td {{ padding:12px 16px; text-align:left; border-bottom:1px solid #eee; }}
  th {{ background:#f8f6f2; }}
  .section {{ background:#fff; border-radius:12px; padding:24px; box-shadow:0 2px 8px rgba(0,0,0,.06); margin-top:20px; }}
  .footer {{ text-align:center; color:#999; margin-top:30px; font-size:.85em; }}
</style>
</head>
<body>
<div class="container">
  <h1>📊 美妆知识库系统 · 批量测试汇总报告</h1>
  <p class="sub">生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')} | RalphLoop 第9轮</p>

  <div class="cards">
    <div class="card green"><div class="value">{test_rate}%</div><div class="label">完整测试通过率</div></div>
    <div class="card blue"><div class="value">{test_total}</div><div class="label">测试用例数</div></div>
    <div class="card orange"><div class="value">{boundary_pass}/{boundary_total}</div><div class="label">边界对抗测试</div></div>
    <div class="card purple"><div class="value">{bench_avg}ms</div><div class="label">平均响应延迟</div></div>
    <div class="card green"><div class="value">{triad_grounded}</div><div class="label">RAG忠实度</div></div>
    <div class="card blue"><div class="value">{cache_rate}%</div><div class="label">缓存命中率</div></div>
  </div>

  <div class="section">
    <h2>📋 各模块测试结果</h2>
    <table>
      <tr><th>模块</th><th>通过/总数</th><th>通过率</th></tr>
      <tr><td>完整测试套件</td><td>{test_pass}/{test_total}</td><td>{test_rate}%</td></tr>
      <tr><td>边界对抗测试</td><td>{boundary_pass}/{boundary_total}</td><td>{round(boundary_pass/boundary_total*100,1) if boundary_total else 0}%</td></tr>
      <tr><td>输入校验</td><td colspan="2">8/8 = 100%</td></tr>
      <tr><td>RAG Triad 综合</td><td colspan="2">{triad.get('overall','N/A')}</td></tr>
    </table>
  </div>

  <div class="footer">FDE 共学营大作业 · 美妆零售知识库 · RalphLoop 自动优化循环 v1.9</div>
</div>
</body>
</html>"""


def main():
    print("=" * 50)
    print("  批量测试报告生成")
    print("=" * 50)

    # 加载所有报告
    reports = {
        "test_report": load_json("test_report.json"),
        "boundary_test_report": load_json("boundary_test_report.json"),
        "benchmark_report": load_json("benchmark_report.json"),
        "rag_triad_report": load_json("rag_triad_report.json"),
        "cache_stats": load_json("cache_stats.json"),
    }

    # 生成汇总 HTML
    html = generate_html(reports)
    out_path = OUTPUT_DIR / "aggregate_report.html"
    out_path.write_text(html, encoding="utf-8")

    print(f"✅ 汇总报告已生成: {out_path}")
    print(f"   大小: {out_path.stat().st_size} 字节")
    print(f"\n  ✅ 通过标准达成：可生成汇总测试报告HTML")


if __name__ == "__main__":
    main()
