"""
配置热加载
功能：动态读取 config.yaml 配置，修改配置无需重启即可生效
特点：
- 每次读取时检查文件修改时间，变化时重新加载
- 支持按需获取单个配置项
- 提供 mtime 监控（配置变化自动重载）
"""

import os
import time
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"

# 默认配置（config.yaml 缺失时的兜底）
DEFAULT_CONFIG = {
    "server": {"host": "0.0.0.0", "port": 8502, "api_port": 8000},
    "data": {"dir": "data", "chunk_size": 300, "chunk_overlap": 50},
    "llm": {
        "api_key": "${DEEPSEEK_API_KEY:-}",
        "base_url": "${DEEPSEEK_BASE_URL:-https://api.deepseek.com}",
        "model": "${DEEPSEEK_MODEL:-deepseek-chat}",
        "temperature": 0.3,
        "max_tokens": 500,
        "max_retries": 2,
    },
    "embedding": {
        "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "dim": 384,
        "hf_endpoint": "${HF_ENDPOINT:-https://hf-mirror.com}",
    },
    "retrieval": {
        "top_k": 5, "vector_top": 10, "bm25_top": 10,
        "vec_threshold": 0.5, "rrf_vector_k": 60, "rrf_bm25_k": 20,
        "rewrite_threshold": 0.02,
    },
    "cache": {"enabled": True, "ttl_seconds": 300},
    "session": {"max_rounds": 10, "history_rounds": 3, "persist": True, "file": "output/sessions.json"},
    "guard": {"max_query_len": 200, "injection_check": True},
}


class HotConfig:
    """配置热加载器"""

    def __init__(self, config_file=None, auto_reload=True):
        self.config_file = Path(config_file) if config_file else CONFIG_FILE
        self._config = None
        self._mtime = 0
        self._lock = threading.Lock()
        self.auto_reload = auto_reload
        self._load()

    def _load(self):
        """加载配置（带环境变量解析）"""
        config = {}
        if self.config_file.exists():
            try:
                import yaml
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                self._mtime = self.config_file.stat().st_mtime
            except Exception:
                config = {}
        # 合并默认值（缺失的键用默认）
        merged = self._deep_merge(DEFAULT_CONFIG, config)
        self._config = self._resolve_env(merged)

    @staticmethod
    def _deep_merge(default, override):
        """深度合并配置"""
        result = dict(default)
        for k, v in (override or {}).items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = HotConfig._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    @staticmethod
    def _resolve_env(config):
        """解析环境变量占位符 ${VAR:-default}"""
        if isinstance(config, dict):
            return {k: HotConfig._resolve_env(v) for k, v in config.items()}
        if isinstance(config, list):
            return [HotConfig._resolve_env(v) for v in config]
        if isinstance(config, str) and config.startswith("${") and config.endswith("}"):
            inner = config[2:-1]
            if ":-" in inner:
                var, default = inner.split(":-", 1)
            else:
                var, default = inner, ""
            return os.environ.get(var, default)
        return config

    def _check_reload(self):
        """检查配置文件是否变化，变化则重载（热加载核心）"""
        if not self.auto_reload or not self.config_file.exists():
            return
        try:
            current_mtime = self.config_file.stat().st_mtime
            if current_mtime != self._mtime:
                with self._lock:
                    self._load()
        except Exception:
            pass

    # ===== 对外接口 =====
    def get(self, section: str, key: str = None, default=None):
        """获取配置项（自动检查热加载）
        get("server", "port") → 端口
        get("retrieval", "top_k") → TopK
        """
        self._check_reload()
        section_cfg = self._config.get(section, {})
        if key is None:
            return section_cfg
        return section_cfg.get(key, default)

    def get_section(self, section: str) -> dict:
        """获取整个配置段"""
        self._check_reload()
        return self._config.get(section, {})

    def all(self) -> dict:
        """获取全部配置"""
        self._check_reload()
        return self._config

    def mtime(self) -> float:
        """获取配置最后修改时间"""
        self._check_reload()
        return self._mtime

    def reload(self):
        """手动强制重载"""
        with self._lock:
            self._load()


if __name__ == "__main__":
    print("=" * 60)
    print("  配置热加载 - 测试")
    print("=" * 60)

    config = HotConfig()

    # 1. 读取配置
    print(f"\nWeb 端口: {config.get('server', 'port')}")
    print(f"检索 TopK: {config.get('retrieval', 'top_k')}")
    print(f"LLM 模型: {config.get('llm', 'model')}")
    print(f"缓存 TTL: {config.get('cache', 'ttl_seconds')}")

    # 2. 记录初始 mtime
    mtime1 = config.mtime()
    print(f"\n初始配置 mtime: {mtime1}")

    # 3. 模拟修改配置（修改 config.yaml 的缓存 TTL）
    import time as _time
    _time.sleep(0.1)
    original = CONFIG_FILE.read_text(encoding="utf-8")
    modified = original.replace("ttl_seconds: 300", "ttl_seconds: 600")
    CONFIG_FILE.write_text(modified, encoding="utf-8")

    # 4. 热加载生效（无需重启）
    new_ttl = config.get('cache', 'ttl_seconds')
    mtime2 = config.mtime()
    print(f"\n修改后缓存 TTL: {new_ttl}（热加载自动生效）")
    print(f"mtime 已更新: {mtime2} != {mtime1}: {mtime2 != mtime1}")

    # 5. 恢复原始配置
    CONFIG_FILE.write_text(original, encoding="utf-8")
    config.reload()
    restored_ttl = config.get('cache', 'ttl_seconds')
    print(f"\n恢复后缓存 TTL: {restored_ttl}")

    ok = new_ttl == 600 and mtime2 != mtime1 and restored_ttl == 300
    print(f"\n  {'✅ 通过标准达成：修改配置无需重启生效' if ok else '❌ 未通过'}")
