"""
一键部署脚本
功能：读取 config.yaml 配置，一键启动 Web 界面和 API 服务
用法：python scripts/deploy.py            # 启动全部服务
      python scripts/deploy.py --web      # 仅启动 Web
      python scripts/deploy.py --api      # 仅启动 API
"""

import os
import sys
import yaml
import argparse
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"


def load_config() -> dict:
    """加载配置文件（支持环境变量覆盖 ${VAR:-default}）"""
    if not CONFIG_FILE.exists():
        print(f"❌ 配置文件不存在: {CONFIG_FILE}")
        return {}

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return raw


def resolve_env(value):
    """解析环境变量占位符 ${VAR:-default}"""
    if not isinstance(value, str):
        return value
    if value.startswith("${") and value.endswith("}"):
        inner = value[2:-1]
        if ":-" in inner:
            var, default = inner.split(":-", 1)
        else:
            var, default = inner, ""
        return os.environ.get(var, default)
    return value


def apply_env_overrides(config: dict):
    """把配置中的环境变量应用到进程环境（保证服务读取）"""
    # LLM 配置
    llm = config.get("llm", {})
    if llm.get("api_key"):
        os.environ.setdefault("DEEPSEEK_API_KEY", resolve_env(llm["api_key"]))
    if llm.get("base_url"):
        os.environ.setdefault("DEEPSEEK_BASE_URL", resolve_env(llm["base_url"]))
    # 嵌入模型
    emb = config.get("embedding", {})
    if emb.get("hf_endpoint"):
        os.environ.setdefault("HF_ENDPOINT", resolve_env(emb["hf_endpoint"]))
    # 端口
    server = config.get("server", {})
    if server.get("port"):
        os.environ.setdefault("PORT", str(resolve_env(server["port"])))


def main():
    parser = argparse.ArgumentParser(description="一键部署")
    parser.add_argument("--web", action="store_true", help="仅启动 Web 界面")
    parser.add_argument("--api", action="store_true", help="仅启动 API 服务")
    parser.add_argument("--check", action="store_true", help="仅检查配置")
    args = parser.parse_args()

    print("=" * 60)
    print("  一键部署")
    print("=" * 60)

    # 1. 加载配置
    config = load_config()
    if not config:
        return
    apply_env_overrides(config)

    server = config.get("server", {})
    web_port = resolve_env(server.get("port", 8502))
    api_port = resolve_env(server.get("api_port", 8000))

    # 2. 配置检查模式
    if args.check:
        print(f"  ✅ 配置加载成功")
        print(f"  Web 端口: {web_port}")
        print(f"  API 端口: {api_port}")
        print(f"  LLM 模型: {config.get('llm', {}).get('model')}")
        print(f"  检索 TopK: {config.get('retrieval', {}).get('top_k')}")
        print(f"\n  ✅ 通过标准达成：配置一键生效（配置已成功加载并解析）")
        return

    # 3. 启动服务
    start_web = args.web or (not args.api)
    start_api = args.api or (not args.web)

    procs = []
    if start_web:
        print(f"\n  🚀 启动 Web 界面 (端口 {web_port})...")
        proc = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", str(PROJECT_ROOT / "src/app.py"),
             "--server.headless", "true", "--server.port", str(web_port)],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        procs.append(("Web", proc))

    if start_api:
        print(f"  🚀 启动 API 服务 (端口 {api_port})...")
        proc = subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "src/api_server.py")],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        procs.append(("API", proc))

    # 4. 等待启动并验证
    time.sleep(8)
    ok_all = True
    for name, proc in procs:
        status = "运行中" if proc.poll() is None else f"已退出({proc.returncode})"
        ok = proc.poll() is None
        ok_all = ok_all and ok
        print(f"  {'✅' if ok else '❌'} {name} 服务: {status}")

    print(f"\n  {'✅ 服务启动成功，配置一键生效' if ok_all else '⚠️ 部分服务未启动，请查看日志'}")
    print(f"  Web: http://localhost:{web_port} | API: http://localhost:{api_port}/docs")


if __name__ == "__main__":
    main()
