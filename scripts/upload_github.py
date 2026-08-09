"""
通过 GitHub REST API 上传项目文件到 TrueFurina/FDE
原因：github.com 的 git 协议不可达，但 api.github.com 可达
方式：逐个文件 PUT /repos/TrueFurina/FDE/contents/{path}
token 从环境变量 GITHUB_TOKEN 读取，不经过命令行
"""

import os
import json
import base64
import time
from pathlib import Path

import requests
import urllib3
urllib3.disable_warnings()

TOKEN = os.environ.get("GITHUB_TOKEN", "")
OWNER = "TrueFurina"
REPO = "FDE"
API = f"https://api.github.com/repos/{OWNER}/{REPO}/contents"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

# 项目根目录
PROJECT_ROOT = Path(r"E:\Program\美妆知识库")

# 排除的文件/目录（二进制索引、缓存等）
EXCLUDE_DIRS = {".git", "__pycache__", ".huggingface", "models", "venv", ".venv"}
EXCLUDE_FILES = {
    "faiss_index.bin", "bm25_index.pkl",  # 大二进制，可重建
    "demo_home.png", "demo_answer.png", "demo_full.png",  # 截图，可选
}


def list_project_files(root: Path):
    """列出所有要上传的文件"""
    files = []
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        # 相对路径
        rel = p.relative_to(root)
        parts = rel.parts
        # 排除目录
        if any(d in EXCLUDE_DIRS for d in parts):
            continue
        # 排除文件
        if p.name in EXCLUDE_FILES:
            continue
        files.append((rel.as_posix(), p))
    return files


def upload_file(path: str, file_path: Path, retries=3):
    """上传单个文件到 GitHub"""
    content = file_path.read_bytes()
    data = base64.b64encode(content).decode()

    payload = {
        "message": f"Add {path}",
        "content": data,
        "branch": "main",
    }

    for attempt in range(retries):
        try:
            r = requests.put(
                f"{API}/{path}",
                headers=HEADERS,
                json=payload,
                timeout=30,
                verify=False,
            )
            if r.status_code in (200, 201):
                return True, r.status_code
            elif r.status_code == 422 and "sha" in json.loads(r.text).get("message", ""):
                # 文件已存在，需要先删除或更新（此处跳过已存在文件）
                return False, 422
            else:
                time.sleep(2)
                continue
        except Exception:
            time.sleep(2)
            continue
    return False, 0


def main():
    print("=" * 60)
    print(f"  上传项目到 GitHub: {OWNER}/{REPO}")
    print("=" * 60)

    files = list_project_files(PROJECT_ROOT)
    print(f"待上传文件数: {len(files)}")

    # 先创建 README（确保仓库有初始内容）
    upload_file("README.md", PROJECT_ROOT / "README.md")

    success, failed, skipped = 0, 0, 0
    for path, file_path in files:
        if path == "README.md":
            continue  # 已传
        ok, code = upload_file(path, file_path)
        if ok:
            success += 1
            print(f"  ✅ {path}")
        elif code == 422:
            skipped += 1
            print(f"  ⏭️ {path} (已存在)")
        else:
            failed += 1
            print(f"  ❌ {path} (失败)")

    print("\n" + "=" * 60)
    print(f"  上传完成: 成功 {success}, 跳过 {skipped}, 失败 {failed}")
    print("=" * 60)

    # 验证
    time.sleep(2)
    r = requests.get(f"{API}/", headers=HEADERS, timeout=20, verify=False)
    if r.status_code == 200:
        names = [f["name"] for f in r.json()]
        print(f"  仓库文件数: {len(names)}")
        print(f"  文件列表: {names}")


if __name__ == "__main__":
    main()
