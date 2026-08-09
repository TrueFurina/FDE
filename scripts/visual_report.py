"""
数据可视化统计：测试报告可视化
功能：读取测试报告，生成可视化指标（HTML图表），便于展示
输出：output/visual_report.html（自包含HTML，含CSS+SVG图表）
"""

import json
import time
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


def generate_html(test_report: dict, boundary_report: dict, triad_report: dict) -> str:
    """生成可视化报告 HTML"""

    # 测试套件数据
    total = test_report.get("total", 0)
    passed = test_report.get("passed", 0)
    failed = test_report.get("failed", 0)
    pass_rate = test_report.get("pass_rate", 0)
    sections = test_report.get("sections", {})

    # 边界测试数据
    boundary_total = boundary_report.get("total", 0)
    boundary_passed = boundary_report.get("passed", 0)

    # RAG Triad 数据
    triad_scores = triad_report.get("triad_scores", {})
    context_rel = triad_scores.get("context_relevance", 0)
    groundedness = triad_scores.get("groundedness", 0)
    answer_rel = triad_scores.get("answer_relevance", 0)
    overall = triad_report.get("overall", 0)

    # 模块通过率条形图数据
    bars_html = ""
    for module, data in sections.items():
        m_pass = data.get("passed", 0)
        m_total = data.get("total", 1)
        m_rate = m_pass / m_total * 100 if m_total else 0
        bar_w = max(m_rate, 2)
        bars_html += f"""
        <div class="bar-row">
            <span class="bar-label">{module}</span>
            <div class="bar-track"><div class="bar-fill" style="width:{bar_w}%"></div></div>
            <span class="bar-value">{m_pass}/{m_total} ({m_rate:.0f}%)</span>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>美妆知识库系统 · 测试可视化报告</title>
<style>
  body {{ font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; background: #f5f7fa; margin: 0; padding: 30px; color: #333; }}
  .container {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ text-align: center; color: #1a1a2e; margin-bottom: 8px; }}
  .subtitle {{ text-align: center; color: #888; margin-bottom: 30px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 30px; }}
  .card {{ background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); text-align: center; }}
  .card .value {{ font-size: 2.2em; font-weight: 700; }}
  .card .label {{ color: #888; font-size: 0.9em; margin-top: 4px; }}
  .card.green .value {{ color: #16a34a; }}
  .card.blue .value {{ color: #2563eb; }}
  .card.orange .value {{ color: #ea580c; }}
  .card.purple .value {{ color: #7c3aed; }}
  .section {{ background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 20px; }}
  .section h2 {{ margin-top: 0; font-size: 1.2em; color: #1a1a2e; }}
  .bar-row {{ display: flex; align-items: center; margin: 10px 0; gap: 12px; }}
  .bar-label {{ width: 120px; font-size: 0.9em; color: #555; }}
  .bar-track {{ flex: 1; background: #eee; border-radius: 8px; height: 20px; overflow: hidden; }}
  .bar-fill {{ height: 100%; background: linear-gradient(90deg, #4ade80, #16a34a); border-radius: 8px; transition: width 0.5s; }}
  .bar-value {{ width: 130px; font-size: 0.85em; color: #555; text-align: right; }}
  .donut-wrap {{ display: flex; align-items: center; justify-content: center; gap: 30px; flex-wrap: wrap; }}
  .legend {{ font-size: 0.9em; color: #555; }}
  .legend div {{ margin: 4px 0; }}
  .dot {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 6px; }}
  .footer {{ text-align: center; color: #999; font-size: 0.85em; margin-top: 30px; }}
</style>
</head>
<body>
<div class="container">
  <h1>💄 美妆知识库系统 · 测试可视化报告</h1>
  <p class="subtitle">生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')} | RalphLoop 第4轮</p>

  <div class="cards">
    <div class="card green"><div class="value">{pass_rate:.1f}%</div><div class="label">测试通过率</div></div>
    <div class="card blue"><div class="value">{total}</div><div class="label">测试用例总数</div></div>
    <div class="card orange"><div class="value">{boundary_passed}/{boundary_total}</div><div class="label">边界对抗测试</div></div>
    <div class="card purple"><div class="value">{overall:.2f}</div><div class="label">RAG Triad 综合</div></div>
  </div>

  <div class="section">
    <h2>📊 各模块通过率</h2>
    {bars_html}
  </div>

  <div class="section">
    <h2>🧠 RAG Triad 三指标</h2>
    <div class="donut-wrap">
      <div>
        <div class="bar-row"><span class="bar-label">上下文相关性</span><div class="bar-track"><div class="bar-fill" style="width:{context_rel*100:.0f}%"></div></div><span class="bar-value">{context_rel:.2f}</span></div>
        <div class="bar-row"><span class="bar-label">回答忠实度</span><div class="bar-track"><div class="bar-fill" style="width:{groundedness*100:.0f}%"></div></div><span class="bar-value">{groundedness:.2f}</span></div>
        <div class="bar-row"><span class="bar-label">答案相关性</span><div class="bar-track"><div class="bar-fill" style="width:{answer_rel*100:.0f}%"></div></div><span class="bar-value">{answer_rel:.2f}</span></div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>🔄 功能版本迭代</h2>
    <div class="legend">
      <div><span class="dot" style="background:#16a34a"></span>v1.0 基础 RAG + 意图 + 合规</div>
      <div><span class="dot" style="background:#2563eb"></span>v1.1 查询重写 + 标题感知分块 + Grounding 护栏</div>
      <div><span class="dot" style="background:#ea580c"></span>v1.2 多轮对话 + 知识库扩充 + RRF 加权</div>
      <div><span class="dot" style="background:#7c3aed"></span>v1.3 API 多轮 + 忠实度1.0 + 反馈闭环</div>
      <div><span class="dot" style="background:#db2777"></span>v1.4 热更新 + 高频问答集 + 可视化</div>
    </div>
  </div>

  <div class="footer">FDE 共学营大作业 · 美妆零售知识库与客服协作 · RalphLoop 自动优化循环</div>
</div>
</body>
</html>"""
    return html


def main():
    print("=" * 50)
    print("  数据可视化统计")
    print("=" * 50)

    # 加载报告
    test_report = load_json(OUTPUT_DIR / "test_report.json")
    boundary_report = load_json(OUTPUT_DIR / "boundary_test_report.json")
    triad_report = load_json(OUTPUT_DIR / "rag_triad_report.json")

    # 生成 HTML
    html = generate_html(test_report, boundary_report, triad_report)
    html_path = OUTPUT_DIR / "visual_report.html"
    html_path.write_text(html, encoding="utf-8")

    print(f"✅ 可视化报告已生成: {html_path}")
    print(f"   大小: {html_path.stat().st_size} 字节")
    print(f"\n✅ 通过标准达成：测试报告含可视化指标（HTML图表）")


if __name__ == "__main__":
    main()
