"""
美妆零售知识库 AI 客服助手 · Streamlit Web 演示界面
运行方式：streamlit run src/app.py
"""

import sys
import os
from pathlib import Path

# 确保能导入项目模块
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills"))

import streamlit as st

# 页面配置
st.set_page_config(
    page_title="美妆零售知识库 AI 客服",
    page_icon="💄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 顶部样式
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #ff6b9d 0%, #c44dff 100%);
        padding: 24px 32px;
        border-radius: 16px;
        color: white;
        margin-bottom: 24px;
    }
    .main-header h1 { margin: 0; font-size: 1.8em; }
    .main-header p { margin: 8px 0 0; opacity: 0.9; }
    .answer-box {
        background: #f8f9fa;
        border-left: 4px solid #ff6b9d;
        padding: 16px 20px;
        border-radius: 8px;
        margin: 12px 0;
    }
    .source-tag {
        display: inline-block;
        background: #e9ecef;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.85em;
        margin-right: 6px;
    }
    .verdict-pass { color: #16a34a; font-weight: 600; }
    .verdict-block { color: #dc2626; font-weight: 600; }
    .verdict-human { color: #ca8a04; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_agent():
    """加载答案生成 Agent（缓存，避免重复加载模型）"""
    from answer_generator import AnswerGenerator
    return AnswerGenerator()


def main():
    # 头部
    st.markdown("""
    <div class="main-header">
        <h1>💄 美妆零售知识库 AI 客服助手</h1>
        <p>基于 RAG 混合检索 + 意图识别 + 合规风控的智能客服系统 | FDE 共学营大作业</p>
    </div>
    """, unsafe_allow_html=True)

    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 系统信息")
        st.info("**技术栈**\n- RAG: FAISS + BM25 + RRF\n- LLM: DeepSeek\n- UI: Streamlit")
        st.divider()
        st.header("🔍 示例问题")
        examples = [
            "烟酰胺有什么功效？",
            "敏感肌可以用视黄醇吗？",
            "这款面霜多少钱？",
            "拆封了还能退货吗？",
            "用了之后过敏了怎么办？",
        ]
        for ex in examples:
            if st.button(ex, key=ex, use_container_width=True):
                st.session_state["query"] = ex
        st.divider()
        st.caption("FDE 共学营 · 大作业演示")

    # 主区域
    agent = load_agent()

    # 输入区
    default_query = st.session_state.get("query", "")
    query = st.text_input("💬 输入您的美妆咨询问题：", value=default_query,
                          placeholder="例如：烟酰胺有什么功效？")

    col1, col2, col3 = st.columns([1, 1, 4])
    ask_btn = col1.button("🚀 发送", use_container_width=True, type="primary")
    clear_btn = col2.button("🧹 清空", use_container_width=True)

    if clear_btn:
        st.session_state["query"] = ""
        st.rerun()

    if ask_btn and query:
        with st.spinner("🔍 正在检索知识库并生成回答..."):
            try:
                result = agent.answer(query)

                # 展示回答
                st.markdown("### 📝 回答")
                verdict = result["compliance"]["verdict"]
                verdict_cls = {"pass": "verdict-pass", "block": "verdict-block", "human": "verdict-human"}[verdict]
                st.markdown(
                    f'<div class="answer-box">{result["answer"]}</div>',
                    unsafe_allow_html=True
                )

                # 合规状态
                if verdict == "pass":
                    st.success("✅ 合规检查通过")
                elif verdict == "block":
                    st.error(f"🚫 合规拦截：{result['compliance']['reason']}")
                else:
                    st.warning(f"⚠️ 需人工确认：{result['compliance']['reason']}")

                # 意图信息
                st.markdown(f"**意图识别：** {result['intent']['intent_label']} | "
                            f"**路由：** {result['intent']['route']} | "
                            f"**耗时：** {result['elapsed_ms']}ms")

                # 是否需要人工
                if result.get("needs_human"):
                    st.info("👨‍💼 本问题已标记为需人工介入")

                # 来源展示
                if result["sources"]:
                    st.markdown("### 📚 知识来源")
                    for i, s in enumerate(result["sources"]):
                        st.markdown(
                            f'<span class="source-tag">{s["source"]} 第{s["chunk_index"]+1}段</span>'
                            f'<span style="font-size:0.9em;color:#666;">{s["text"][:60]}...</span>',
                            unsafe_allow_html=True
                        )

                # 合规详情（有违规时）
                if result["compliance"]["violated_rules"]:
                    with st.expander("🔍 合规检查详情"):
                        for v in result["compliance"]["violated_rules"]:
                            st.markdown(f"- **[{v['label']}]** 关键词 \"{v['keyword']}\" → {v['message']}")

                # 完整 JSON（调试用）
                with st.expander("📄 原始响应 JSON"):
                    import json
                    st.json(result)

            except Exception as e:
                st.error(f"处理出错：{str(e)}")

    elif ask_btn:
        st.warning("请输入问题")

    # 页脚
    st.divider()
    st.caption("FDE 共学营 Day3/大作业 · 美妆零售知识库与客服协作 | 基于 RAG + Agent + 合规风控")


if __name__ == "__main__":
    main()
