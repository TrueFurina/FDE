"""
项目配置文件
把硬编码的参数统一抽到配置，便于部署和修改
"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# ============ 数据配置 ============
DATA_DIR = str(PROJECT_ROOT / "data")

# ============ LLM 配置 ============
LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 500

# ============ 嵌入模型配置 ============
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384
HF_ENDPOINT = "https://hf-mirror.com"  # 国内镜像

# ============ 检索配置 ============
RETRIEVAL_TOP_K = 5          # 最终返回条数
VECTOR_TOP_K = 10            # 向量检索候选数
BM25_TOP_K = 10              # BM25 检索候选数
RRF_K = 60                   # RRF 融合参数
RAG_REWRITE_THRESHOLD = 0.02  # 查询重写触发阈值（rrf 低于此值触发）

# ============ 意图识别配置 ============
# 高风险关键词（必须转人工）
RISK_KEYWORDS = [
    "过敏", "刺痛", "发红", "红肿", "起疹", "瘙痒", "痒", "肿", "呼吸困难",
    "治疗", "治愈", "处方", "医院", "医生", "药用", "疗程", "患者", "就医",
    "不良反应", "副作用", "烂脸", "毁容",
]

# ============ 合规风控配置 ============
COMPLIANCE_RULES = {
    "medical_diagnosis": {
        "keywords": ["治疗", "治愈", "处方", "药物", "疗程", "根治", "临床证明"],
        "level": "block",
        "label": "医疗诊断",
        "message": "不得使用医疗术语，建议修改为改善、缓解等表述",
    },
    "absolute_promise": {
        "keywords": ["100%", "绝对", "保证", "百分百", "无效退款", "一定有效", "包治"],
        "level": "block",
        "label": "绝对承诺",
        "message": "不得使用绝对化承诺用语",
    },
    "efficacy_overreach": {
        "keywords": ["美白", "抗衰老", "祛斑", "祛皱", "缩毛孔", "减肥", "增高", "祛痘印"],
        "level": "human",
        "label": "功效越界",
        "message": "涉及功效宣称，需确认产品是否有相关备案",
    },
    "medical_implication": {
        "keywords": ["医院", "医生推荐", "药用", "疗效", "患者", "处方药"],
        "level": "human",
        "label": "医疗暗示",
        "message": "涉及医疗场景暗示，需人工确认",
    },
}

# ============ Web 服务配置 ============
WEB_HOST = "0.0.0.0"
WEB_PORT = int(os.environ.get("PORT", 8502))

# ============ 分块配置 ============
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
